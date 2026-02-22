#!/usr/bin/env python3
"""
ATLAS Orchestration Helper - Multi-Agent Coordination

Spawns and monitors multiple sub-agents, aggregates results, logs metrics.
Designed for ATLAS/OpenClaw to programmatically coordinate parallel tasks.

Usage:
    from orchestrate import Orchestrator
    
    orch = Orchestrator()
    tasks = [
        {"label": "research-x", "task": "Research topic X", "timeout": 300},
        {"label": "research-y", "task": "Research topic Y", "timeout": 300},
    ]
    results = orch.run_parallel(tasks)
"""

import os
import json
import time
import uuid
import subprocess
import threading
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
SESSIONS_DIR = Path("/root/.openclaw/agents/main/sessions")
METRICS_LOG = Path("/workspace/clawd/logs/agent_metrics.jsonl")
OUTPUTS_DIR = Path("/workspace/clawd/outputs")

# Status markers to look for in agent output
STATUS_COMPLETE = "[STATUS:COMPLETE]"
STATUS_PROGRESS = "[STATUS:PROGRESS]"
STATUS_BLOCKER = "[STATUS:BLOCKER]"
STATUS_STARTING = "[STATUS:STARTING]"


@dataclass
class AgentResult:
    """Result from a single agent task."""
    label: str
    status: str  # "complete", "timeout", "error", "partial"
    output_path: Optional[str] = None
    output_content: Optional[str] = None
    session_id: Optional[str] = None
    start_time: float = 0
    end_time: float = 0
    runtime_seconds: float = 0
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    cost_usd: float = 0
    error: Optional[str] = None
    progress_updates: List[str] = field(default_factory=list)


@dataclass  
class TaskDefinition:
    """Definition for an agent task."""
    label: str
    task: str
    timeout: int = 300  # seconds
    model: Optional[str] = None
    output_file: Optional[str] = None
    context: Optional[str] = None  # Additional context to inject


