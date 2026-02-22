#!/usr/bin/env python3
"""
ATLAS Brain v2 - Phase 5: Proactive Recall
===========================================
Automatically surfaces relevant memories before responding.

Based on research:
- Context injection techniques
- Retrieval-Augmented Generation (RAG)
- Timing and readiness awareness
- Pattern detection for proactive suggestions

Key concept: Before responding to any query, search memories
and inject relevant context. "Remember when..." suggestions.
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import re

# Try to import vector DB components
try:
    import lancedb
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False


@dataclass
class RecallResult:
    """A single recalled memory."""
    content: str
    source: str
    relevance_score: float
    timestamp: Optional[str] = None
    category: Optional[str] = None
    context_type: str = "semantic"  # semantic, temporal, entity


@dataclass
class ProactiveContext:
    """Context to inject before responding."""
    query: str
    recalled_memories: List[RecallResult]
    suggested_context: str
    confidence: float
    recall_type: str  # semantic, temporal, entity, pattern


class MemoryIndex:
    """
    Fast memory index for proactive recall.
    
    Combines:
    - Vector similarity (semantic)
    - Keyword matching (entities)
    - Temporal patterns (recent, recurring)
    """
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.workspace = Path(workspace)
        self.memory_file = self.workspace / "MEMORY.md"
        self.memory_dir = self.workspace / "memory"
        self.vector_db_path = self.workspace / "data" / "vector_db"
        
        # Load embedder
        self.embedder = None
        if HAS_EMBEDDINGS:
            try:
                self.embedder = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)
                if hasattr(self.embedder, 'max_seq_length'):
                    self.embedder.max_seq_length = 8192
            except Exception as e:
                print(f"[proactive_recall] Could not load embedder: {e}")
        
        # Load vector DB
        self.db = None
        if HAS_LANCEDB and self.vector_db_path.exists():
            try:
                self.db = lancedb.connect(str(self.vector_db_path))
            except Exception:
                pass
        
        # Cache for MEMORY.md content
        self._memory_cache: Optional[str] = None
        self._memory_cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)
    
    def _get_memory_content(self) -> str:
        """Get MEMORY.md content with caching."""
        now = datetime.now()
        
        if (self._memory_cache is not None and 
            self._memory_cache_time is not None and
            now - self._memory_cache_time < self._cache_ttl):
            return self._memory_cache
        
        if self.memory_file.exists():
            self._memory_cache = self.memory_file.read_text()
            self._memory_cache_time = now
            return self._memory_cache
        
        return ""
    
    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Extract sections from MEMORY.md."""
        sections = {}
        current_section = "general"
        current_content = []
        
        for line in content.split('\n'):
            if line.startswith('## '):
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line[3:].strip().lower()
                current_content = []
            else:
                current_content.append(line)
        
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _keyword_search(self, query: str, content: str, limit: int = 5) -> List[RecallResult]:
        """Simple keyword-based search."""
        results = []
        query_words = set(query.lower().split())
        
        # Split content into chunks (paragraphs or list items)
        chunks = re.split(r'\n\n+', content)
        
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or len(chunk) < 20:
                continue
            
            chunk_lower = chunk.lower()
            
            # Count matching words
            matches = sum(1 for word in query_words if word in chunk_lower)
            
            if matches > 0:
                # Calculate relevance
                relevance = matches / len(query_words) if query_words else 0
                
                results.append(RecallResult(
                    content=chunk[:500],
                    source="MEMORY.md",
                    relevance_score=relevance,
                    context_type="keyword",
                ))
        
        # Sort by relevance and return top N
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:limit]
    
    async def semantic_search(self, query: str, limit: int = 5) -> List[RecallResult]:
        """Search using vector embeddings."""
        results = []
        
        if not self.embedder or not self.db:
            return results
        
        try:
            # Check if memories table exists
            if "memories" not in self.db.table_names():
                return results
            
            table = self.db.open_table("memories")
            
            # Embed query
            query_embedding = self.embedder.encode(query).tolist()
            
            # Search
            search_results = table.search(query_embedding).limit(limit).to_list()
            
            for item in search_results:
                results.append(RecallResult(
                    content=item.get("text", "")[:500],
                    source=item.get("source", "vector_db"),
                    relevance_score=1.0 - item.get("_distance", 0.5),  # Convert distance to similarity
                    timestamp=item.get("timestamp"),
                    category=item.get("category"),
                    context_type="semantic",
                ))
        
        except Exception as e:
            print(f"[proactive_recall] Semantic search error: {e}")
        
        return results
    
    def entity_search(self, query: str, limit: int = 5) -> List[RecallResult]:
        """Search for specific entities mentioned in query."""
        results = []
        content = self._get_memory_content()
        
        # Extract potential entities from query
        # Look for capitalized words, quoted strings, paths, URLs
        entities = []
        
        # Capitalized words (potential names/projects)
        entities.extend(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query))
        
        # Quoted strings
        entities.extend(re.findall(r'"([^"]+)"', query))
        entities.extend(re.findall(r"'([^']+)'", query))
        
        # Technical terms (common patterns)
        entities.extend(re.findall(r'\b(?:api|key|token|password|project|app|repo)\b', query.lower()))
        
        if not entities:
            return results
        
        # Search for each entity in memory
        for entity in entities[:5]:  # Limit to 5 entities
            entity_lower = entity.lower()
            
            for line in content.split('\n'):
                if entity_lower in line.lower():
                    results.append(RecallResult(
                        content=line.strip()[:500],
                        source="MEMORY.md",
                        relevance_score=0.8,
                        context_type="entity",
                    ))
                    break  # One result per entity
        
        return results[:limit]
    
    def temporal_search(self, limit: int = 3) -> List[RecallResult]:
        """Get recent memories (last 24-48 hours)."""
        results = []
        
        # Check recent daily logs
        now = datetime.now()
        
        for days_ago in range(2):
            date = now - timedelta(days=days_ago)
            log_file = self.memory_dir / f"{date.strftime('%Y-%m-%d')}.md"
            
            if log_file.exists():
                content = log_file.read_text()
                
                # Extract key sections (headers and first few lines)
                lines = content.split('\n')
                key_lines = []
                
                for line in lines:
                    if line.startswith('#') or line.startswith('- **'):
                        key_lines.append(line)
                
                if key_lines:
                    results.append(RecallResult(
                        content='\n'.join(key_lines[:10]),
                        source=log_file.name,
                        relevance_score=0.7 - (days_ago * 0.2),
                        timestamp=date.isoformat(),
                        context_type="temporal",
                    ))
        
        return results[:limit]


