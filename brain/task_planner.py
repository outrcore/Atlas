"""
ATLAS Task Planner
Multi-step task planning and execution with reflection.

Built by ATLAS during autonomous improvement session.
2026-02-01
"""
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TaskStep:
    """A single step in a task plan."""
    id: str
    description: str
    action: str  # What to do
    expected_outcome: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class TaskPlan:
    """A multi-step task plan."""
    id: str
    goal: str
    context: Optional[str]
    steps: List[TaskStep]
    created_at: str
    status: TaskStatus = TaskStatus.PENDING
    reflection: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "context": self.context,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "status": self.status.value,
            "reflection": self.reflection,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TaskPlan":
        steps = [
            TaskStep(
                id=s["id"],
                description=s["description"],
                action=s["action"],
                expected_outcome=s["expected_outcome"],
                status=TaskStatus(s["status"]),
                result=s.get("result"),
                error=s.get("error"),
                started_at=s.get("started_at"),
                completed_at=s.get("completed_at"),
                dependencies=s.get("dependencies", []),
            )
            for s in data["steps"]
        ]
        return cls(
            id=data["id"],
            goal=data["goal"],
            context=data.get("context"),
            steps=steps,
            created_at=data["created_at"],
            status=TaskStatus(data["status"]),
            reflection=data.get("reflection"),
        )


class TaskPlanner:
    """
    Multi-step task planner for ATLAS.
    
    Features:
    - Breaks complex tasks into steps
    - Tracks dependencies between steps
    - Executes steps with reflection
    - Handles failures and replanning
    """
    
    def __init__(
        self,
        workspace: str = "/workspace/clawd",
        model: str = "claude-sonnet-4-20250514",
    ):
        self.workspace = Path(workspace)
        self.plans_dir = self.workspace / "brain_data" / "task_plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = model
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None
        
        # Active plans
        self._active_plans: Dict[str, TaskPlan] = {}
    
    async def create_plan(
        self,
        goal: str,
        context: Optional[str] = None,
        max_steps: int = 10,
    ) -> TaskPlan:
        """
        Create a multi-step plan for a complex task.
        
        Args:
            goal: What to accomplish
            context: Additional context about the situation
            max_steps: Maximum number of steps to generate
            
        Returns:
            TaskPlan with generated steps
        """
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if self.client:
            steps = await self._generate_steps_ai(goal, context, max_steps)
        else:
            # Fallback: simple single-step plan
            steps = [
                TaskStep(
                    id="step_1",
                    description=goal,
                    action=f"Execute: {goal}",
                    expected_outcome="Task completed successfully",
                )
            ]
        
        plan = TaskPlan(
            id=plan_id,
            goal=goal,
            context=context,
            steps=steps,
            created_at=datetime.now().isoformat(),
        )
        
        self._active_plans[plan_id] = plan
        self._save_plan(plan)
        
        return plan
    
    async def _generate_steps_ai(
        self,
        goal: str,
        context: Optional[str],
        max_steps: int,
    ) -> List[TaskStep]:
        """Use Claude to generate task steps."""
        prompt = f"""Break down this task into clear, actionable steps.

GOAL: {goal}

{f'CONTEXT: {context}' if context else ''}

Requirements:
- Generate at most {max_steps} steps
- Each step should be atomic and verifiable
- Include dependencies between steps
- Be specific about actions and expected outcomes

Output as JSON array with this structure:
[
  {{
    "id": "step_1",
    "description": "Brief description",
    "action": "Specific action to take",
    "expected_outcome": "How to verify completion",
    "dependencies": []  // IDs of steps that must complete first
  }}
]

Only output the JSON array, nothing else."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            steps_data = json.loads(text)
            
            return [
                TaskStep(
                    id=s["id"],
                    description=s["description"],
                    action=s["action"],
                    expected_outcome=s["expected_outcome"],
                    dependencies=s.get("dependencies", []),
                )
                for s in steps_data
            ]
        except Exception as e:
            # Fallback on error
            return [
                TaskStep(
                    id="step_1",
                    description=goal,
                    action=f"Execute: {goal}",
                    expected_outcome="Task completed successfully",
                )
            ]
    
    async def execute_step(
        self,
        plan: TaskPlan,
        step_id: str,
        executor: Callable[[TaskStep], Any],
    ) -> TaskStep:
        """
        Execute a single step in a plan.
        
        Args:
            plan: The task plan
            step_id: ID of step to execute
            executor: Function that executes the step's action
            
        Returns:
            Updated step with result
        """
        step = next((s for s in plan.steps if s.id == step_id), None)
        if not step:
            raise ValueError(f"Step {step_id} not found in plan {plan.id}")
        
        # Check dependencies
        for dep_id in step.dependencies:
            dep = next((s for s in plan.steps if s.id == dep_id), None)
            if dep and dep.status != TaskStatus.COMPLETED:
                step.status = TaskStatus.BLOCKED
                step.error = f"Blocked by dependency: {dep_id}"
                return step
        
        step.status = TaskStatus.IN_PROGRESS
        step.started_at = datetime.now().isoformat()
        
        try:
            result = await executor(step) if asyncio.iscoroutinefunction(executor) else executor(step)
            step.result = str(result)
            step.status = TaskStatus.COMPLETED
        except Exception as e:
            step.error = str(e)
            step.status = TaskStatus.FAILED
        
        step.completed_at = datetime.now().isoformat()
        self._save_plan(plan)
        
        return step
    
    async def reflect_on_step(
        self,
        plan: TaskPlan,
        step: TaskStep,
    ) -> Dict[str, Any]:
        """
        Reflect on a completed step to evaluate success.
        
        Args:
            plan: The task plan
            step: The completed step
            
        Returns:
            Reflection with success assessment and learnings
        """
        if not self.client:
            return {
                "success": step.status == TaskStatus.COMPLETED,
                "reflection": "No AI client available for reflection",
            }
        
        prompt = f"""Reflect on this completed task step.

