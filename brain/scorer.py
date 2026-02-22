"""
Multi-Dimensional Scorer - UMA Phase 3

Combines multiple signals for memory relevance scoring:
- Semantic similarity (vector)
- Recency (time decay)
- Relationship (graph proximity)
- Importance (node weight)
- Reliability (source quality)

Created: 2026-02-06
"""

import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

try:
    from .fast_graph import FastGraph, get_fast_graph
except ImportError:
    from fast_graph import FastGraph, get_fast_graph


@dataclass
class ScoredMemory:
    """A memory with multi-dimensional scores."""
    content: str
    source: str
    
    # Individual scores (0-1)
    semantic_score: float = 0.0
    recency_score: float = 0.0
    relationship_score: float = 0.0
    importance_score: float = 0.0
    reliability_score: float = 0.0
    
    # Final weighted score
    final_score: float = 0.0
    
    # Metadata
    timestamp: Optional[datetime] = None
    node_ids: List[str] = field(default_factory=list)
    
    @property
    def score_breakdown(self) -> Dict[str, float]:
        return {
            'semantic': self.semantic_score,
            'recency': self.recency_score,
            'relationship': self.relationship_score,
            'importance': self.importance_score,
            'reliability': self.reliability_score,
            'final': self.final_score
        }


@dataclass
class Candidate:
    """A candidate memory for scoring."""
    content: str
    source: str
    embedding: Optional[List[float]] = None
    timestamp: Optional[datetime] = None
    node_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiDimensionalScorer:
    """
    Score memories using multiple signals.
    """
    
    # Configurable weights
    WEIGHTS = {
        'semantic': 0.30,      # Vector similarity
        'recency': 0.20,       # How recent
        'relationship': 0.25,  # Graph proximity
        'importance': 0.15,    # Node importance
        'reliability': 0.10,   # Source quality
    }
    
    # Source reliability scores
    SOURCE_RELIABILITY = {
        'memory/': 0.9,        # Daily logs - high
        'knowledge/': 1.0,     # Knowledge base - highest
        'session:': 0.7,       # Session extracts
        'MEMORY.md': 1.0,      # Curated memory
        'default': 0.5
    }
    
    def __init__(self, graph: Optional[FastGraph] = None):
        self.graph = graph or get_fast_graph()
    
    def score(
        self,
        candidates: List[Candidate],
        query_entities: List[str],
        query_embedding: Optional[List[float]] = None
    ) -> List[ScoredMemory]:
        """
        Score candidates using all dimensions.
        
        Args:
            candidates: List of candidate memories
            query_entities: Entity names from the query
            query_embedding: Vector embedding of the query (if available)
            
        Returns:
            Sorted list of ScoredMemory (highest first)
        """
        scored = []
        
        for c in candidates:
            scores = {
                'semantic': self._semantic_score(c, query_embedding),
                'recency': self._recency_score(c.timestamp),
                'relationship': self._relationship_score(c, query_entities),
                'importance': self._importance_score(c.node_ids),
                'reliability': self._reliability_score(c.source),
            }
            
            # Weighted combination
            final = sum(scores[k] * self.WEIGHTS[k] for k in scores)
            
            scored.append(ScoredMemory(
                content=c.content,
                source=c.source,
                semantic_score=scores['semantic'],
                recency_score=scores['recency'],
                relationship_score=scores['relationship'],
                importance_score=scores['importance'],
                reliability_score=scores['reliability'],
                final_score=final,
                timestamp=c.timestamp,
                node_ids=c.node_ids
            ))
        
        return sorted(scored, key=lambda x: x.final_score, reverse=True)
    
    def _semantic_score(
        self,
        candidate: Candidate,
        query_embedding=None
    ) -> float:
        """Cosine similarity between candidate and query embeddings."""
        if query_embedding is None or candidate.embedding is None:
            return 0.5  # Neutral if no embeddings
        
        try:
            import numpy as np
            q = np.asarray(query_embedding)
            c = np.asarray(candidate.embedding)
            dot = float(np.dot(q, c))
            norm_q = float(np.linalg.norm(q))
            norm_c = float(np.linalg.norm(c))
            if norm_q == 0 or norm_c == 0:
                return 0.5
            similarity = dot / (norm_q * norm_c)
        except Exception:
            return 0.5
        
        # Normalize to 0-1 (cosine similarity is -1 to 1)
        return (similarity + 1) / 2
    
    def _recency_score(self, timestamp: Optional[datetime]) -> float:
        """Exponential decay based on age."""
        if not timestamp:
            return 0.5  # Neutral if no timestamp
        
        age_days = (datetime.now() - timestamp).days
        # Half-life of ~30 days
        return math.exp(-age_days / 30)
    
    def _relationship_score(
        self,
        candidate: Candidate,
        query_entities: List[str]
    ) -> float:
        """Graph distance from candidate to query entities (FAST with NetworkX)."""
        if not query_entities or not candidate.node_ids:
            return 0.5  # Neutral if no graph info
        
        best_score = 0.0
        
        for query_entity in query_entities:
            # Find the query entity in the graph
            query_node = self.graph.find_node('person', query_entity)
            if not query_node:
                query_node = self.graph.find_node('project', query_entity)
            if not query_node:
                # Try searching
                nodes = self.graph.search_nodes(query_entity, limit=1)
                query_node = nodes[0] if nodes else None
            
            if not query_node:
                continue
            
            for candidate_node_id in candidate.node_ids:
                # Use fast connection_strength instead of BFS
                strength = self.graph.connection_strength(query_node.id, candidate_node_id)
                best_score = max(best_score, strength)
        
        return best_score if best_score > 0 else 0.3
    
    def _importance_score(self, node_ids: List[str]) -> float:
        """Average importance of related nodes."""
        if not node_ids:
            return 0.5
        
        total = 0.0
        count = 0
        
        for node_id in node_ids:
            node = self.graph.get_node(node_id)
            if node:
                total += node.importance
                count += 1
        
        return total / count if count > 0 else 0.5
    
    def _reliability_score(self, source: str) -> float:
        """Score based on source type."""
        for prefix, score in self.SOURCE_RELIABILITY.items():
            if prefix in source:
                return score
        return self.SOURCE_RELIABILITY['default']


# Quick test
if __name__ == "__main__":
    scorer = MultiDimensionalScorer()
    
    # Test candidates
    candidates = [
        Candidate(
            content="User decided to use SQLite for the graph",
            source="memory/2026-02-06.md",
            timestamp=datetime.now()
        ),
        Candidate(
            content="ProjectAlpha uses Supabase for the backend",
            source="knowledge/100-projects/wander/PROJECT.md"
        ),
        Candidate(
            content="Old decision from last month",
            source="memory/2026-01-06.md",
            timestamp=datetime(2026, 1, 6)
        ),
    ]
    
    results = scorer.score(candidates, query_entities=['User', 'SQLite'])
    
    print("Scored memories:")
    for r in results:
        print(f"  {r.final_score:.2f}: {r.content[:50]}...")
        print(f"       Breakdown: {r.score_breakdown}")
