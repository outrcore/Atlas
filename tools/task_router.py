#!/usr/bin/env python3
"""
Task Router - Intelligently route tasks to Kimi (cheap) or Claude (powerful)

Usage:
    from task_router import TaskRouter
    
    router = TaskRouter()
    
    # Auto-route based on task complexity
    result = router.run("Write a simple REST endpoint for user registration")
    
    # Force a specific backend
    result = router.run("Debug this complex race condition", backend="claude")
    result = router.run("Format this JSON data", backend="kimi")
    
    # Parallel tasks (always uses Kimi for cost efficiency)
    results = router.run_parallel([
        {"label": "task1", "prompt": "Write function A"},
        {"label": "task2", "prompt": "Write function B"},
    ])
"""

import os
import json
import re
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass

# Import our existing clients
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fireworks_client import FireworksClient
from fireworks_orchestrator import FireworksOrchestrator


@dataclass
class TaskResult:
    """Result from a routed task."""
    backend: str  # "kimi" or "claude"
    response: str
    cost_usd: float
    reasoning: str  # Why this backend was chosen


class TaskRouter:
    """Route tasks to the appropriate backend based on complexity."""
    
    # Keywords that suggest a task needs Claude's power
    COMPLEX_INDICATORS = [
        # Debugging/reasoning
        "debug", "diagnose", "investigate", "trace", "race condition",
        "memory leak", "performance issue", "optimize",
        # Architecture
        "architect", "design system", "refactor entire", "restructure",
        "migration strategy", "scalability",
        # Complex analysis
        "analyze codebase", "security audit", "review architecture",
        "evaluate tradeoffs", "complex logic",
        # Multi-step reasoning
        "step by step", "think through", "explain why", "reason about",
        # Integration work
        "integrate with", "coordinate between", "orchestrate",
    ]
    
    # Keywords that suggest Kimi can handle it
    SIMPLE_INDICATORS = [
        # Basic CRUD
        "write endpoint", "create function", "add route", "implement method",
        "write test", "add validation",
        # Formatting/transformation
        "format", "convert", "transform", "parse", "serialize",
        "generate", "template",
        # Simple fixes
        "fix typo", "rename", "update", "change", "modify",
        "add field", "remove",
        # Documentation
        "document", "add comments", "write readme", "jsdoc",
        # Boilerplate
        "boilerplate", "scaffold", "skeleton", "stub",
    ]
    
    def __init__(self):
        self.kimi = FireworksClient()
        self.orchestrator = FireworksOrchestrator()
        
    def _estimate_complexity(self, task: str) -> tuple[str, str]:
        """
        Estimate task complexity and return (backend, reasoning).
        
        Returns:
            ("kimi", reason) or ("claude", reason)
        """
        task_lower = task.lower()
        
        # Check for complex indicators
        for indicator in self.COMPLEX_INDICATORS:
            if indicator in task_lower:
                return ("claude", f"Complex task detected: '{indicator}'")
        
        # Check for simple indicators
        for indicator in self.SIMPLE_INDICATORS:
            if indicator in task_lower:
                return ("kimi", f"Simple task detected: '{indicator}'")
        
        # Length heuristic - very long prompts often need more reasoning
        if len(task) > 2000:
            return ("claude", "Long/detailed task - needs careful reasoning")
        
        # Check for code context size
        code_blocks = re.findall(r'```[\s\S]*?```', task)
        total_code_lines = sum(len(block.split('\n')) for block in code_blocks)
        if total_code_lines > 200:
            return ("claude", f"Large code context ({total_code_lines} lines)")
        
        # Default to Kimi for cost efficiency
        return ("kimi", "Default: no complexity indicators found")
    
    def run(
        self, 
        task: str, 
        backend: Optional[Literal["kimi", "claude"]] = None,
        max_tokens: int = 4000,
        system_prompt: Optional[str] = None
    ) -> TaskResult:
        """
        Run a task, routing to appropriate backend.
        
        Args:
            task: The task/prompt to execute
            backend: Force "kimi" or "claude", or None for auto-routing
            max_tokens: Max response tokens
            system_prompt: Optional system prompt
            
        Returns:
            TaskResult with response, cost, and routing reasoning
        """
        if backend:
            chosen = backend
            reasoning = f"Forced backend: {backend}"
        else:
            chosen, reasoning = self._estimate_complexity(task)
        
        if chosen == "kimi":
            # Use Kimi via Fireworks
            response = self.kimi.chat(
                task, 
                max_tokens=max_tokens,
                system=system_prompt
            )
            # Estimate cost: $0.10/1M input, $0.30/1M output
            input_tokens = getattr(self.kimi, 'total_input_tokens', 0)
            output_tokens = getattr(self.kimi, 'total_output_tokens', 0)
            cost = (input_tokens * 0.10 + output_tokens * 0.30) / 1_000_000
        else:
            # For Claude, we return a marker - actual Claude call happens via sessions_spawn
            # This is because Claude access is through OpenClaw, not direct API
            response = f"[ROUTE_TO_CLAUDE]\nTask requires Claude. Use sessions_spawn or handle directly.\n\nTask: {task}"
            cost = 0  # Cost tracked by OpenClaw
            reasoning += " (Use sessions_spawn for Claude)"
        
        return TaskResult(
            backend=chosen,
            response=response,
            cost_usd=cost,
            reasoning=reasoning
        )
    
    def run_parallel(
        self, 
        tasks: List[Dict[str, str]], 
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Run multiple tasks in parallel using Kimi (always, for cost efficiency).
        
        Args:
            tasks: List of {"label": "...", "prompt": "..."}
            max_workers: Max concurrent tasks
            
        Returns:
            List of task results
        """
        return self.orchestrator.run_parallel(tasks, max_workers=max_workers)
    
    def estimate(self, task: str) -> Dict[str, Any]:
        """
        Estimate which backend would be used without running the task.
        
        Returns:
            {"backend": "kimi"|"claude", "reasoning": "..."}
        """
        backend, reasoning = self._estimate_complexity(task)
        return {"backend": backend, "reasoning": reasoning}


def main():
    """CLI interface for task router."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Route tasks to Kimi or Claude")
    parser.add_argument("task", nargs="?", help="Task to run")
    parser.add_argument("--backend", "-b", choices=["kimi", "claude"], help="Force backend")
    parser.add_argument("--estimate", "-e", action="store_true", help="Just estimate, don't run")
    parser.add_argument("--system", "-s", help="System prompt")
    
    args = parser.parse_args()
    
    if not args.task:
        # Interactive mode
        print("Task Router - Enter task (or 'quit' to exit):")
        while True:
            try:
                task = input("\n> ").strip()
                if task.lower() in ("quit", "exit", "q"):
                    break
                if not task:
                    continue
                    
                router = TaskRouter()
                if args.estimate:
                    result = router.estimate(task)
                    print(f"Backend: {result['backend']}")
                    print(f"Reasoning: {result['reasoning']}")
                else:
                    result = router.run(task, backend=args.backend, system_prompt=args.system)
                    print(f"\n[{result.backend.upper()}] (${result.cost_usd:.6f})")
                    print(f"Reasoning: {result.reasoning}\n")
                    print(result.response)
            except KeyboardInterrupt:
                break
    else:
        router = TaskRouter()
        if args.estimate:
            result = router.estimate(args.task)
            print(f"Backend: {result['backend']}")
            print(f"Reasoning: {result['reasoning']}")
        else:
            result = router.run(args.task, backend=args.backend, system_prompt=args.system)
            print(f"[{result.backend.upper()}] (${result.cost_usd:.6f})")
            print(f"Reasoning: {result.reasoning}\n")
            print(result.response)


if __name__ == "__main__":
    main()