class SessionMonitor:
    """Monitor an OpenClaw session for completion."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_path = SESSIONS_DIR / f"{session_id}.jsonl"
        self._last_line = 0
        
    def exists(self) -> bool:
        """Check if session file exists."""
        return self.session_path.exists()
    
    def get_new_messages(self) -> List[dict]:
        """Get new messages since last check."""
        if not self.exists():
            return []
        
        messages = []
        try:
            with open(self.session_path, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[self._last_line:], start=self._last_line):
                    try:
                        msg = json.loads(line.strip())
                        messages.append(msg)
                    except json.JSONDecodeError:
                        pass
                self._last_line = len(lines)
        except Exception as e:
            pass
        return messages
    
    def get_all_messages(self) -> List[dict]:
        """Get all messages from the session."""
        if not self.exists():
            return []
        
        messages = []
        try:
            with open(self.session_path, 'r') as f:
                for line in f:
                    try:
                        msg = json.loads(line.strip())
                        messages.append(msg)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        return messages
    
    def extract_assistant_content(self, messages: List[dict]) -> str:
        """Extract all assistant message content."""
        content_parts = []
        for msg in messages:
            if msg.get("type") == "message":
                inner = msg.get("message", {})
                if inner.get("role") == "assistant":
                    for part in inner.get("content", []):
                        if part.get("type") == "text":
                            content_parts.append(part.get("text", ""))
        return "\n".join(content_parts)
    
    def extract_metrics(self, messages: List[dict]) -> dict:
        """Extract token usage and cost metrics."""
        total_input = 0
        total_output = 0
        total_cost = 0.0
        
        for msg in messages:
            if msg.get("type") == "message":
                inner = msg.get("message", {})
                usage = inner.get("usage", {})
                total_input += usage.get("input", 0)
                total_output += usage.get("output", 0)
                cost = usage.get("cost", {})
                if isinstance(cost, dict):
                    total_cost += cost.get("total", 0)
                elif isinstance(cost, (int, float)):
                    total_cost += cost
        
        return {
            "tokens_input": total_input,
            "tokens_output": total_output,
            "tokens_total": total_input + total_output,
            "cost_usd": total_cost
        }
    
    def check_completion(self, messages: List[dict]) -> tuple[bool, List[str]]:
        """Check if agent has reported completion. Returns (complete, progress_updates)."""
        progress = []
        complete = False
        
        for msg in messages:
            if msg.get("type") == "message":
                inner = msg.get("message", {})
                if inner.get("role") == "assistant":
                    for part in inner.get("content", []):
                        if part.get("type") == "text":
                            text = part.get("text", "")
                            if STATUS_COMPLETE in text:
                                complete = True
                            if STATUS_PROGRESS in text:
                                # Extract progress message
                                match = re.search(r'\[STATUS:PROGRESS\]\s*(.+?)(?:\n|$)', text)
                                if match:
                                    progress.append(match.group(1).strip())
        
        return complete, progress


class Orchestrator:
    """
    Orchestrate multiple agent tasks in parallel.
    
    Example:
        orch = Orchestrator()
        tasks = [
            {"label": "task-1", "task": "Do thing 1", "timeout": 300},
            {"label": "task-2", "task": "Do thing 2", "timeout": 300},
        ]
        results = orch.run_parallel(tasks)
    """
    
    def __init__(self, 
                 max_workers: int = 5,
                 poll_interval: float = 5.0,
                 outputs_dir: Optional[Path] = None,
                 metrics_log: Optional[Path] = None):
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.outputs_dir = outputs_dir or OUTPUTS_DIR
        self.metrics_log = metrics_log or METRICS_LOG
        
        # Ensure directories exist
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_log.parent.mkdir(parents=True, exist_ok=True)
    
    def _find_recent_session(self, label: str, since_timestamp: float) -> Optional[str]:
        """Find a session created after the given timestamp with matching label."""
        if not SESSIONS_DIR.exists():
            return None
            
        for session_file in SESSIONS_DIR.glob("*.jsonl"):
            if session_file.suffix == ".lock":
                continue
            if ".deleted" in session_file.name:
                continue
                
            # Check creation time
            try:
                stat = session_file.stat()
                if stat.st_ctime < since_timestamp:
                    continue
                    
                # Read first few lines to check for our label
                with open(session_file, 'r') as f:
                    for i, line in enumerate(f):
                        if i > 10:  # Only check first 10 lines
                            break
                        try:
                            msg = json.loads(line)
                            # Check if this session has our task label
                            if msg.get("type") == "message":
                                inner = msg.get("message", {})
                                content = inner.get("content", [])
                                for part in content:
                                    if part.get("type") == "text":
                                        if label in part.get("text", ""):
                                            return session_file.stem
                        except:
                            pass
            except:
                pass
        
        return None
    
    def spawn_agent(self, task: TaskDefinition) -> Optional[str]:
        """
        Spawn a new agent for the given task.
        
        Returns the session ID if successful, None otherwise.
        
        Note: This attempts to use the OpenClaw CLI or gateway API.
        If neither is available, returns None and the task should be
        run manually.
        """
        before_spawn = time.time()
        
        # Try to spawn via subprocess if openclaw binary exists
        # First check common locations
        openclaw_paths = [
            "/usr/local/bin/openclaw",
            "/root/.openclaw/bin/openclaw",
            "openclaw"
        ]
        
        openclaw_bin = None
        for path in openclaw_paths:
            try:
                result = subprocess.run(
                    ["which", path] if "/" not in path else ["test", "-f", path],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    openclaw_bin = path
                    break
            except:
                pass
        
        if openclaw_bin:
            # Build the prompt with status protocol
            prompt = f"""[Task Label: {task.label}]

{task.task}

