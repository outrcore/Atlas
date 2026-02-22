"""
Unified Search - UMA Phase 3

Combines:
- Entity graph traversal
- Vector similarity search
- Multi-dimensional scoring

Single entry point for memory queries.

Created: 2026-02-06
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    from .fast_graph import FastGraph, get_fast_graph
    from .graph_extractor import GraphExtractor
    from .scorer import MultiDimensionalScorer, Candidate, ScoredMemory
    from .sonnet_extractor import SonnetExtractor
    from .graph_rag import get_graph_rag
    from .embedder import get_embedder
except ImportError:
    from fast_graph import FastGraph, get_fast_graph
    from graph_extractor import GraphExtractor
    from scorer import MultiDimensionalScorer, Candidate, ScoredMemory
    from sonnet_extractor import SonnetExtractor
    from graph_rag import get_graph_rag
    from embedder import get_embedder

# Try to import LanceDB for vector search
try:
    import lancedb
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False


@dataclass
class SearchResult:
    """Result from unified search."""
    memories: List[ScoredMemory]
    graph_context: Dict[str, Any]
    query_entities: List[str]
    method: str  # 'graph', 'vector', 'hybrid'
    confidence: float


class UnifiedSearch:
    """
    Unified memory search combining graph and vector approaches.
    """
    
    def __init__(
        self,
        graph: Optional[FastGraph] = None,
        vector_db_path: Optional[str] = None
    ):
        self.graph = graph or get_fast_graph()
        self.scorer = MultiDimensionalScorer(self.graph)
        self.extractor = SonnetExtractor()
        
        # Vector DB
        self.vector_db = None
        if HAS_LANCEDB:
            db_path = vector_db_path or "/workspace/clawd/brain/lancedb"
            if Path(db_path).exists():
                try:
                    self.vector_db = lancedb.connect(db_path)
                except:
                    pass
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        include_graph: bool = True,
        include_vector: bool = True,
        query_embedding=None,
        node_embeddings: dict = None
    ) -> SearchResult:
        """
        Search memories using all available methods.
        
        Args:
            query: Natural language query
            limit: Max results to return
            include_graph: Use graph traversal
            include_vector: Use vector similarity
            
        Returns:
            SearchResult with scored memories
        """
        candidates = []
        query_entities = []
        method = 'hybrid'
        
        # Step 0: Compute query embedding if not provided
        if query_embedding is None:
            try:
                embedder = get_embedder()
                query_embedding = embedder.embed(query)
            except Exception as e:
                print(f"Embedder error: {e}")
        
        # Step 1: Extract entities from query
        if include_graph:
            query_entities = await self._extract_query_entities(query)
        
        # Step 2: Graph-based search
        if include_graph and query_entities:
            graph_candidates = self._search_graph(query_entities, limit=limit * 2)
            candidates.extend(graph_candidates)
        
        # Step 3: Vector search (if available)
        if include_vector and self.vector_db:
            vector_candidates = self._search_vector(query, limit=limit * 2)
            candidates.extend(vector_candidates)
        
        # Step 4: Deduplicate
        candidates = self._deduplicate(candidates)
        
        # Step 4.5: Compute embeddings for candidates that don't have them
        if query_embedding is not None:
            try:
                embedder = get_embedder()
                texts_to_embed = []
                indices_to_embed = []
                for i, c in enumerate(candidates):
                    if c.embedding is None and c.content:
                        texts_to_embed.append(c.content[:512])  # Truncate for efficiency
                        indices_to_embed.append(i)
                
                if texts_to_embed:
                    embeddings = embedder.embed_batch(texts_to_embed)
                    for idx, emb in zip(indices_to_embed, embeddings):
                        candidates[idx].embedding = emb
            except Exception as e:
                print(f"Batch embedding error: {e}")
        
        # Step 5: Score all candidates
        scored = self.scorer.score(
            candidates,
            query_entities=query_entities,
            query_embedding=query_embedding
        )
        
        # Step 5.5: Apply Graph RAG boosts
        scored = self._apply_graph_rag_boosts(scored, query_entities)
        
        # Step 6: Get graph context for top results
        graph_context = {}
        if query_entities:
            graph_context = self._get_graph_context(query_entities)
        
        # Determine method used
        if candidates and not self.vector_db:
            method = 'graph'
        elif not query_entities:
            method = 'vector'
        
        # Calculate confidence
        confidence = self._calculate_confidence(scored[:limit])
        
        return SearchResult(
            memories=scored[:limit],
            graph_context=graph_context,
            query_entities=query_entities,
            method=method,
            confidence=confidence
        )
    
    async def _extract_query_entities(self, query: str) -> List[str]:
        """Extract entity names from query."""
        entities = []
        query_lower = query.lower()
        
        # Skip common stop words
        stop_words = {'what', 'is', 'the', 'a', 'an', 'how', 'why', 'when', 'where',
                      'who', 'which', 'that', 'this', 'are', 'was', 'were', 'be',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                      'could', 'should', 'can', 'may', 'might', 'about', 'with',
                      'from', 'for', 'and', 'but', 'or', 'not', 'we', 'our', 'my',
                      'i', 'me', 'you', 'your', 'it', 'its', 'on', 'in', 'to', 'of',
                      'at', 'by', 'up', 'so', 'if', 'no', 'yes', 'all', 'any', 'some'}
        
        # Extract meaningful words from query (strip punctuation)
        words = [w.strip('?.,!:;()[]"\'') for w in query.split() 
                 if w.lower().strip('?.,!:;()[]"\'') not in stop_words and len(w.strip('?.,!:;()[]"\'')) > 1]
        
        # Also try multi-word phrases (bigrams)
        phrases = words[:]
        for i in range(len(words) - 1):
            phrases.append(f"{words[i]} {words[i+1]}")
        
        # Search graph for matching nodes - prefer exact/close matches
        seen = set()
        for phrase in phrases:
            nodes = self.graph.search_nodes(phrase, limit=3)
            for node in nodes:
                name_lower = node.name.lower()
                phrase_lower = phrase.lower().strip('?.,!')
                # Require strong match: phrase in node name OR node name in query
                if (phrase_lower in name_lower or name_lower in query_lower) and \
                   len(node.name) < 100 and node.name not in seen:  # Skip long decision strings
                    seen.add(node.name)
                    entities.append(node.name)
        
        return list(dict.fromkeys(entities))  # Preserve order, dedupe
    
    def _search_graph(self, entities: List[str], limit: int = 20) -> List[Candidate]:
        """Search graph for relevant memories by reading source files."""
        candidates = []
        seen_sources = set()
        
        # Collect all evidence file paths and their associated node IDs
        source_nodes: Dict[str, List[str]] = {}  # source_path -> [node_ids]
        
        for entity_name in entities:
            # Find the entity node
            node = None
            for node_type in ['person', 'project', 'tool', 'decision', 'concept']:
                node = self.graph.find_node(node_type, entity_name)
                if node:
                    break
            
            if not node:
                nodes = self.graph.search_nodes(entity_name, limit=1)
                node = nodes[0] if nodes else None
            
            if not node:
                continue
            
            # Get neighbors (related nodes)
            neighbors = self.graph.get_neighbors(node.id, depth=2)
            
            for neighbor_node, edge, depth in neighbors:
                evidence = edge.evidence
                if evidence:
                    if evidence not in source_nodes:
                        source_nodes[evidence] = []
                    source_nodes[evidence].extend([node.id, neighbor_node.id])
            
            # Also check node metadata for source
            if node.type == 'decision':
                src = node.metadata.get('source')
                if src:
                    if src not in source_nodes:
                        source_nodes[src] = []
                    source_nodes[src].append(node.id)
        
        # Read actual file content from evidence sources
        workspace = Path("/workspace/clawd")
        for source_path, node_ids in source_nodes.items():
            if source_path in seen_sources:
                continue
            seen_sources.add(source_path)
            
            # Resolve path
            p = Path(source_path)
            if not p.is_absolute():
                p = workspace / source_path
            
            if not p.exists() or not p.is_file():
                continue
            
            try:
                content = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            
            if not content.strip():
                continue
            
            # Split into chunks by sections (## headers) for granularity
            chunks = self._chunk_file(content, source_path)
            unique_nodes = list(dict.fromkeys(node_ids))
            
            for chunk_text, chunk_source in chunks:
                candidates.append(Candidate(
                    content=chunk_text,
                    source=chunk_source,
                    node_ids=unique_nodes,
                    metadata={'type': 'file_chunk'}
                ))
        
        return candidates[:limit]
    
    def _chunk_file(self, content: str, source: str, max_chunk: int = 500) -> List[tuple]:
        """Split file content into section-based chunks."""
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_len = 0
        
        for line in lines:
            if line.startswith('## ') and current_chunk:
                # Start new chunk at section boundary
                text = '\n'.join(current_chunk).strip()
                if text and len(text) > 30:
                    chunks.append((text[:max_chunk], source))
                current_chunk = [line]
                current_len = len(line)
            else:
                current_chunk.append(line)
                current_len += len(line)
                if current_len > max_chunk:
                    text = '\n'.join(current_chunk).strip()
                    if text and len(text) > 30:
                        chunks.append((text[:max_chunk], source))
                    current_chunk = []
                    current_len = 0
        
        # Last chunk
        if current_chunk:
            text = '\n'.join(current_chunk).strip()
            if text and len(text) > 30:
                chunks.append((text[:max_chunk], source))
        
        # If no chunks (small file), return whole content
        if not chunks and content.strip():
            chunks.append((content[:max_chunk], source))
        
        return chunks
    
    def _search_vector(self, query: str, limit: int = 20) -> List[Candidate]:
        """Search vector DB for similar content."""
        if not self.vector_db:
            return []
        
        candidates = []
        
        try:
            # Try memories table
            if 'memories' in self.vector_db.table_names():
                table = self.vector_db.open_table('memories')
                results = table.search(query).limit(limit).to_list()
                
                for r in results:
                    candidates.append(Candidate(
                        content=r.get('text', r.get('content', '')),
                        source=r.get('source', 'vector'),
                        timestamp=self._parse_timestamp(r.get('timestamp')),
                        metadata={'score': r.get('_distance', 0)}
                    ))
            
            # Try knowledge table
            if 'knowledge' in self.vector_db.table_names():
                table = self.vector_db.open_table('knowledge')
                results = table.search(query).limit(limit).to_list()
                
                for r in results:
                    candidates.append(Candidate(
                        content=r.get('text', r.get('content', '')),
                        source=r.get('source', 'knowledge'),
                        metadata={'score': r.get('_distance', 0)}
                    ))
        except Exception as e:
            print(f"Vector search error: {e}")
        
        return candidates
    
    def _deduplicate(self, candidates: List[Candidate]) -> List[Candidate]:
        """Remove duplicate candidates."""
        seen = set()
        unique = []
        
        for c in candidates:
            # Create a key from content
            key = c.content[:100].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(c)
        
        return unique
    
    def _get_graph_context(self, entities: List[str]) -> Dict[str, Any]:
        """Get graph context for entities."""
        context = {
            'entities': {},
            'relationships': []
        }
        
        for entity_name in entities:
            # Find node
            node = None
            for node_type in ['person', 'project', 'tool', 'decision']:
                node = self.graph.find_node(node_type, entity_name)
                if node:
                    break
            
            if not node:
                nodes = self.graph.search_nodes(entity_name, limit=1)
                node = nodes[0] if nodes else None
            
            if node:
                context['entities'][entity_name] = {
                    'type': node.type,
                    'importance': node.importance,
                    'access_count': node.access_count
                }
                
                # Get direct relationships
                edges = self.graph.get_edges(node.id, direction='both')
                for edge in edges[:5]:  # Limit to 5 per entity
                    other_id = edge.target_id if edge.source_id == node.id else edge.source_id
                    other = self.graph.get_node(other_id)
                    
                    if other:
                        context['relationships'].append({
                            'from': entity_name,
                            'relation': edge.relation,
                            'to': other.name,
                            'weight': edge.weight
                        })
        
        return context
    
    def _apply_graph_rag_boosts(
        self,
        scored: List[ScoredMemory],
        query_entities: List[str]
    ) -> List[ScoredMemory]:
        """Apply Graph RAG path/community/centrality boosts to scored results."""
        if not scored:
            return scored

        try:
            rag = get_graph_rag()
        except Exception:
            return scored

        # Find seed node IDs from query entities
        seed_ids = []
        for entity_name in query_entities:
            node = None
            for t in ['person', 'project', 'tool', 'decision', 'concept']:
                node = self.graph.find_node(t, entity_name)
                if node:
                    break
            if not node:
                nodes = self.graph.search_nodes(entity_name, limit=1)
                node = nodes[0] if nodes else None
            if node:
                seed_ids.append(node.id)

        if not seed_ids:
            return scored

        # Collect all candidate node IDs
        all_node_ids = set()
        for mem in scored:
            all_node_ids.update(mem.node_ids or [])

        if not all_node_ids:
            return scored

        # Get boosts
        try:
            boosts = rag.boost_scores(seed_ids, list(all_node_ids))
        except Exception:
            return scored

        # Apply boosts to final scores
        for mem in scored:
            if not mem.node_ids:
                continue
            # Take best boost across the memory's nodes
            best_path = 0.0
            best_comm = 0.0
            best_cent = 1.0
            for nid in mem.node_ids:
                if nid in boosts:
                    b = boosts[nid]
                    best_path = max(best_path, b["path"])
                    best_comm = max(best_comm, b["community"])
                    best_cent = max(best_cent, b["centrality"])

            # Additive path + community boost, multiplicative centrality
            mem.final_score = (mem.final_score + best_path * 0.15 + best_comm * 0.1) * best_cent

        # Re-sort
        scored.sort(key=lambda x: x.final_score, reverse=True)
        return scored

    def _calculate_confidence(self, memories: List[ScoredMemory]) -> float:
        """Calculate overall confidence in results."""
        if not memories:
            return 0.0
        scores = [m.final_score for m in memories[:5]]
        top = max(scores)
        spread = max(scores) - min(scores) if len(scores) > 1 else 0
        # High confidence = high top score AND good differentiation
        differentiation = min(spread / 0.3, 1.0)
        return top * 0.6 + differentiation * 0.4
    
    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if not ts:
            return None
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(str(ts))
        except:
            return None
    
    # ─────────────────────────────────────────────────────────────
    # Convenience methods
    # ─────────────────────────────────────────────────────────────
    
    async def ask(self, question: str) -> str:
        """
        Simple Q&A interface.
        
        Returns formatted answer with sources.
        """
        result = await self.search(question, limit=5)
        
        if not result.memories:
            return "No relevant memories found."
        
        lines = [f"Found {len(result.memories)} relevant memories:\n"]
        
        for i, mem in enumerate(result.memories, 1):
            lines.append(f"{i}. [{mem.final_score:.2f}] {mem.content}")
            lines.append(f"   Source: {mem.source}")
            lines.append("")
        
        if result.graph_context.get('relationships'):
            lines.append("Graph context:")
            for rel in result.graph_context['relationships'][:3]:
                lines.append(f"  • {rel['from']} → {rel['relation']} → {rel['to']}")
        
        return "\n".join(lines)


# Singleton for easy access
_unified_search = None

def get_unified_search() -> UnifiedSearch:
    """Get or create the unified search instance."""
    global _unified_search
    if _unified_search is None:
        _unified_search = UnifiedSearch()
    return _unified_search


async def search(query: str, limit: int = 10) -> SearchResult:
    """Convenience function for searching."""
    return await get_unified_search().search(query, limit)


async def ask(question: str) -> str:
    """Convenience function for Q&A."""
    return await get_unified_search().ask(question)


# CLI
if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python unified_search.py <query>")
            print("\nExample: python unified_search.py 'What did the user decide about ProjectBeta?'")
            return
        
        query = " ".join(sys.argv[1:])
        print(f"Query: {query}\n")
        
        result = await search(query, limit=5)
        
        print(f"Method: {result.method}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Entities found: {result.query_entities}")
        print()
        
        for i, mem in enumerate(result.memories, 1):
            print(f"{i}. [{mem.final_score:.2f}] {mem.content}")
            print(f"   Scores: sem={mem.semantic_score:.2f} rec={mem.recency_score:.2f} " +
                  f"rel={mem.relationship_score:.2f} imp={mem.importance_score:.2f}")
            print()
    
    asyncio.run(main())
