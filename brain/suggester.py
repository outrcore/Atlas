"""
Proactive Suggester - Surfaces relevant context and suggestions proactively.
"""
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .linker import SemanticLinker


class ProactiveSuggester:
    """
    Proactively suggests relevant information and actions.
    
    Combines:
    - Semantic memory search
    - Knowledge base lookups
    - Pattern recognition
    - Time-based triggers
    """
    
    def __init__(
        self,
        knowledge_dir: Path,
        memory_dir: Path,
        linker: "SemanticLinker",
    ):
        self.knowledge_dir = Path(knowledge_dir)
        self.memory_dir = Path(memory_dir)
        self.linker = linker
        
        # Cache for recently accessed knowledge
        self._knowledge_cache: Dict[str, str] = {}
        
    async def suggest(
        self,
        current_context: Optional[str] = None,
    ) -> List[Dict]:
        """
        Generate proactive suggestions based on context.
        
        Args:
            current_context: Current conversation/task context
            
        Returns:
            List of suggestions with relevance scores
        """
        suggestions = []
        
        # 1. Time-based suggestions
        time_suggestions = self._get_time_based_suggestions()
        suggestions.extend(time_suggestions)
        
        # 2. Context-based suggestions (if context provided)
        if current_context:
            context_suggestions = await self._get_context_suggestions(current_context)
            suggestions.extend(context_suggestions)
            
        # 3. Pattern-based suggestions
        pattern_suggestions = await self._get_pattern_suggestions()
        suggestions.extend(pattern_suggestions)
        
        # Sort by relevance
        suggestions.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        
        return suggestions[:10]  # Top 10 suggestions
        
    def _get_time_based_suggestions(self) -> List[Dict]:
        """Get suggestions based on time of day/week."""
        suggestions = []
        now = datetime.now()
        
        # Morning suggestions (6-10 AM)
        if 6 <= now.hour < 10:
            suggestions.append({
                "type": "time_based",
                "suggestion": "Good morning! Would you like a briefing on today's schedule and any overnight updates?",
                "relevance": 0.8,
                "trigger": "morning",
            })
            
        # End of day (5-7 PM)
        elif 17 <= now.hour < 19:
            suggestions.append({
                "type": "time_based",
                "suggestion": "End of day approaching. Should I summarize what we accomplished today?",
                "relevance": 0.7,
                "trigger": "evening",
            })
            
        # Monday morning
        if now.weekday() == 0 and now.hour < 12:
            suggestions.append({
                "type": "time_based",
                "suggestion": "It's Monday! Would you like a weekly planning session?",
                "relevance": 0.75,
                "trigger": "monday_morning",
            })
            
        # Friday afternoon
        if now.weekday() == 4 and now.hour >= 14:
            suggestions.append({
                "type": "time_based",
                "suggestion": "It's Friday afternoon. Should I prepare a weekly summary?",
                "relevance": 0.7,
                "trigger": "friday_afternoon",
            })
            
        return suggestions
        
    async def _get_context_suggestions(
        self,
        context: str,
    ) -> List[Dict]:
        """Get suggestions based on current context."""
        suggestions = []
        
        # Search for related memories
        related = await self.linker.search(context, limit=5)
        
        for memory in related:
            if memory["score"] > 0.6:
                suggestions.append({
                    "type": "context_memory",
                    "suggestion": f"Related memory: {memory['content'][:100]}...",
                    "memory_id": memory["id"],
                    "relevance": memory["score"],
                    "category": memory["category"],
                })
                
        # Check knowledge base for relevant files
        knowledge_matches = self._search_knowledge(context)
        for match in knowledge_matches[:3]:
            suggestions.append({
                "type": "knowledge",
                "suggestion": f"Relevant knowledge: {match['title']}",
                "path": match["path"],
                "relevance": match["relevance"],
            })
            
        return suggestions
        
    async def _get_pattern_suggestions(self) -> List[Dict]:
        """Get suggestions based on observed patterns."""
        suggestions = []
        
        # Check for incomplete action items in recent memories
        recent = await self.linker.search("action item TODO", limit=10)
        
        incomplete = [m for m in recent if "incomplete" in m.get("metadata", {}).get("status", "incomplete")]
        if incomplete:
            suggestions.append({
                "type": "pattern",
                "suggestion": f"You have {len(incomplete)} incomplete action items from recent conversations.",
                "relevance": 0.85,
                "items": [m["content"][:50] for m in incomplete[:3]],
            })
            
        return suggestions
        
    def _search_knowledge(self, query: str, limit: int = 5) -> List[Dict]:
        """Simple keyword search in knowledge files."""
        results = []
        query_lower = query.lower()
        keywords = query_lower.split()
        
        for md_file in self.knowledge_dir.rglob("*.md"):
            try:
                content = md_file.read_text()
                content_lower = content.lower()
                
                # Count keyword matches
                matches = sum(1 for kw in keywords if kw in content_lower)
                
                if matches > 0:
                    # Extract title from first line
                    title = content.split("\n")[0].strip("# ").strip()
                    
                    results.append({
                        "path": str(md_file),
                        "title": title or md_file.stem,
                        "relevance": min(matches / len(keywords), 1.0),
                    })
            except Exception:
                pass
                
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:limit]
        
    async def get_recent_context(self) -> str:
        """Get recent context for prediction."""
        # Read today's memory file
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = self.memory_dir / f"{today}.md"
        
        context_parts = []
        
        if today_file.exists():
            context_parts.append(f"Today's notes:\n{today_file.read_text()[:2000]}")
            
        # Get yesterday too
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_file = self.memory_dir / f"{yesterday}.md"
        
        if yesterday_file.exists():
            context_parts.append(f"Yesterday's notes:\n{yesterday_file.read_text()[:1000]}")
            
        # Get recent memories from vector DB
        recent_memories = await self.linker.search("recent activity", limit=5)
        if recent_memories:
            memory_text = "\n".join([m["content"][:100] for m in recent_memories])
            context_parts.append(f"Recent memories:\n{memory_text}")
            
        return "\n\n".join(context_parts)
        
    def get_knowledge_summary(self, category: str) -> str:
        """Get a summary of knowledge in a category."""
        category_dir = self.knowledge_dir / category
        
        if not category_dir.exists():
            return f"No knowledge found in category: {category}"
            
        files = list(category_dir.glob("*.md"))
        
        summary_lines = [f"# Knowledge in {category}", f"Total files: {len(files)}", ""]
        
        for f in files[:10]:
            title = f.stem.replace("-", " ").title()
            summary_lines.append(f"- {title}")
            
        if len(files) > 10:
            summary_lines.append(f"- ... and {len(files) - 10} more")
            
        return "\n".join(summary_lines)