**STATUS PROTOCOL** - Use these markers:
- [STATUS:STARTING] when you begin
- [STATUS:PROGRESS] for milestones
- [STATUS:BLOCKER] if you need help  
- [STATUS:COMPLETE] when done

Begin now."""
            
            if task.context:
                prompt = f"{task.context}\n\n{prompt}"
            
            try:
                # Spawn as a background subagent
                cmd = [
                    openclaw_bin, "agent", "spawn",
                    "--label", task.label,
                    "--message", prompt
                ]
                
                if task.model:
                    cmd.extend(["--model", task.model])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    # Try to extract session ID from output
                    output = result.stdout
                    # Look for UUID pattern
                    match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', output)
                    if match:
                        return match.group(0)
                    
                    # Otherwise try to find the new session
                    time.sleep(1)
                    return self._find_recent_session(task.label, before_spawn)
            except Exception as e:
                pass
        
        # If CLI spawn didn't work, try writing a task file that the main agent can pick up
        task_file = self.outputs_dir / f"pending_tasks/{task.label}.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        with open(task_file, 'w') as f:
            json.dump({
                "label": task.label,
                "task": task.task,
                "timeout": task.timeout,
                "model": task.model,
                "context": task.context,
                "created_at": datetime.now().isoformat()
            }, f, indent=2)
        
        return None  # No session ID - task needs manual pickup
    
    def monitor_agent(self, session_id: str, task: TaskDefinition) -> AgentResult:
        """Monitor an agent until completion or timeout."""
        start_time = time.time()
        monitor = SessionMonitor(session_id)
        
        result = AgentResult(
            label=task.label,
            status="running",
            session_id=session_id,
            start_time=start_time
        )
        
        deadline = start_time + task.timeout
        
        while time.time() < deadline:
            if not monitor.exists():
                time.sleep(self.poll_interval)
                continue
            
            messages = monitor.get_all_messages()
            complete, progress = monitor.check_completion(messages)
            result.progress_updates.extend(progress)
            
            if complete:
                result.status = "complete"
                result.end_time = time.time()
                result.runtime_seconds = result.end_time - start_time
                
                # Extract content
                content = monitor.extract_assistant_content(messages)
                result.output_content = content
                
                # Save to file
                output_path = self.outputs_dir / f"{task.label}.md"
                with open(output_path, 'w') as f:
                    f.write(f"# {task.label}\n\n")
                    f.write(f"*Completed at: {datetime.now().isoformat()}*\n")
                    f.write(f"*Runtime: {result.runtime_seconds:.1f}s*\n\n")
                    f.write(content)
                result.output_path = str(output_path)
                
                # Extract metrics
                metrics = monitor.extract_metrics(messages)
                result.tokens_input = metrics["tokens_input"]
                result.tokens_output = metrics["tokens_output"]
                result.tokens_total = metrics["tokens_total"]
                result.cost_usd = metrics["cost_usd"]
                
                break
            
            time.sleep(self.poll_interval)
        else:
            # Timeout
            result.status = "timeout"
            result.end_time = time.time()
            result.runtime_seconds = result.end_time - start_time
            
            # Still capture partial results
            messages = monitor.get_all_messages()
            content = monitor.extract_assistant_content(messages)
            result.output_content = content
            
            if content:
                output_path = self.outputs_dir / f"{task.label}_partial.md"
                with open(output_path, 'w') as f:
                    f.write(f"# {task.label} (PARTIAL - Timeout)\n\n")
                    f.write(f"*Timed out at: {datetime.now().isoformat()}*\n")
                    f.write(f"*Runtime: {result.runtime_seconds:.1f}s*\n\n")
                    f.write(content)
                result.output_path = str(output_path)
            
            metrics = monitor.extract_metrics(messages)
            result.tokens_input = metrics["tokens_input"]
            result.tokens_output = metrics["tokens_output"]
            result.tokens_total = metrics["tokens_total"]
            result.cost_usd = metrics["cost_usd"]
        
        return result
    
    def run_single(self, task_def: dict) -> AgentResult:
        """Run a single task and return result."""
        task = TaskDefinition(
            label=task_def["label"],
            task=task_def["task"],
            timeout=task_def.get("timeout", 300),
            model=task_def.get("model"),
            output_file=task_def.get("output_file"),
            context=task_def.get("context")
        )
        
        start_time = time.time()
        
        # Try to spawn agent
        session_id = self.spawn_agent(task)
        
        if session_id:
            result = self.monitor_agent(session_id, task)
        else:
            # No session - create a placeholder result
            result = AgentResult(
                label=task.label,
                status="pending",
                start_time=start_time,
                end_time=time.time(),
                runtime_seconds=time.time() - start_time,
                error="Could not spawn agent - task saved to pending_tasks/"
            )
        
        # Log metrics
        self._log_metrics(result)
        
        return result
    
    def run_parallel(self, tasks: List[dict]) -> Dict[str, dict]:
        """
        Run multiple tasks in parallel.
        
        Args:
            tasks: List of task definitions, each with:
                - label: Unique identifier for the task
                - task: The task description/prompt
                - timeout: Max seconds to wait (default 300)
                - model: Optional model override
                - context: Optional additional context
        
        Returns:
            Dict mapping label to result dict with:
                - status: "complete", "timeout", "error", or "pending"
                - output_path: Path to output file if any
                - runtime: Seconds taken
                - tokens: Total tokens used
                - cost: USD cost
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_label = {
                executor.submit(self.run_single, task): task["label"]
                for task in tasks
            }
            
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    result = future.result()
                    results[label] = {
                        "status": result.status,
                        "output_path": result.output_path,
                        "runtime": result.runtime_seconds,
                        "tokens": result.tokens_total,
                        "cost": result.cost_usd,
                        "progress": result.progress_updates,
                        "error": result.error
                    }
                except Exception as e:
                    results[label] = {
                        "status": "error",
                        "error": str(e),
                        "output_path": None,
                        "runtime": 0,
                        "tokens": 0,
                        "cost": 0
                    }
        
        # Log aggregated summary
        self._log_summary(tasks, results)
        
        return results
    
    def _log_metrics(self, result: AgentResult):
        """Log metrics for a single task."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "label": result.label,
            "status": result.status,
            "session_id": result.session_id,
            "runtime_seconds": result.runtime_seconds,
            "tokens_input": result.tokens_input,
            "tokens_output": result.tokens_output,
            "tokens_total": result.tokens_total,
            "cost_usd": result.cost_usd,
            "error": result.error
        }
        
        with open(self.metrics_log, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    
    def _log_summary(self, tasks: List[dict], results: Dict[str, dict]):
        """Log summary of parallel run."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "type": "parallel_run_summary",
            "task_count": len(tasks),
            "completed": sum(1 for r in results.values() if r["status"] == "complete"),
            "timeouts": sum(1 for r in results.values() if r["status"] == "timeout"),
            "errors": sum(1 for r in results.values() if r["status"] == "error"),
            "pending": sum(1 for r in results.values() if r["status"] == "pending"),
            "total_runtime": sum(r.get("runtime", 0) for r in results.values()),
            "total_tokens": sum(r.get("tokens", 0) for r in results.values()),
            "total_cost_usd": sum(r.get("cost", 0) for r in results.values()),
            "labels": list(results.keys())
        }
        
        with open(self.metrics_log, 'a') as f:
            f.write(json.dumps(summary) + "\n")


