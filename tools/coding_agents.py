#!/usr/bin/env python3
"""
ATLAS Coding Agents - Tiered Routing System

Routes coding tasks to appropriate agents based on complexity:
- Simple tasks → Kimi K2.5 (cheap, fast)
- Complex tasks → Claude Sonnet (expensive, smart)
- Architecture/Review → ATLAS/Opus (you call this directly)

Usage:
    from coding_agents import CodingAgentRouter
    
    router = CodingAgentRouter()
    
    # Auto-route based on task complexity
    result = router.execute_task("Write a simple hello world function")
    
    # Force specific tier
    result = router.execute_task("Debug this complex async race condition", tier="complex")
    
    # Batch tasks with auto-routing
    tasks = [
        {"task": "Write unit tests for user.py", "context": "..."},
        {"task": "Refactor auth system", "context": "..."},
    ]
    results = router.execute_batch(tasks)
"""

import os
import json
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import our Fireworks client
from fireworks_client import FireworksClient

# For Sonnet, we'll use OpenClaw's sessions_spawn or direct API
import subprocess


@dataclass
class TaskResult:
    """Result from a coding task."""
    task: str
    tier: str  # "simple", "complex"
    agent: str  # "kimi-k2.5", "claude-sonnet"
    status: str  # "complete", "error", "needs_review"
    code: str = ""
    explanation: str = ""
    files_modified: List[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    runtime_seconds: float = 0.0
    error: Optional[str] = None
    review_notes: Optional[str] = None
    
    def __post_init__(self):
        if self.files_modified is None:
            self.files_modified = []


class TaskClassifier:
    """Classifies coding tasks into complexity tiers."""
    
    # Keywords that suggest simple tasks
    SIMPLE_KEYWORDS = [
        "boilerplate", "template", "simple", "basic", "crud",
        "getter", "setter", "constructor", "init", "__init__",
        "test", "unit test", "docstring", "comment", "documentation",
        "config", "configuration", "env", "environment",
        "import", "export", "type", "interface", "model",
        "create file", "add file", "new file",
        "hello world", "example", "sample",
        "format", "lint", "style", "rename",
    ]
    
    # Keywords that suggest complex tasks
    COMPLEX_KEYWORDS = [
        "debug", "fix bug", "race condition", "memory leak",
        "refactor", "redesign", "rewrite", "overhaul",
        "optimize", "performance", "bottleneck",
        "security", "vulnerability", "authentication", "authorization",
        "async", "concurrent", "parallel", "threading",
        "architecture", "design pattern", "abstraction",
        "migrate", "upgrade", "breaking change",
        "complex", "intricate", "sophisticated",
        "integrate", "third-party", "api integration",
        "algorithm", "data structure",
    ]
    
    @classmethod
    def classify(cls, task: str, context: str = "") -> str:
        """
        Classify a task as 'simple' or 'complex'.
        
        Returns:
            'simple' or 'complex'
        """
        combined = f"{task} {context}".lower()
        
        # Count keyword matches
        simple_score = sum(1 for kw in cls.SIMPLE_KEYWORDS if kw in combined)
        complex_score = sum(1 for kw in cls.COMPLEX_KEYWORDS if kw in combined)
        
        # Heuristics for complexity
        # Long tasks tend to be more complex
        if len(task) > 200:
            complex_score += 1
        
        # Multiple files = more complex
        file_mentions = len(re.findall(r'\b\w+\.(py|js|ts|jsx|tsx|go|rs)\b', combined))
        if file_mentions > 2:
            complex_score += 1
        
        # Default to simple if unclear (cheaper)
        if complex_score > simple_score:
            return "complex"
        return "simple"


class CodingAgentRouter:
    """Routes coding tasks to appropriate agents."""
    
    CODING_SYSTEM_PROMPT = """You are an expert software engineer. Your task is to write clean, working code.

Guidelines:
- Write production-quality code
- Include error handling
- Add brief comments for complex logic
- Follow the language's conventions and best practices
- If you need to modify existing code, show the changes clearly

Output format:
1. Brief explanation of approach (2-3 sentences max)
2. The code in a markdown code block
3. Any important notes about usage or dependencies

Be concise. Focus on working code."""

    def __init__(self):
        self.kimi_client = FireworksClient(model="kimi-k2.5")
        self.classifier = TaskClassifier()
        self.results: List[TaskResult] = []
        
        # Track costs
        self.total_kimi_cost = 0.0
        self.total_sonnet_cost = 0.0
    
    def execute_task(
        self,
        task: str,
        context: str = "",
        tier: Optional[Literal["simple", "complex"]] = None,
        file_contents: Dict[str, str] = None,
    ) -> TaskResult:
        """
        Execute a single coding task.
        
        Args:
            task: Description of what to build/fix
            context: Additional context (existing code, requirements, etc.)
            tier: Force 'simple' or 'complex', or None for auto-detect
            file_contents: Dict of {filename: content} for relevant files
        
        Returns:
            TaskResult with code and metadata
        """
        start_time = time.time()
        
        # Classify if not specified
        if tier is None:
            tier = self.classifier.classify(task, context)
        
        # Build the prompt
        prompt = self._build_prompt(task, context, file_contents)
        
        if tier == "simple":
            result = self._execute_kimi(task, prompt)
        else:
            result = self._execute_sonnet(task, prompt)
        
        result.runtime_seconds = time.time() - start_time
        result.tier = tier
        
        self.results.append(result)
        return result
    
    def execute_batch(
        self,
        tasks: List[Dict[str, Any]],
        max_parallel_simple: int = 5,
        max_parallel_complex: int = 2,
    ) -> List[TaskResult]:
        """
        Execute multiple tasks with intelligent routing.
        
        Args:
            tasks: List of {"task": str, "context": str, "tier": str (optional)}
            max_parallel_simple: Max concurrent Kimi tasks
            max_parallel_complex: Max concurrent Sonnet tasks
        
        Returns:
            List of TaskResult objects
        """
        # Classify and separate tasks
        simple_tasks = []
        complex_tasks = []
        
        for t in tasks:
            tier = t.get("tier") or self.classifier.classify(
                t.get("task", ""), 
                t.get("context", "")
            )
            t["_tier"] = tier
            
            if tier == "simple":
                simple_tasks.append(t)
            else:
                complex_tasks.append(t)
        
        print(f"Task breakdown: {len(simple_tasks)} simple, {len(complex_tasks)} complex")
        
        results = []
        
        # Run simple tasks in parallel (cheap, can parallelize more)
        if simple_tasks:
            print(f"Running {len(simple_tasks)} simple tasks via Kimi K2.5...")
            with ThreadPoolExecutor(max_workers=max_parallel_simple) as executor:
                futures = {
                    executor.submit(
                        self.execute_task,
                        t.get("task", ""),
                        t.get("context", ""),
                        "simple",
                        t.get("files"),
                    ): t for t in simple_tasks
                }
                for future in as_completed(futures):
                    results.append(future.result())
        
        # Run complex tasks with limited parallelism (expensive)
        if complex_tasks:
            print(f"Running {len(complex_tasks)} complex tasks via Claude Sonnet...")
            with ThreadPoolExecutor(max_workers=max_parallel_complex) as executor:
                futures = {
                    executor.submit(
                        self.execute_task,
                        t.get("task", ""),
                        t.get("context", ""),
                        "complex",
                        t.get("files"),
                    ): t for t in complex_tasks
                }
                for future in as_completed(futures):
                    results.append(future.result())
        
        return results
    
    def _build_prompt(
        self,
        task: str,
        context: str = "",
        file_contents: Dict[str, str] = None,
    ) -> str:
        """Build the full prompt for the agent."""
        parts = [f"## Task\n{task}"]
        
        if context:
            parts.append(f"\n## Context\n{context}")
        
        if file_contents:
            parts.append("\n## Existing Files")
            for filename, content in file_contents.items():
                # Truncate very long files
                if len(content) > 5000:
                    content = content[:5000] + "\n... (truncated)"
                parts.append(f"\n### {filename}\n```\n{content}\n```")
        
        return "\n".join(parts)
    
    def _execute_kimi(self, task: str, prompt: str) -> TaskResult:
        """Execute task via Kimi K2.5."""
        try:
            response = self.kimi_client.chat(
                prompt=prompt,
                system=self.CODING_SYSTEM_PROMPT,
                max_tokens=4096,
                temperature=0.3,  # Lower temp for code
            )
            
            stats = self.kimi_client.get_usage_stats()
            cost = stats.get("estimated_cost_usd", 0)
            self.total_kimi_cost = cost
            
            # Parse code from response
            code, explanation = self._parse_code_response(response)
            
            return TaskResult(
                task=task,
                tier="simple",
                agent="kimi-k2.5",
                status="complete",
                code=code,
                explanation=explanation,
                input_tokens=stats.get("total_input_tokens", 0),
                output_tokens=stats.get("total_output_tokens", 0),
                cost_usd=cost,
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                tier="simple",
                agent="kimi-k2.5",
                status="error",
                error=str(e),
            )
    
    def _execute_sonnet(self, task: str, prompt: str) -> TaskResult:
        """
        Execute task via Claude Sonnet.
        Uses OpenClaw sessions_spawn for proper integration.
        Falls back to direct API if needed.
        """
        try:
            # For now, use a simple subprocess call to the Anthropic API
            # In production, this would use sessions_spawn
            
            import anthropic
            
            # Try to get API key from environment
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                # Read from OpenClaw config or .env
                env_path = Path("/workspace/clawd/.env")
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        if line.startswith("ANTHROPIC_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
            
            if not api_key:
                # Fall back to Kimi for now
                print("Warning: No Anthropic API key, falling back to Kimi")
                result = self._execute_kimi(task, prompt)
                result.agent = "kimi-k2.5 (fallback)"
                result.tier = "complex"
                return result
            
            client = anthropic.Anthropic(api_key=api_key)
            
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=self.CODING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            
            content = response.content[0].text
            code, explanation = self._parse_code_response(content)
            
            # Calculate cost (Sonnet pricing: $3/1M input, $15/1M output)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = (input_tokens / 1_000_000) * 3 + (output_tokens / 1_000_000) * 15
            self.total_sonnet_cost += cost
            
            return TaskResult(
                task=task,
                tier="complex",
                agent="claude-sonnet",
                status="complete",
                code=code,
                explanation=explanation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                tier="complex",
                agent="claude-sonnet",
                status="error",
                error=str(e),
            )
    
    def _parse_code_response(self, response: str) -> tuple[str, str]:
        """Parse code blocks and explanation from response."""
        # Find code blocks
        code_pattern = r'```(?:\w+)?\n(.*?)```'
        code_blocks = re.findall(code_pattern, response, re.DOTALL)
        code = "\n\n".join(code_blocks) if code_blocks else ""
        
        # Everything before the first code block is explanation
        explanation = response.split("```")[0].strip() if "```" in response else response
        
        return code, explanation
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all executed tasks."""
        if not self.results:
            return {"status": "no tasks run"}
        
        simple_count = sum(1 for r in self.results if r.tier == "simple")
        complex_count = sum(1 for r in self.results if r.tier == "complex")
        success_count = sum(1 for r in self.results if r.status == "complete")
        
        return {
            "total_tasks": len(self.results),
            "simple_tasks": simple_count,
            "complex_tasks": complex_count,
            "successful": success_count,
            "failed": len(self.results) - success_count,
            "total_kimi_cost_usd": round(self.total_kimi_cost, 6),
            "total_sonnet_cost_usd": round(self.total_sonnet_cost, 4),
            "total_cost_usd": round(self.total_kimi_cost + self.total_sonnet_cost, 4),
            "estimated_savings": f"{round((1 - (self.total_kimi_cost + self.total_sonnet_cost) / max(0.001, complex_count * 0.02 + simple_count * 0.02)) * 100)}% vs all-Sonnet",
        }
    
    def review_result(self, result: TaskResult, notes: str, approved: bool) -> TaskResult:
        """Add review notes to a result."""
        result.review_notes = notes
        result.status = "complete" if approved else "needs_rework"
        return result


# CLI for testing
if __name__ == "__main__":
    import sys
    
    router = CodingAgentRouter()
    
    if len(sys.argv) < 2:
        print("Usage: python coding_agents.py 'task description'")
        print("       python coding_agents.py --classify 'task'")
        print("       python coding_agents.py --demo")
        sys.exit(1)
    
    if sys.argv[1] == "--classify":
        task = " ".join(sys.argv[2:])
        tier = TaskClassifier.classify(task)
        print(f"Task: {task}")
        print(f"Classification: {tier}")
    
    elif sys.argv[1] == "--demo":
        tasks = [
            {"task": "Write a simple Python function to validate an email address"},
            {"task": "Create unit tests for a user authentication module"},
            {"task": "Debug and fix a race condition in an async WebSocket handler"},
        ]
        
        print("Running demo tasks...\n")
        for t in tasks:
            tier = TaskClassifier.classify(t["task"])
            print(f"• {t['task'][:50]}... → {tier}")
        
        print("\nExecuting first task only (to save costs)...")
        result = router.execute_task(tasks[0]["task"])
        
        print(f"\nResult:")
        print(f"  Agent: {result.agent}")
        print(f"  Status: {result.status}")
        print(f"  Cost: ${result.cost_usd:.6f}")
        print(f"\nCode:\n{result.code[:500]}...")
    
    else:
        task = " ".join(sys.argv[1:])
        print(f"Executing: {task}\n")
        
        result = router.execute_task(task)
        
        print(f"Agent: {result.agent} ({result.tier})")
        print(f"Status: {result.status}")
        print(f"Cost: ${result.cost_usd:.6f}")
        print(f"\n{'-'*50}\n")
        print(result.explanation)
        print(f"\n{'-'*50}\n")
        print(result.code)
