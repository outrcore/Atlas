#!/usr/bin/env python3
"""
Agent Metrics Logger

Tracks agent performance: tasks, tokens, runtime, success rates.
Logs to /workspace/clawd/logs/agent_metrics.jsonl
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from collections import defaultdict

METRICS_FILE = Path("/workspace/clawd/logs/agent_metrics.jsonl")


def log_metric(
    task: str,
    tokens: int = 0,
    runtime_sec: float = 0.0,
    success: bool = True,
    agent_id: str = "main",
    metadata: Optional[dict] = None
) -> dict:
    """
    Log an agent metric entry.
    
    Args:
        task: Description of the task performed
        tokens: Number of tokens used (input + output)
        runtime_sec: Execution time in seconds
        success: Whether the task completed successfully
        agent_id: Identifier for the agent
        metadata: Optional additional data
    
    Returns:
        The logged metric entry
    """
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent_id": agent_id,
        "task": task,
        "tokens": tokens,
        "runtime_sec": round(runtime_sec, 2),
        "success": success,
    }
    
    if metadata:
        entry["metadata"] = metadata
    
    with open(METRICS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return entry


def read_metrics(
    since_hours: Optional[int] = None,
    agent_id: Optional[str] = None,
    limit: Optional[int] = None
) -> list[dict]:
    """
    Read metrics from the log file.
    
    Args:
        since_hours: Only return metrics from the last N hours
        agent_id: Filter by specific agent
        limit: Maximum number of entries to return (most recent)
    
    Returns:
        List of metric entries
    """
    if not METRICS_FILE.exists():
        return []
    
    entries = []
    cutoff = None
    if since_hours:
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)
    
    with open(METRICS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                
                # Filter by time
                if cutoff:
                    entry_time = datetime.fromisoformat(entry["timestamp"].rstrip("Z"))
                    if entry_time < cutoff:
                        continue
                
                # Filter by agent
                if agent_id and entry.get("agent_id") != agent_id:
                    continue
                
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    
    if limit:
        entries = entries[-limit:]
    
    return entries


def summarize_metrics(since_hours: int = 24) -> dict:
    """
    Generate a summary of agent metrics.
    
    Args:
        since_hours: Time window for summary (default 24h)
    
    Returns:
        Summary dict with stats per agent and totals
    """
    entries = read_metrics(since_hours=since_hours)
    
    if not entries:
        return {
            "period_hours": since_hours,
            "total_entries": 0,
            "message": "No metrics found"
        }
    
    # Aggregate by agent
    by_agent = defaultdict(lambda: {
        "tasks": 0,
        "tokens": 0,
        "runtime_sec": 0,
        "successes": 0,
        "failures": 0
    })
    
    for entry in entries:
        agent = entry.get("agent_id", "unknown")
        by_agent[agent]["tasks"] += 1
        by_agent[agent]["tokens"] += entry.get("tokens", 0)
        by_agent[agent]["runtime_sec"] += entry.get("runtime_sec", 0)
        if entry.get("success", True):
            by_agent[agent]["successes"] += 1
        else:
            by_agent[agent]["failures"] += 1
    
    # Calculate totals
    total_tasks = sum(a["tasks"] for a in by_agent.values())
    total_tokens = sum(a["tokens"] for a in by_agent.values())
    total_runtime = sum(a["runtime_sec"] for a in by_agent.values())
    total_successes = sum(a["successes"] for a in by_agent.values())
    
    # Convert defaultdict to regular dict and add success rate
    agents_summary = {}
    for agent, stats in by_agent.items():
        stats["success_rate"] = round(stats["successes"] / stats["tasks"] * 100, 1) if stats["tasks"] > 0 else 0
        agents_summary[agent] = dict(stats)
    
    return {
        "period_hours": since_hours,
        "total_entries": total_tasks,
        "total_tokens": total_tokens,
        "total_runtime_sec": round(total_runtime, 2),
        "overall_success_rate": round(total_successes / total_tasks * 100, 1) if total_tasks > 0 else 0,
        "by_agent": agents_summary
    }


def print_summary(since_hours: int = 24):
    """Print a human-readable summary to stdout."""
    summary = summarize_metrics(since_hours)
    
    print(f"\n=== Agent Metrics (last {since_hours}h) ===\n")
    
    if summary.get("total_entries", 0) == 0:
        print("No metrics recorded.")
        return
    
    print(f"Total tasks: {summary['total_entries']}")
    print(f"Total tokens: {summary['total_tokens']:,}")
    print(f"Total runtime: {summary['total_runtime_sec']:.1f}s")
    print(f"Success rate: {summary['overall_success_rate']}%")
    
    print("\nBy Agent:")
    for agent, stats in summary.get("by_agent", {}).items():
        print(f"  {agent}:")
        print(f"    Tasks: {stats['tasks']} ({stats['success_rate']}% success)")
        print(f"    Tokens: {stats['tokens']:,}")
        print(f"    Runtime: {stats['runtime_sec']:.1f}s")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        print_summary(hours)
    else:
        # Demo logging
        log_metric(
            task="infrastructure_setup",
            tokens=1500,
            runtime_sec=12.5,
            success=True,
            agent_id="subagent:infra"
        )
        print("Logged demo metric. Run 'python metrics.py summary' to view.")