def poll_existing_sessions(labels: List[str], timeout: int = 300) -> Dict[str, AgentResult]:
    """
    Poll existing sessions by label until they complete.
    
    Use this when you've already spawned agents and want to monitor them.
    
    Args:
        labels: List of task labels to look for
        timeout: Max seconds to wait for each
    
    Returns:
        Dict mapping label to AgentResult
    """
    results = {}
    
    for label in labels:
        # Find session with this label
        session_id = None
        if SESSIONS_DIR.exists():
            for session_file in SESSIONS_DIR.glob("*.jsonl"):
                if ".deleted" in session_file.name or session_file.suffix == ".lock":
                    continue
                try:
                    with open(session_file, 'r') as f:
                        content = f.read(50000)  # First 50KB
                        if label in content:
                            session_id = session_file.stem
                            break
                except:
                    pass
        
        if session_id:
            task = TaskDefinition(label=label, task="", timeout=timeout)
            orch = Orchestrator()
            result = orch.monitor_agent(session_id, task)
        else:
            result = AgentResult(
                label=label,
                status="not_found",
                error=f"No session found for label: {label}"
            )
        
        results[label] = result
    
    return results


# Convenience functions for ATLAS

def spawn_research_agents(topics: List[str], timeout: int = 300) -> Dict[str, dict]:
    """
    Quick helper to spawn multiple research agents.
    
    Example:
        results = spawn_research_agents([
            "Latest trends in quantum computing",
            "Multi-agent AI systems best practices"
        ])
    """
    orch = Orchestrator()
    tasks = [
        {
            "label": f"research-{i}",
            "task": f"""Research the following topic and write a comprehensive summary:

{topic}

Use the Perplexity research tool:
```bash
python /workspace/clawd/tools/research.py "{topic}" --detailed
```

Synthesize the findings into a clear, actionable summary.""",
            "timeout": timeout
        }
        for i, topic in enumerate(topics)
    ]
    return orch.run_parallel(tasks)


