#!/usr/bin/env python3
"""
Smart Memory Consolidation with Deduplication
==============================================
Consolidates memories while checking against existing MEMORY.md
to avoid duplicates and build on existing knowledge.
"""

import os
import re
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False


class SmartConsolidator:
    """
    Memory consolidation that:
    1. Checks existing MEMORY.md before promoting
    2. Considers existing knowledge when scoring
    3. Avoids semantic duplicates
    4. Builds on rather than repeats existing facts
    """
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.workspace = Path(workspace)
        self.memory_file = self.workspace / "MEMORY.md"
        self.memory_dir = self.workspace / "memory"
        
        # Load embedder for semantic dedup
        self.embedder = None
        if HAS_EMBEDDINGS:
            try:
                self.embedder = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)
                if hasattr(self.embedder, 'max_seq_length'):
                    self.embedder.max_seq_length = 8192
            except Exception:
                pass
        
        # Cache for existing memory embeddings
        self._existing_embeddings: Optional[np.ndarray] = None
        self._existing_chunks: List[str] = []
        self.similarity_threshold = 0.85  # Above this = duplicate
    
    def _load_existing_memory(self) -> str:
        """Load current MEMORY.md content."""
        if self.memory_file.exists():
            return self.memory_file.read_text()
        return ""
    
    def _chunk_memory(self, content: str) -> List[str]:
        """Split MEMORY.md into searchable chunks."""
        chunks = []
        
        # Split by list items and paragraphs
        lines = content.split('\n')
        current_chunk = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    if len(chunk_text) > 20:
                        chunks.append(chunk_text)
                    current_chunk = []
            elif line.startswith('- ') or line.startswith('* '):
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    if len(chunk_text) > 20:
                        chunks.append(chunk_text)
                current_chunk = [line[2:]]
            elif line.startswith('#'):
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    if len(chunk_text) > 20:
                        chunks.append(chunk_text)
                current_chunk = []
            else:
                current_chunk.append(line)
        
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text) > 20:
                chunks.append(chunk_text)
        
        return chunks
    
    def _build_existing_index(self):
        """Build embedding index of existing MEMORY.md content."""
        if not self.embedder:
            return
        
        content = self._load_existing_memory()
        self._existing_chunks = self._chunk_memory(content)
        
        if self._existing_chunks:
            self._existing_embeddings = self.embedder.encode(
                self._existing_chunks,
                convert_to_numpy=True
            )
    
    def is_duplicate(self, candidate: str) -> tuple[bool, Optional[str]]:
        """
        Check if candidate is semantically similar to existing memory.
        
        Returns:
            (is_duplicate, similar_existing_text)
        """
        # Simple text match first
        existing_content = self._load_existing_memory().lower()
        candidate_lower = candidate.lower()[:200]
        
        if candidate_lower in existing_content:
            return True, "Exact match found"
        
        # Semantic similarity check
        if not self.embedder or self._existing_embeddings is None:
            return False, None
        
        if len(self._existing_chunks) == 0:
            return False, None
        
        try:
            candidate_emb = self.embedder.encode([candidate], convert_to_numpy=True)
            
            # Cosine similarity
            similarities = np.dot(self._existing_embeddings, candidate_emb.T).flatten()
            max_sim_idx = np.argmax(similarities)
            max_sim = similarities[max_sim_idx]
            
            if max_sim >= self.similarity_threshold:
                return True, self._existing_chunks[max_sim_idx][:100]
        except Exception:
            pass
        
        return False, None
    
    def score_with_context(
        self, 
        candidate: str, 
        existing_knowledge: str
    ) -> Dict[str, Any]:
        """
        Score a candidate considering existing knowledge.
        
        Boosts score if:
        - Adds NEW information to existing topics
        - Provides updates to known projects
        - Contains corrections or clarifications
        
        Reduces score if:
        - Just repeats existing facts
        - Contradicts without explanation
        """
        score_adjustment = 0.0
        reasons = []
        
        candidate_lower = candidate.lower()
        existing_lower = existing_knowledge.lower()
        
        # Check if it references known entities
        known_entities = ['user', 'atlas', 'brain', 'memory', 
                         'project_a', 'project_b', 'project_c', 'runpod']
        
        mentions_known = [e for e in known_entities if e in candidate_lower]
        
        if mentions_known:
            # References known stuff - check if it adds info
            for entity in mentions_known:
                # Find existing info about this entity
                if entity in existing_lower:
                    # We know about this - is the candidate adding new info?
                    if 'update' in candidate_lower or 'now' in candidate_lower:
                        score_adjustment += 0.1
                        reasons.append(f"Updates info about {entity}")
                    elif 'learned' in candidate_lower or 'discovered' in candidate_lower:
                        score_adjustment += 0.15
                        reasons.append(f"New learning about {entity}")
                else:
                    # New entity mention
                    score_adjustment += 0.1
                    reasons.append(f"New info about {entity}")
        
        # Boost for corrections/clarifications
        if any(x in candidate_lower for x in ['actually', 'correction', 'not ', 'wrong']):
            score_adjustment += 0.1
            reasons.append("Contains correction")
        
        # Boost for decisions
        if any(x in candidate_lower for x in ['decided', 'will use', 'chose', 'going with']):
            score_adjustment += 0.1
            reasons.append("Contains decision")
        
        # Reduce for likely duplicates
        if any(x in candidate_lower for x in ['as mentioned', 'like before', 'again']):
            score_adjustment -= 0.1
            reasons.append("Likely references existing info")
        
        return {
            "adjustment": score_adjustment,
            "reasons": reasons,
            "mentions_known": mentions_known,
        }
    
    async def consolidate_smart(
        self,
        candidates: List[str],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Smart consolidation with deduplication.
        
        Returns stats on what was kept/skipped.
        """
        # Build index of existing memories
        self._build_existing_index()
        existing_knowledge = self._load_existing_memory()
        
        results = {
            "total": len(candidates),
            "kept": [],
            "duplicates": [],
            "low_value": [],
        }
        
        for candidate in candidates:
            # Check for duplicates
            is_dup, similar = self.is_duplicate(candidate)
            
            if is_dup:
                results["duplicates"].append({
                    "content": candidate[:100],
                    "similar_to": similar,
                })
                continue
            
            # Score with context
            context_score = self.score_with_context(candidate, existing_knowledge)
            
            # Base score (simple heuristic)
            base_score = 0.5
            if any(x in candidate.lower() for x in ['important', 'lesson', 'decision', 'api key']):
                base_score = 0.8
            elif any(x in candidate.lower() for x in ['built', 'created', 'completed']):
                base_score = 0.7
            
            final_score = base_score + context_score["adjustment"]
            
            if final_score >= 0.6:
                results["kept"].append({
                    "content": candidate,
                    "score": final_score,
                    "reasons": context_score["reasons"],
                })
            else:
                results["low_value"].append({
                    "content": candidate[:100],
                    "score": final_score,
                })
        
        # Actually write if not dry run
        if not dry_run and results["kept"]:
            await self._write_to_memory(results["kept"])
        
        return {
            "total": results["total"],
            "kept": len(results["kept"]),
            "duplicates": len(results["duplicates"]),
            "low_value": len(results["low_value"]),
            "details": results if dry_run else None,
        }
    
    async def _write_to_memory(self, items: List[Dict]):
        """Write kept items to STAGING.md for manual review.
        
        MEMORY.md is now manually curated, not auto-appended.
        """
        content = f"\n\n---\n*Smart consolidation: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
        
        for item in items[:15]:  # Limit per run
            text = item["content"][:300]
            if item["reasons"]:
                content += f"\n- {text}"
            else:
                content += f"\n- {text}"
        
        # Write to staging file, not MEMORY.md
        staging_file = self.workspace / "memory" / "STAGING.md"
        staging_file.parent.mkdir(parents=True, exist_ok=True)
        with open(staging_file, 'a') as f:
            f.write(content)
        print(f"[smart_consolidation] Wrote {len(items)} items to STAGING.md for review")


async def test_smart_consolidation():
    """Test the smart consolidator."""
    consolidator = SmartConsolidator()
    
    test_candidates = [
        "User has set a goal for the AI",  # Likely duplicate
        "ATLAS completed Brain v2 with 5 phases today",  # New info
        "The weather in Chicago is cold",  # Low value
        "LESSON: Always check for duplicates before promoting memories",  # High value
        "User prefers Fahrenheit over Celsius",  # Likely duplicate
    ]
    
    print("Testing smart consolidation...\n")
    result = await consolidator.consolidate_smart(test_candidates, dry_run=True)
    
    print(f"Total: {result['total']}")
    print(f"Kept: {result['kept']}")
    print(f"Duplicates: {result['duplicates']}")
    print(f"Low value: {result['low_value']}")
    
    if result.get('details'):
        print("\nDetails:")
        for item in result['details']['kept']:
            print(f"  ✅ {item['content'][:50]}... (score: {item['score']:.2f})")
        for item in result['details']['duplicates']:
            print(f"  🔄 {item['content'][:50]}... (similar to existing)")


if __name__ == "__main__":
    asyncio.run(test_smart_consolidation())
