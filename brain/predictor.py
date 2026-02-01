"""
Intent Predictor - Predicts what the user might need next.

Uses Claude to analyze recent activity patterns and predict intent.
"""
import os
import json
from typing import Optional, Dict, List, Any
from datetime import datetime

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


PREDICTION_PROMPT = """You are a proactive AI assistant analyzing user activity patterns to predict what they might need next.

<recent_activities>
{activities}
</recent_activities>

<context>
{context}
</context>

Based on this activity pattern, predict:

1. **Immediate Needs**: What might the user need in the next few hours?
2. **Upcoming Tasks**: What tasks or projects seem to be in progress?
3. **Potential Blockers**: Any issues or blockers you notice?
4. **Proactive Suggestions**: What could you prepare or do proactively?
5. **Patterns Noticed**: Any behavioral patterns worth noting?

Consider:
- Time patterns (is it morning? end of day?)
- Project momentum (what's being actively worked on?)
- Incomplete items (anything left hanging?)
- Recurring themes (what keeps coming up?)

Respond in JSON:
```json
{{
  "immediate_needs": [
    {{"need": "description", "confidence": 0.8, "reasoning": "why"}}
  ],
  "upcoming_tasks": [
    {{"task": "description", "priority": "high/medium/low"}}
  ],
  "potential_blockers": [
    {{"blocker": "description", "suggestion": "how to address"}}
  ],
  "proactive_suggestions": [
    {{"suggestion": "what to do", "benefit": "why it helps"}}
  ],
  "patterns": ["pattern1", "pattern2"],
  "overall_context": "Brief summary of what's happening"
}}
```"""


class IntentPredictor:
    """
    Predicts user intent and needs based on activity patterns.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = None
        
        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            
    async def predict(
        self,
        activities: List[Dict],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Predict user intent based on recent activities.
        
        Args:
            activities: List of recent activities
            context: Additional context (recent memories, etc.)
            
        Returns:
            Prediction dict with needs, tasks, suggestions, etc.
        """
        if not self.client:
            return self._empty_prediction("No API client available")
            
        # Format activities for prompt
        activities_text = self._format_activities(activities)
        context_text = context or "No additional context available."
        
        prompt = PREDICTION_PROMPT.format(
            activities=activities_text,
            context=context_text,
        )
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",  # Sonnet for analysis
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            
            text = response.content[0].text
            
            # Parse JSON
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            else:
                json_str = text
                
            result = json.loads(json_str.strip())
            result["_predicted_at"] = datetime.now().isoformat()
            result["_activity_count"] = len(activities)
            result["_success"] = True
            
            return result
            
        except json.JSONDecodeError as e:
            return self._empty_prediction(f"JSON parse error: {e}")
        except Exception as e:
            return self._empty_prediction(f"Prediction error: {e}")
            
    def _format_activities(self, activities: List[Dict]) -> str:
        """Format activities for the prompt."""
        if not activities:
            return "No recent activities recorded."
            
        lines = []
        for a in activities[-50:]:  # Last 50 activities max
            ts = a.get("timestamp", "")[:16].replace("T", " ")
            atype = a.get("type", "unknown").upper()
            content = a.get("content", "")[:300]  # Truncate
            
            lines.append(f"[{ts}] {atype}: {content}")
            
        return "\n".join(lines)
        
    def _empty_prediction(self, reason: str) -> Dict[str, Any]:
        """Return empty prediction result."""
        return {
            "immediate_needs": [],
            "upcoming_tasks": [],
            "potential_blockers": [],
            "proactive_suggestions": [],
            "patterns": [],
            "overall_context": "Unable to generate prediction",
            "_success": False,
            "_error": reason,
            "_predicted_at": datetime.now().isoformat(),
        }
        
    async def quick_predict(
        self,
        current_query: str,
        recent_topics: List[str],
    ) -> List[str]:
        """
        Quick prediction of what the user might ask next.
        
        Args:
            current_query: Current user query
            recent_topics: Recent topics discussed
            
        Returns:
            List of likely follow-up queries
        """
        if not self.client:
            return []
            
        prompt = f"""Based on the current query and recent topics, predict 3-5 likely follow-up questions.

Current query: {current_query}
Recent topics: {', '.join(recent_topics)}

Return as JSON array of strings:
["likely question 1", "likely question 2", ...]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            
            text = response.content[0].text
            
            # Parse JSON array
            if "[" in text:
                json_str = text[text.index("["):text.rindex("]")+1]
                return json.loads(json_str)
                
            return []
            
        except Exception:
            return []
