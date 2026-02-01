"""
ATLAS Self-Reflection Module
Enables ATLAS to reflect on outputs, decisions, and behaviors.

Built by ATLAS during autonomous improvement session.
2026-02-01
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class Reflection:
    """A single reflection entry."""
    id: str
    type: str  # "response", "decision", "behavior", "error"
    subject: str  # What's being reflected on
    context: Optional[str]
    reflection: str  # The actual reflection
    insights: List[str]
    improvements: List[str]
    confidence: float  # 0-1 confidence in the reflection
    created_at: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


class SelfReflector:
    """
    Self-reflection capabilities for ATLAS.
    
    Enables:
    - Reflecting on responses before sending
    - Analyzing decisions after the fact
    - Learning from mistakes
    - Continuous self-improvement
    """
    
    def __init__(
        self,
        workspace: str = "/workspace/clawd",
        model: str = "claude-sonnet-4-20250514",
    ):
        self.workspace = Path(workspace)
        self.reflections_dir = self.workspace / "brain_data" / "reflections"
        self.reflections_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = model
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None
    
    async def reflect_on_response(
        self,
        response: str,
        context: str,
        goal: Optional[str] = None,
    ) -> Reflection:
        """
        Reflect on a response before or after sending.
        
        Args:
            response: The response text
            context: The conversation context
            goal: What the response was trying to achieve
            
        Returns:
            Reflection with insights and improvements
        """
        return await self._reflect(
            type_="response",
            subject=response[:500],
            context=context,
            prompt=f"""Reflect on this response I'm about to send.

CONTEXT: {context[:1000]}

{f'GOAL: {goal}' if goal else ''}

RESPONSE:
{response}

Evaluate:
1. Does it achieve the goal?
2. Is the tone appropriate?
3. Is it clear and concise?
4. What could be improved?
5. Any potential issues?"""
        )
    
    async def reflect_on_decision(
        self,
        decision: str,
        options: List[str],
        reasoning: str,
        outcome: Optional[str] = None,
    ) -> Reflection:
        """
        Reflect on a decision that was made.
        
        Args:
            decision: What was decided
            options: What alternatives existed
            reasoning: Why this option was chosen
            outcome: What happened (if known)
            
        Returns:
            Reflection with analysis
        """
        options_str = "\n".join(f"- {opt}" for opt in options)
        
        return await self._reflect(
            type_="decision",
            subject=decision,
            context=f"Options: {options_str}\nReasoning: {reasoning}",
            prompt=f"""Reflect on this decision I made.

DECISION: {decision}

OPTIONS CONSIDERED:
{options_str}

REASONING: {reasoning}

{f'OUTCOME: {outcome}' if outcome else 'Outcome not yet known.'}

Evaluate:
1. Was the reasoning sound?
2. Were all options properly considered?
3. What biases might have influenced the decision?
4. What could be done differently next time?
5. What did I learn?"""
        )
    
    async def reflect_on_error(
        self,
        error: str,
        context: str,
        action_taken: str,
    ) -> Reflection:
        """
        Reflect on an error or mistake.
        
        Args:
            error: What went wrong
            context: When/where it happened
            action_taken: What was being attempted
            
        Returns:
            Reflection with lessons learned
        """
        return await self._reflect(
            type_="error",
            subject=error,
            context=context,
            prompt=f"""Reflect on this error I encountered.

ERROR: {error}

CONTEXT: {context}

ACTION ATTEMPTED: {action_taken}