def aggregate_results(results: Dict[str, dict]) -> str:
    """
    Aggregate multiple agent results into a single summary.
    
    Returns markdown-formatted combined output.
    """
    lines = ["# Aggregated Results\n"]
    lines.append(f"*Generated: {datetime.now().isoformat()}*\n")
    
    # Stats
    complete = sum(1 for r in results.values() if r["status"] == "complete")
    total = len(results)
    total_tokens = sum(r.get("tokens", 0) for r in results.values())
    total_cost = sum(r.get("cost", 0) for r in results.values())
    
    lines.append(f"**Stats**: {complete}/{total} complete | {total_tokens:,} tokens | ${total_cost:.4f}\n")
    lines.append("---\n")
    
    for label, result in results.items():
        lines.append(f"## {label}\n")
        lines.append(f"**Status**: {result['status']}\n")
        
        if result.get("output_path"):
            try:
                with open(result["output_path"], 'r') as f:
                    content = f.read()
                    # Skip the header we added
                    if "---" in content:
                        content = content.split("---", 1)[-1]
                    lines.append(content)
            except:
                lines.append(f"*Output at: {result['output_path']}*\n")
        elif result.get("error"):
            lines.append(f"**Error**: {result['error']}\n")
        
        lines.append("\n---\n")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Demo/test
    print("ATLAS Orchestrator - Test Mode")
    print("=" * 50)
    
    # Test basic functionality
    orch = Orchestrator()
    
    # List any active sessions
    if SESSIONS_DIR.exists():
        sessions = list(SESSIONS_DIR.glob("*.jsonl"))
        active = [s for s in sessions if ".deleted" not in s.name and s.suffix != ".lock"]
        print(f"Found {len(active)} active sessions")
        
        # Show most recent
        if active:
            recent = max(active, key=lambda p: p.stat().st_mtime)
            print(f"Most recent: {recent.stem}")
            
            monitor = SessionMonitor(recent.stem)
            messages = monitor.get_all_messages()
            metrics = monitor.extract_metrics(messages)
            print(f"  Tokens: {metrics['tokens_total']:,}")
            print(f"  Cost: ${metrics['cost_usd']:.4f}")
    else:
        print("Sessions directory not found")
    
    print("\nOrchestrator ready for use.")
    print("Import with: from orchestrate import Orchestrator")