class ProactiveRecaller:
    """
    Main class for proactive memory recall.
    
    Before responding to a query:
    1. Search for relevant memories
    2. Build context injection
    3. Return suggested context
    """
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.index = MemoryIndex(workspace)
        self.min_confidence = 0.3
    
    async def recall(
        self,
        query: str,
        include_temporal: bool = True,
        include_entity: bool = True,
        max_results: int = 5,
    ) -> ProactiveContext:
        """
        Recall relevant memories for a query.
        
        Returns context to inject before responding.
        """
        all_results: List[RecallResult] = []
        
        # 1. Semantic search (if available)
        semantic_results = await self.index.semantic_search(query, limit=3)
        all_results.extend(semantic_results)
        
        # 2. Keyword search in MEMORY.md
        memory_content = self.index._get_memory_content()
        keyword_results = self.index._keyword_search(query, memory_content, limit=3)
        all_results.extend(keyword_results)
        
        # 3. Entity search
        if include_entity:
            entity_results = self.index.entity_search(query, limit=2)
            all_results.extend(entity_results)
        
        # 4. Temporal context (recent memories)
        if include_temporal:
            temporal_results = self.index.temporal_search(limit=2)
            all_results.extend(temporal_results)
        
        # Deduplicate and sort by relevance
        seen_content = set()
        unique_results = []
        
        for result in sorted(all_results, key=lambda x: x.relevance_score, reverse=True):
            content_key = result.content[:100].lower()
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_results.append(result)
        
        unique_results = unique_results[:max_results]
        
        # Calculate overall confidence
        if unique_results:
            confidence = sum(r.relevance_score for r in unique_results) / len(unique_results)
        else:
            confidence = 0.0
        
        # Determine recall type
        if semantic_results:
            recall_type = "semantic"
        elif entity_results:
            recall_type = "entity"
        elif temporal_results:
            recall_type = "temporal"
        else:
            recall_type = "keyword"
        
        # Build suggested context
        suggested_context = self._build_context(query, unique_results)
        
        return ProactiveContext(
            query=query,
            recalled_memories=unique_results,
            suggested_context=suggested_context,
            confidence=confidence,
            recall_type=recall_type,
        )
    
    def _build_context(self, query: str, results: List[RecallResult]) -> str:
        """Build context string to inject."""
        if not results:
            return ""
        
        parts = ["[Relevant memories:]"]
        
        for result in results:
            content = result.content.strip()
            if len(content) > 200:
                content = content[:200] + "..."
            
            source_tag = f"({result.source})" if result.source else ""
            parts.append(f"- {content} {source_tag}")
        
        return '\n'.join(parts)
    
    async def get_context_injection(self, query: str) -> Optional[str]:
        """
        Get context to inject before responding.
        
        Returns None if no relevant context found.
        """
        context = await self.recall(query)
        
        if context.confidence >= self.min_confidence and context.recalled_memories:
            return context.suggested_context
        
        return None
    
    async def suggest_reminders(self, query: str) -> List[str]:
        """
        Suggest "remember when..." type reminders.
        
        Returns list of relevant past events/decisions.
        """
        reminders = []
        context = await self.recall(query, include_temporal=False)
        
        for memory in context.recalled_memories:
            if memory.relevance_score >= 0.5:
                # Format as reminder
                content = memory.content[:100]
                if memory.timestamp:
                    reminders.append(f"On {memory.timestamp}: {content}...")
                else:
                    reminders.append(f"Previously: {content}...")
        
        return reminders[:3]


# Convenience function for integration
async def get_proactive_context(query: str) -> Optional[str]:
    """
    Quick function to get proactive context for a query.
    
    Use before responding to inject relevant memories.
    """
    recaller = ProactiveRecaller()
    return await recaller.get_context_injection(query)


async def test_proactive_recall():
    """Test the proactive recall system."""
    print("🧠 Testing Proactive Recall - Phase 5\n")
    
    recaller = ProactiveRecaller()
    
    test_queries = [
        "What's Matt's Perplexity API key?",
        "How do I run Claude Code?",
        "What did we work on yesterday?",
        "Mac Studio configuration",
        "Memory consolidation system",
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 50)
        
        context = await recaller.recall(query)
        
        print(f"   Confidence: {context.confidence:.0%}")
        print(f"   Recall type: {context.recall_type}")
        print(f"   Memories found: {len(context.recalled_memories)}")
        
        if context.recalled_memories:
            print(f"\n   Top memory:")
            top = context.recalled_memories[0]
            print(f"   [{top.relevance_score:.0%}] {top.content[:100]}...")
        
        if context.suggested_context:
            print(f"\n   Context injection preview:")
            print(f"   {context.suggested_context[:200]}...")
    
    print("\n" + "=" * 50)
    print("✨ Proactive recall test complete!")


if __name__ == "__main__":
    asyncio.run(test_proactive_recall())