Analyze:
1. What caused this error?
2. Could it have been prevented?
3. How should I handle similar situations?
4. What systemic changes would help?
5. What's the key lesson?"""
        )
    
    async def reflect_on_behavior(
        self,
        behavior: str,
        context: str,
        feedback: Optional[str] = None,
    ) -> Reflection:
        """
        Reflect on a pattern of behavior.
        
        Args:
            behavior: The behavior pattern
            context: When it occurs
            feedback: Any user feedback received
            
        Returns:
            Reflection with insights
        """
        return await self._reflect(
            type_="behavior",
            subject=behavior,
            context=context,
            prompt=f"""Reflect on this behavior pattern.

BEHAVIOR: {behavior}

CONTEXT: {context}

{f'USER FEEDBACK: {feedback}' if feedback else ''}

Consider:
1. Is this behavior helpful or harmful?
2. Why does this pattern occur?
3. Should it be changed?
4. How can I be more intentional about this?
5. What's the ideal behavior?"""
        )
    
    async def _reflect(
        self,
        type_: str,
        subject: str,
        context: str,
        prompt: str,
    ) -> Reflection:
        """Generate a reflection using Claude."""
        ref_id = f"ref_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        if not self.client:
            return Reflection(
                id=ref_id,
                type=type_,
                subject=subject,
                context=context,
                reflection="Self-reflection requires AI client",
                insights=[],
                improvements=[],
                confidence=0.0,
                created_at=datetime.now().isoformat(),
            )
        
        full_prompt = f"""{prompt}

Output as JSON:
{{
  "reflection": "Your overall reflection (2-3 sentences)",
  "insights": ["insight1", "insight2", "insight3"],
  "improvements": ["improvement1", "improvement2"],
  "confidence": 0.0-1.0  // How confident are you in this analysis?
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": full_prompt}]
            )
            
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text)
            
            reflection = Reflection(
                id=ref_id,
                type=type_,
                subject=subject,
                context=context,
                reflection=data.get("reflection", ""),
                insights=data.get("insights", []),
                improvements=data.get("improvements", []),
                confidence=data.get("confidence", 0.5),
                created_at=datetime.now().isoformat(),
            )
            
        except Exception as e:
            reflection = Reflection(
                id=ref_id,
                type=type_,
                subject=subject,
                context=context,
                reflection=f"Reflection failed: {e}",
                insights=[],
                improvements=[],
                confidence=0.0,
                created_at=datetime.now().isoformat(),
            )
        
        self._save_reflection(reflection)
        return reflection
    
    def _save_reflection(self, reflection: Reflection):
        """Save reflection to disk."""
        # Save to daily file
        date = datetime.now().strftime("%Y-%m-%d")
        daily_file = self.reflections_dir / f"{date}.jsonl"
        
        with open(daily_file, "a") as f:
            f.write(json.dumps(reflection.to_dict()) + "\n")
    
    def get_recent_reflections(
        self,
        days: int = 7,
        type_: Optional[str] = None,
    ) -> List[Reflection]:
        """Get recent reflections."""
        reflections = []
        
        for file in sorted(self.reflections_dir.glob("*.jsonl"), reverse=True)[:days]:
            try:
                for line in file.read_text().strip().split("\n"):
                    if line:
                        data = json.loads(line)
                        ref = Reflection(**data)
                        if type_ is None or ref.type == type_:
                            reflections.append(ref)
            except:
                pass
        
        return reflections
    
    def get_insights_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get a summary of recent insights and improvements."""
        reflections = self.get_recent_reflections(days)
        
        all_insights = []
        all_improvements = []
        
        for ref in reflections:
            all_insights.extend(ref.insights)
            all_improvements.extend(ref.improvements)
        
        # Count frequencies
        insight_counts = {}
        for insight in all_insights:
            key = insight[:50]  # Truncate for grouping
            insight_counts[key] = insight_counts.get(key, 0) + 1
        
        improvement_counts = {}
        for imp in all_improvements:
            key = imp[:50]
            improvement_counts[key] = improvement_counts.get(key, 0) + 1
        
        return {
            "period_days": days,
            "total_reflections": len(reflections),
            "by_type": {
                type_: len([r for r in reflections if r.type == type_])
                for type_ in ["response", "decision", "behavior", "error"]
            },
            "top_insights": sorted(
                insight_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "top_improvements": sorted(
                improvement_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "avg_confidence": sum(r.confidence for r in reflections) / max(1, len(reflections)),
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get reflector status."""
        recent = self.get_recent_reflections(7)
        return {
            "ai_available": self.client is not None,
            "reflections_dir": str(self.reflections_dir),
            "recent_count": len(recent),
            "model": self.model,
        }


# Convenience function for quick reflection
async def quick_reflect(
    subject: str,
    context: str = "",
    type_: str = "response",
) -> Reflection:
    """Quick reflection without instantiating the class."""
    reflector = SelfReflector()
    
    if type_ == "response":
        return await reflector.reflect_on_response(subject, context)
    elif type_ == "decision":
        return await reflector.reflect_on_decision(subject, [], context)
    elif type_ == "error":
        return await reflector.reflect_on_error(subject, context, "")
    else:
        return await reflector.reflect_on_behavior(subject, context)


if __name__ == "__main__":
    import asyncio
    
    async def test():
        reflector = SelfReflector()
        print(f"Status: {reflector.get_status()}")
        
        # Test reflection
        ref = await reflector.reflect_on_response(
            response="I'll help you with that task right away!",
            context="User asked for help with a coding project",
            goal="Be helpful and efficient",
        )
        
        print(f"\nReflection: {ref.reflection}")
        print(f"Insights: {ref.insights}")
        print(f"Improvements: {ref.improvements}")
        print(f"Confidence: {ref.confidence}")
    
    asyncio.run(test())
