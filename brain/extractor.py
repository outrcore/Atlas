"""
Memory Extractor - Uses Claude to extract insights from conversations.
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


EXTRACTION_PROMPT = """Analyze this conversation and extract structured information.

<conversation>
{conversation}
</conversation>

{context_section}

Extract the following (return empty lists if nothing found):

1. **Facts**: Concrete facts learned (e.g., "Matt lives in Chicago", "Uses iCloud for email")
2. **Preferences**: User preferences discovered (e.g., "Prefers Fahrenheit", "Trying to quit Zyn")
3. **Decisions**: Decisions made during the conversation
4. **Action Items**: Things to do or follow up on
5. **Topics**: Main topics discussed (for categorization)
6. **Sentiment**: Overall sentiment (positive/neutral/negative)
7. **Key Entities**: People, projects, tools mentioned

Respond in JSON format:
```json
{{
  "facts": ["fact1", "fact2"],
  "preferences": ["pref1", "pref2"],
  "decisions": ["decision1"],
  "action_items": ["action1", "action2"],
  "topics": ["topic1", "topic2"],
  "sentiment": "positive",
  "key_entities": {{
    "people": ["name1"],
    "projects": ["project1"],
    "tools": ["tool1"]
  }},
  "summary": "One sentence summary of the conversation"
}}
```"""


class MemoryExtractor:
    """
    Extracts structured insights from conversations using Claude.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = None
        
        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            
    async def extract(
        self,
        conversation: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract insights from a conversation.
        
        Args:
            conversation: The conversation text
            context: Optional additional context
            
        Returns:
            Dict with facts, preferences, decisions, action_items, etc.
        """
        if not self.client:
            return self._empty_extraction("No API client available")
            
        context_section = ""
        if context:
            context_section = f"<context>\n{context}\n</context>\n"
            
        prompt = EXTRACTION_PROMPT.format(
            conversation=conversation,
            context_section=context_section,
        )
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",  # Use Sonnet for extraction (cheaper)
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Parse JSON from response
            text = response.content[0].text
            
            # Find JSON block
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            else:
                json_str = text
                
            result = json.loads(json_str.strip())
            result["_extracted_at"] = datetime.now().isoformat()
            result["_success"] = True
            
            return result
            
        except json.JSONDecodeError as e:
            return self._empty_extraction(f"JSON parse error: {e}")
        except Exception as e:
            return self._empty_extraction(f"Extraction error: {e}")
            
    def _empty_extraction(self, reason: str) -> Dict[str, Any]:
        """Return empty extraction result."""
        return {
            "facts": [],
            "preferences": [],
            "decisions": [],
            "action_items": [],
            "topics": [],
            "sentiment": "neutral",
            "key_entities": {"people": [], "projects": [], "tools": []},
            "summary": "",
            "_success": False,
            "_error": reason,
            "_extracted_at": datetime.now().isoformat(),
        }
        
    async def extract_batch(
        self,
        conversations: List[str],
    ) -> List[Dict[str, Any]]:
        """Extract insights from multiple conversations."""
        results = []
        for conv in conversations:
            result = await self.extract(conv)
            results.append(result)
        return results
        
    async def merge_extractions(
        self,
        extractions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge multiple extractions, deduplicating facts/preferences."""
        merged = {
            "facts": [],
            "preferences": [],
            "decisions": [],
            "action_items": [],
            "topics": [],
            "key_entities": {"people": set(), "projects": set(), "tools": set()},
        }
        
        seen_facts = set()
        seen_prefs = set()
        
        for ext in extractions:
            for fact in ext.get("facts", []):
                fact_lower = fact.lower()
                if fact_lower not in seen_facts:
                    seen_facts.add(fact_lower)
                    merged["facts"].append(fact)
                    
            for pref in ext.get("preferences", []):
                pref_lower = pref.lower()
                if pref_lower not in seen_prefs:
                    seen_prefs.add(pref_lower)
                    merged["preferences"].append(pref)
                    
            merged["decisions"].extend(ext.get("decisions", []))
            merged["action_items"].extend(ext.get("action_items", []))
            merged["topics"].extend(ext.get("topics", []))
            
            entities = ext.get("key_entities", {})
            merged["key_entities"]["people"].update(entities.get("people", []))
            merged["key_entities"]["projects"].update(entities.get("projects", []))
            merged["key_entities"]["tools"].update(entities.get("tools", []))
            
        # Convert sets back to lists
        merged["key_entities"] = {
            k: list(v) for k, v in merged["key_entities"].items()
        }
        
        # Deduplicate topics
        merged["topics"] = list(set(merged["topics"]))
        
        return merged
