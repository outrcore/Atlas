"""
Brain Core - The main orchestrator for ATLAS's memory and intelligence system.
"""
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

from .activity import ActivityLogger
from .extractor import MemoryExtractor
from .linker import SemanticLinker
from .predictor import IntentPredictor
from .suggester import ProactiveSuggester
from .utils import ensure_api_key


class Brain:
    """
    ATLAS Brain - Proactive Memory & Intelligence System
    
    Orchestrates all brain components to provide:
    - Automatic activity logging
    - Insight extraction from conversations
    - Semantic memory linking
    - Intent prediction
    - Proactive suggestions
    """
    
    def __init__(
        self,
        workspace: str = "/workspace/clawd",
        anthropic_api_key: Optional[str] = None,
    ):
        self.workspace = Path(workspace)
        
        # Ensure API key is available
        ensure_api_key()
        self.api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        # Paths
        self.brain_dir = self.workspace / "brain_data"
        self.knowledge_dir = self.workspace / "knowledge"
        self.memory_dir = self.workspace / "memory"
        self.vector_db_path = self.workspace / "data" / "vector_db"
        
        # Ensure directories exist
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.activity_logger = ActivityLogger(self.brain_dir / "activity")
        self.extractor = MemoryExtractor(api_key=self.api_key)
        self.linker = SemanticLinker(self.vector_db_path)
        self.predictor = IntentPredictor(api_key=self.api_key)
        self.suggester = ProactiveSuggester(
            knowledge_dir=self.knowledge_dir,
            memory_dir=self.memory_dir,
            linker=self.linker,
        )
        
        # State
        self._initialized = False
        self._last_maintenance = None
        
    async def initialize(self):
        """Initialize all brain components."""
        if self._initialized:
            return
            
        print("🧠 Initializing ATLAS Brain...")
        
        # Initialize linker (loads/creates vector DB)
        await self.linker.initialize()
        
        # Load recent activity context
        self.activity_logger.load_recent(days=7)
        
        self._initialized = True
        print("🧠 Brain initialized!")
        
    def log_activity(
        self,
        activity_type: str,
        content: str,
        metadata: Optional[Dict] = None,
    ):
        """
        Log an activity (conversation, action, event).
        
        Args:
            activity_type: Type of activity (conversation, action, observation, etc.)
            content: The content/text of the activity
            metadata: Optional additional metadata
        """
        self.activity_logger.log(
            activity_type=activity_type,
            content=content,
            metadata=metadata or {},
        )
        
    async def extract_insights(
        self,
        conversation: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract insights, facts, and preferences from a conversation.
        
        Args:
            conversation: The conversation text to analyze
            context: Optional additional context
            
        Returns:
            Dict with extracted facts, preferences, action_items, etc.
        """
        return await self.extractor.extract(conversation, context)
        
    async def link_memory(
        self,
        content: str,
        category: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add content to semantic memory and link to related memories.
        
        Args:
            content: The content to store
            category: Dewey Decimal category (e.g., "300-personal")
            metadata: Optional metadata
            
        Returns:
            Memory ID
        """
        return await self.linker.add_and_link(content, category, metadata)
        
    async def find_related(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """
        Find memories related to a query.
        
        Args:
            query: Search query
            limit: Max results
            category: Optional category filter
            
        Returns:
            List of related memories with scores
        """
        return await self.linker.search(query, limit, category)
        
    async def predict_intent(
        self,
        recent_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Predict what the user might need based on recent activity.
        
        Args:
            recent_hours: How many hours of activity to consider
            
        Returns:
            Dict with predictions, confidence, and reasoning
        """
        # Get recent activities
        activities = self.activity_logger.get_recent(hours=recent_hours)
        
        # Get recent memories
        recent_memories = await self.suggester.get_recent_context()
        
        return await self.predictor.predict(
            activities=activities,
            context=recent_memories,
        )
        
    async def get_proactive_suggestions(
        self,
        current_context: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get proactive suggestions based on context and patterns.
        
        Args:
            current_context: Current conversation/task context
            
        Returns:
            List of suggestions with relevance scores
        """
        return await self.suggester.suggest(current_context)
        
    async def run_maintenance(self):
        """
        Run periodic maintenance tasks:
        - Extract insights from recent unprocessed conversations
        - Update memory links
        - Cluster related memories
        - Clean up old activity logs
        """
        print("🧠 Running brain maintenance...")
        
        # Get unprocessed activities
        unprocessed = self.activity_logger.get_unprocessed()
        
        for activity in unprocessed:
            if activity["type"] == "conversation":
                # Extract insights
                insights = await self.extract_insights(activity["content"])
                
                # Store extracted facts
                if insights.get("facts"):
                    for fact in insights["facts"]:
                        await self.link_memory(
                            content=fact,
                            category="000-reference",
                            metadata={"source": "extracted", "activity_id": activity["id"]},
                        )
                        
                # Store preferences
                if insights.get("preferences"):
                    for pref in insights["preferences"]:
                        await self.link_memory(
                            content=pref,
                            category="300-personal",
                            metadata={"source": "extracted", "type": "preference"},
                        )
                        
                # Mark as processed
                self.activity_logger.mark_processed(activity["id"])
                
        # Update memory clusters
        await self.linker.update_clusters()
        
        # Clean old logs (keep 30 days)
        self.activity_logger.cleanup(days=30)
        
        self._last_maintenance = datetime.now()
        print("🧠 Maintenance complete!")
        
    async def think(self, query: str) -> Dict[str, Any]:
        """
        High-level thinking: combines search, prediction, and suggestions.
        
        Use this for complex queries that need the full brain.
        
        Args:
            query: What to think about
            
        Returns:
            Dict with relevant_memories, predictions, suggestions, synthesis
        """
        # Find related memories
        related = await self.find_related(query, limit=10)
        
        # Get predictions
        predictions = await self.predict_intent()
        
        # Get suggestions
        suggestions = await self.get_proactive_suggestions(query)
        
        # Synthesize (could use Claude to combine these)
        return {
            "query": query,
            "relevant_memories": related,
            "predictions": predictions,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat(),
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get brain status and statistics."""
        return {
            "initialized": self._initialized,
            "last_maintenance": self._last_maintenance.isoformat() if self._last_maintenance else None,
            "activity_count": self.activity_logger.count(),
            "memory_count": self.linker.count() if self._initialized else 0,
            "paths": {
                "brain_data": str(self.brain_dir),
                "knowledge": str(self.knowledge_dir),
                "memory": str(self.memory_dir),
                "vector_db": str(self.vector_db_path),
            }
        }