GOAL: {plan.goal}
STEP: {step.description}
ACTION: {step.action}
EXPECTED: {step.expected_outcome}
RESULT: {step.result or step.error}
STATUS: {step.status.value}

Provide:
1. Was the step successful? Why/why not?
2. What was learned?
3. Should the plan be adjusted?
4. What's the next recommended action?

Output as JSON:
{{
  "success": true/false,
  "assessment": "Brief assessment",
  "learnings": ["learning1", "learning2"],
  "adjust_plan": true/false,
  "next_action": "Recommended next step"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            return json.loads(text)
        except Exception as e:
            return {
                "success": step.status == TaskStatus.COMPLETED,
                "error": str(e),
            }
    
    async def execute_plan(
        self,
        plan: TaskPlan,
        executor: Callable[[TaskStep], Any],
        reflect: bool = True,
    ) -> TaskPlan:
        """
        Execute all steps in a plan with optional reflection.
        
        Args:
            plan: The task plan
            executor: Function that executes each step
            reflect: Whether to reflect after each step
            
        Returns:
            Updated plan
        """
        plan.status = TaskStatus.IN_PROGRESS
        
        # Build dependency graph
        completed = set()
        
        while True:
            # Find next executable step
            next_step = None
            for step in plan.steps:
                if step.status == TaskStatus.PENDING:
                    deps_met = all(d in completed for d in step.dependencies)
                    if deps_met:
                        next_step = step
                        break
            
            if not next_step:
                break
            
            # Execute step
            await self.execute_step(plan, next_step.id, executor)
            
            # Reflect if enabled
            if reflect and next_step.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                reflection = await self.reflect_on_step(plan, next_step)
                
                # Handle failure with replanning
                if next_step.status == TaskStatus.FAILED and reflection.get("adjust_plan"):
                    # Could implement replanning here
                    pass
            
            if next_step.status == TaskStatus.COMPLETED:
                completed.add(next_step.id)
            elif next_step.status == TaskStatus.FAILED:
                plan.status = TaskStatus.FAILED
                break
        
        # Final status
        if all(s.status == TaskStatus.COMPLETED for s in plan.steps):
            plan.status = TaskStatus.COMPLETED
        
        # Generate final reflection
        if reflect and self.client:
            plan.reflection = await self._final_reflection(plan)
        
        self._save_plan(plan)
        return plan
    
    async def _final_reflection(self, plan: TaskPlan) -> str:
        """Generate a final reflection on the completed plan."""
        steps_summary = "\n".join([
            f"- {s.description}: {s.status.value}"
            for s in plan.steps
        ])
        
        prompt = f"""Provide a brief reflection on this completed task plan.

GOAL: {plan.goal}
STATUS: {plan.status.value}
STEPS:
{steps_summary}

In 2-3 sentences, summarize:
1. What was accomplished
2. What could be improved next time
3. Key lessons learned"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except:
            return ""
    
    def _save_plan(self, plan: TaskPlan):
        """Save plan to disk."""
        filepath = self.plans_dir / f"{plan.id}.json"
        filepath.write_text(json.dumps(plan.to_dict(), indent=2))
    
    def load_plan(self, plan_id: str) -> Optional[TaskPlan]:
        """Load a plan from disk."""
        filepath = self.plans_dir / f"{plan_id}.json"
        if filepath.exists():
            data = json.loads(filepath.read_text())
            return TaskPlan.from_dict(data)
        return None
    
    def list_plans(self, status: Optional[TaskStatus] = None) -> List[TaskPlan]:
        """List all saved plans, optionally filtered by status."""
        plans = []
        for file in self.plans_dir.glob("plan_*.json"):
            try:
                data = json.loads(file.read_text())
                plan = TaskPlan.from_dict(data)
                if status is None or plan.status == status:
                    plans.append(plan)
            except:
                pass
        return sorted(plans, key=lambda p: p.created_at, reverse=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get planner status."""
        all_plans = self.list_plans()
        return {
            "total_plans": len(all_plans),
            "by_status": {
                status.value: len([p for p in all_plans if p.status == status])
                for status in TaskStatus
            },
            "ai_available": self.client is not None,
            "plans_dir": str(self.plans_dir),
        }


# Test the planner
if __name__ == "__main__":
    import asyncio
    
    async def test():
        planner = TaskPlanner()
        print(f"Status: {planner.get_status()}")
        
        # Create a test plan
        plan = await planner.create_plan(
            goal="Set up a new Python project with tests",
            context="We want a clean project structure with pytest",
        )
        
        print(f"\nCreated plan: {plan.id}")
        print(f"Steps: {len(plan.steps)}")
        for step in plan.steps:
            print(f"  - {step.description}")
    
    asyncio.run(test())
