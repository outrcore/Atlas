#!/usr/bin/env python3
"""
Fireworks Orchestrator - Cheap parallel sub-agent execution via Kimi K2.5

Uses Fireworks.ai API for sub-agent tasks instead of spawning full Claude agents.
~1000x cheaper than Claude Sonnet for simple tasks.

Usage:
    from fireworks_orchestrator import FireworksOrchestrator
    
    orch = FireworksOrchestrator()
    
    # Single task
    result = orch.run_task("Research the history of Python programming")
    
    # Parallel tasks
    tasks = [
        {"label": "task1", "prompt": "Summarize X"},
        {"label": "task2", "prompt": "Analyze Y"},
    ]
    results = orch.run_parallel(tasks, max_workers=5)
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from fireworks_client import FireworksClient


@dataclass
class TaskResult:
    """Result from a single task."""
    label: str
    status: str  # "complete", "error"
    response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    runtime_seconds: float = 0.0
    error: Optional[str] = None


class FireworksOrchestrator:
    """Orchestrate parallel tasks via Fireworks.ai Kimi K2.5"""
    
    def __init__(
        self,
        model: str = "kimi-k2.5",
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ):
        self.client = FireworksClient(model=model)
        self.system_prompt = system_prompt or "You are a helpful AI assistant. Be concise and accurate."
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Results storage
        self.results: List[TaskResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def run_task(self, prompt: str, label: str = "task") -> TaskResult:
        """Run a single task and return result."""
        start = time.time()
        
        try:
            response = self.client.chat(
                prompt=prompt,
                system=self.system_prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            
            # Get last usage stats (approximation for this request)
            stats = self.client.get_usage_stats()
            
            result = TaskResult(
                label=label,
                status="complete",
                response=response,
                input_tokens=stats.get("total_input_tokens", 0),
                output_tokens=stats.get("total_output_tokens", 0),
                cost_usd=stats.get("estimated_cost_usd", 0),
                runtime_seconds=time.time() - start,
            )
            
        except Exception as e:
            result = TaskResult(
                label=label,
                status="error",
                error=str(e),
                runtime_seconds=time.time() - start,
            )
        
        return result
    
    def run_parallel(
        self,
        tasks: List[Dict[str, str]],
        max_workers: int = 5,
        progress_callback: Optional[callable] = None,
    ) -> List[TaskResult]:
        """
        Run multiple tasks in parallel.
        
        Args:
            tasks: List of {"label": "name", "prompt": "task description"}
            max_workers: Max concurrent tasks
            progress_callback: Called with (completed, total, result) after each task
        
        Returns:
            List of TaskResult objects
        """
        self.start_time = time.time()
        self.results = []
        
        def run_one(task: Dict[str, str]) -> TaskResult:
            label = task.get("label", f"task-{len(self.results)}")
            prompt = task.get("prompt", task.get("task", ""))
            return self.run_task(prompt, label)
        
        completed = 0
        total = len(tasks)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_one, task): task for task in tasks}
            
            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, total, result)
        
        self.end_time = time.time()
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all executed tasks."""
        if not self.results:
            return {"status": "no tasks run"}
        
        total_input = sum(r.input_tokens for r in self.results)
        total_output = sum(r.output_tokens for r in self.results)
        total_cost = sum(r.cost_usd for r in self.results)
        successes = sum(1 for r in self.results if r.status == "complete")
        
        return {
            "total_tasks": len(self.results),
            "successful": successes,
            "failed": len(self.results) - successes,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": round(total_cost, 6),
            "total_runtime_seconds": round(self.end_time - self.start_time, 2) if self.end_time else 0,
            "avg_runtime_per_task": round(sum(r.runtime_seconds for r in self.results) / len(self.results), 2),
        }
    
    def save_results(self, output_path: str = None) -> str:
        """Save results to JSON file."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/workspace/clawd/outputs/fireworks_run_{timestamp}.json"
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "summary": self.get_summary(),
            "results": [asdict(r) for r in self.results],
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        return output_path


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python fireworks_orchestrator.py 'task1' 'task2' 'task3' ...")
        print("       python fireworks_orchestrator.py --demo")
        sys.exit(1)
    
    if sys.argv[1] == "--demo":
        # Demo with sample tasks
        tasks = [
            {"label": "capitals", "prompt": "List 5 European capitals, one per line"},
            {"label": "math", "prompt": "What is 17 * 23? Just the number."},
            {"label": "code", "prompt": "Write a Python one-liner to reverse a string"},
        ]
    else:
        tasks = [{"label": f"task{i}", "prompt": arg} for i, arg in enumerate(sys.argv[1:])]
    
    print(f"Running {len(tasks)} tasks in parallel...\n")
    
    orch = FireworksOrchestrator()
    
    def on_progress(completed, total, result):
        status = "✓" if result.status == "complete" else "✗"
        print(f"[{completed}/{total}] {status} {result.label}: {result.response[:50]}...")
    
    results = orch.run_parallel(tasks, max_workers=3, progress_callback=on_progress)
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    for k, v in orch.get_summary().items():
        print(f"  {k}: {v}")
    
    output_file = orch.save_results()
    print(f"\nResults saved to: {output_file}")
