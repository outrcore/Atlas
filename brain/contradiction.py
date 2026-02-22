"""
Contradiction Detection - UMA Enhancement

Detects and resolves conflicting facts about the same entity.
When a new fact contradicts an existing one, the newer fact wins
and the old one is marked as superseded.

Created: 2026-02-06
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

try:
    from .graph import EntityGraph
    from .embedder import get_embedder
except ImportError:
    from graph import EntityGraph
    from embedder import get_embedder


@dataclass
class Contradiction:
    """A detected contradiction between two facts."""
    id: str
    entity: str               # The entity they're about
    old_fact: str             # The existing fact
    new_fact: str             # The incoming fact
    old_node_id: str          # Graph node ID of old fact
    new_node_id: str          # Graph node ID of new fact (if created)
    similarity: float         # How similar the two facts are (high = likely contradiction)
    conflict_type: str        # "update" (clear replacement) or "ambiguous" (genuinely unclear)
    resolution: str           # "superseded" or "flagged"
    resolved_at: Optional[datetime] = None


# Relation verbs that indicate factual claims (not just mentions)
FACTUAL_RELATIONS = {
    "decided", "uses", "chose", "set", "configured",
    "works_on", "created", "built", "deployed", "runs_on",
    "costs", "pays", "charges", "located_in", "lives_in",
}

# Minimum similarity to consider as potential contradiction
CONTRADICTION_THRESHOLD = 0.80

# Minimum similarity to auto-resolve (clear update, not ambiguous)
AUTO_RESOLVE_THRESHOLD = 0.90


class ContradictionDetector:
    """
    Detect conflicting facts about the same entity in the graph.
    
    Strategy:
    1. When a new decision/fact node is added, find existing decisions
       about the same entity
    2. Use embeddings to compare semantic similarity
    3. High similarity + different content = contradiction
    4. Auto-resolve clear updates, flag ambiguous ones
    """
    
    def __init__(self, graph: Optional[EntityGraph] = None):
        self.graph = graph or EntityGraph()
        self._embedder = None
    
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder
    
    def check_new_fact(
        self,
        entity_name: str,
        new_fact: str,
        new_node_id: str = "",
        source: str = "",
    ) -> List[Contradiction]:
        """
        Check if a new fact contradicts existing facts about an entity.
        
        Args:
            entity_name: The entity the fact is about
            new_fact: The new fact/decision text
            new_node_id: Graph node ID of the new fact
            source: Where the new fact came from
            
        Returns:
            List of detected contradictions (empty if none)
        """
        contradictions = []
        
        # Find existing decision/fact nodes related to this entity
        existing_facts = self._find_related_facts(entity_name)
        
        if not existing_facts:
            return []
        
        # Determine date of new fact
        new_date = self._extract_date(source) or datetime.now().strftime("%Y-%m-%d")
        
        # Embed the new fact
        new_embedding = self.embedder.embed(new_fact)
        
        for old_node_id, old_fact, old_date in existing_facts:
            # Skip self-comparison
            if old_node_id == new_node_id:
                continue
            
            # Skip if facts are identical (not a contradiction, just a duplicate)
            if old_fact.strip().lower() == new_fact.strip().lower():
                continue
            
            # Compare embeddings
            old_embedding = self.embedder.embed(old_fact)
            similarity = float(self.embedder.cosine_similarity(new_embedding, old_embedding))
            
            # Same-day filter: high similarity on the same day = corroboration, not contradiction
            # This handles the instruction→completion pattern (User asks, ATLAS confirms)
            if old_date and new_date and old_date == new_date and similarity >= CONTRADICTION_THRESHOLD:
                continue
            
            if similarity >= CONTRADICTION_THRESHOLD:
                # High semantic similarity but different text = potential contradiction
                conflict_type = "update" if similarity >= AUTO_RESOLVE_THRESHOLD else "ambiguous"
                resolution = "superseded" if conflict_type == "update" else "flagged"
                
                contradiction = Contradiction(
                    id=str(uuid.uuid4())[:8],
                    entity=entity_name,
                    old_fact=old_fact,
                    new_fact=new_fact,
                    old_node_id=old_node_id,
                    new_node_id=new_node_id,
                    similarity=similarity,
                    conflict_type=conflict_type,
                    resolution=resolution,
                    resolved_at=datetime.now() if conflict_type == "update" else None,
                )
                contradictions.append(contradiction)
                
                # Auto-resolve clear updates
                if conflict_type == "update":
                    self._resolve_contradiction(contradiction)
        
        return contradictions
    
    def check_decisions(
        self,
        decisions: List[Dict[str, Any]],
        entity_names: List[str],
        source: str = "",
    ) -> List[Contradiction]:
        """
        Batch check a list of new decisions against existing graph.
        Called during extraction pipeline.
        
        Args:
            decisions: List of decision dicts with 'name' and optionally 'id'
            entity_names: Entity names these decisions relate to
            source: Source of the new decisions
            
        Returns:
            All contradictions found
        """
        all_contradictions = []
        
        for decision in decisions:
            fact_text = decision.get("name", decision.get("full_text", ""))
            node_id = decision.get("id", "")
            
            if not fact_text or len(fact_text) < 10:
                continue
            
            # Check against each related entity
            for entity in entity_names:
                contradictions = self.check_new_fact(
                    entity_name=entity,
                    new_fact=fact_text,
                    new_node_id=node_id,
                    source=source,
                )
                all_contradictions.extend(contradictions)
        
        return all_contradictions
    
    def _find_related_facts(self, entity_name: str) -> List[Tuple[str, str, str]]:
        """
        Find existing decision/fact nodes related to an entity.
        Uses two strategies:
        1. Graph edges (if decisions are linked to entity)
        2. Text matching (if decision name mentions entity)
        Returns list of (node_id, fact_text, created_date) tuples.
        created_date is YYYY-MM-DD string or "" if unknown.
        """
        import sqlite3
        
        results = []
        seen_ids = set()
        
        with sqlite3.connect(self.graph.db_path) as conn:
            # Strategy 1: Find via graph edges
            entity_rows = conn.execute(
                "SELECT id FROM nodes WHERE LOWER(name) = LOWER(?) LIMIT 1",
                (entity_name,)
            ).fetchall()
            
            if entity_rows:
                entity_id = entity_rows[0][0]
                decision_rows = conn.execute("""
                    SELECT DISTINCT n.id, n.name, n.metadata, n.created_at
                    FROM nodes n
                    JOIN edges e ON (
                        (e.source_id = n.id AND e.target_id = ?)
                        OR (e.target_id = n.id AND e.source_id = ?)
                    )
                    WHERE n.type = 'decision'
                    AND n.decay_score > 0.1
                    ORDER BY n.created_at DESC
                    LIMIT 50
                """, (entity_id, entity_id)).fetchall()
                
                for row in decision_rows:
                    node_id, name = row[0], row[1]
                    metadata = json.loads(row[2]) if row[2] else {}
                    created_at = row[3] or ""
                    fact_text = metadata.get("full_text", name)
                    # Extract date from source or created_at
                    source = metadata.get("source", "")
                    date = self._extract_date(source) or created_at[:10]
                    if node_id not in seen_ids:
                        results.append((node_id, fact_text, date))
                        seen_ids.add(node_id)
            
            # Strategy 2: Text matching - decisions that mention the entity
            entity_lower = entity_name.lower()
            if len(entity_lower) >= 3:  # Skip very short names
                decision_rows = conn.execute("""
                    SELECT id, name, metadata, created_at
                    FROM nodes
                    WHERE type = 'decision'
                    AND decay_score > 0.1
                    AND LOWER(name) LIKE ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (f"%{entity_lower}%",)).fetchall()
                
                for row in decision_rows:
                    node_id, name = row[0], row[1]
                    metadata = json.loads(row[2]) if row[2] else {}
                    created_at = row[3] or ""
                    fact_text = metadata.get("full_text", name)
                    source = metadata.get("source", "")
                    date = self._extract_date(source) or created_at[:10]
                    if node_id not in seen_ids:
                        results.append((node_id, fact_text, date))
                        seen_ids.add(node_id)
        
        return results
    
    @staticmethod
    def _extract_date(source: str) -> str:
        """Extract YYYY-MM-DD from a source string like 'memory/2026-02-06.md'."""
        import re
        match = re.search(r'(\d{4}-\d{2}-\d{2})', source)
        return match.group(1) if match else ""
    
    def _resolve_contradiction(self, contradiction: Contradiction):
        """
        Resolve a contradiction by superseding the old fact.
        - Reduces old node's decay_score
        - Adds SUPERSEDES edge from new to old
        - Records in contradictions table
        """
        import sqlite3
        
        with sqlite3.connect(self.graph.db_path) as conn:
            # Reduce old node's importance and decay
            conn.execute("""
                UPDATE nodes 
                SET decay_score = decay_score * 0.3,
                    importance = importance * 0.5
                WHERE id = ?
            """, (contradiction.old_node_id,))
            
            # Add supersedes edge (if both nodes exist)
            if contradiction.new_node_id and contradiction.old_node_id:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO edges (id, source_id, target_id, relation, weight, evidence)
                        VALUES (?, ?, ?, 'supersedes', 1.0, ?)
                    """, (
                        str(uuid.uuid4())[:8],
                        contradiction.new_node_id,
                        contradiction.old_node_id,
                        f"Superseded: {contradiction.old_fact[:100]}"
                    ))
                except sqlite3.IntegrityError:
                    pass
            
            # Record in contradictions table
            conn.execute("""
                INSERT OR IGNORE INTO contradictions (id, memory_a, memory_b, conflict_type, resolution, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                contradiction.id,
                contradiction.old_fact[:500],
                contradiction.new_fact[:500],
                contradiction.conflict_type,
                contradiction.resolution,
                contradiction.resolved_at.isoformat() if contradiction.resolved_at else None,
            ))
    
    def get_unresolved(self) -> List[Dict[str, Any]]:
        """Get all unresolved (ambiguous) contradictions."""
        import sqlite3
        
        with sqlite3.connect(self.graph.db_path) as conn:
            rows = conn.execute("""
                SELECT id, memory_a, memory_b, conflict_type, resolution
                FROM contradictions
                WHERE resolved_at IS NULL
                ORDER BY rowid DESC
                LIMIT 20
            """).fetchall()
        
        return [
            {
                "id": r[0],
                "old_fact": r[1],
                "new_fact": r[2],
                "conflict_type": r[3],
                "resolution": r[4],
            }
            for r in rows
        ]
    
    def resolve(self, contradiction_id: str, keep: str = "new"):
        """
        Manually resolve an ambiguous contradiction.
        keep: "new" (default) or "old"
        """
        import sqlite3
        
        with sqlite3.connect(self.graph.db_path) as conn:
            conn.execute("""
                UPDATE contradictions
                SET resolution = ?, resolved_at = ?
                WHERE id = ?
            """, (
                f"manual:{keep}",
                datetime.now().isoformat(),
                contradiction_id,
            ))
    
    def scan_all(self, entity_name: Optional[str] = None) -> List[Contradiction]:
        """
        Scan existing graph for contradictions among existing facts.
        Useful for initial audit.
        
        Args:
            entity_name: Optional - scan only this entity. None = scan all.
        """
        import sqlite3
        
        all_contradictions = []
        
        with sqlite3.connect(self.graph.db_path) as conn:
            if entity_name:
                entities = [(entity_name,)]
            else:
                # Get all non-decision, non-date entities
                entities = conn.execute("""
                    SELECT DISTINCT name
                    FROM nodes
                    WHERE type IN ('project', 'person', 'tool', 'concept')
                    AND LENGTH(name) >= 3
                    ORDER BY importance DESC
                    LIMIT 50
                """).fetchall()
        
        for (name,) in entities:
            facts = self._find_related_facts(name)
            if len(facts) < 2:
                continue
            
            # Compare all pairs (cross-day only)
            for i in range(len(facts)):
                for j in range(i + 1, len(facts)):
                    id_a, fact_a, date_a = facts[i]
                    id_b, fact_b, date_b = facts[j]
                    
                    if fact_a.strip().lower() == fact_b.strip().lower():
                        continue
                    
                    similarity = self.embedder.similarity(fact_a, fact_b)
                    
                    # Same-day filter: corroboration, not contradiction
                    if date_a and date_b and date_a == date_b and similarity >= CONTRADICTION_THRESHOLD:
                        continue
                    
                    if similarity >= CONTRADICTION_THRESHOLD:
                        conflict_type = "update" if similarity >= AUTO_RESOLVE_THRESHOLD else "ambiguous"
                        
                        contradiction = Contradiction(
                            id=str(uuid.uuid4())[:8],
                            entity=name,
                            old_fact=fact_a,
                            new_fact=fact_b,
                            old_node_id=id_a,
                            new_node_id=id_b,
                            similarity=similarity,
                            conflict_type=conflict_type,
                            resolution="flagged",
                        )
                        all_contradictions.append(contradiction)
        
        return all_contradictions


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    detector = ContradictionDetector()
    
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        entity = sys.argv[2] if len(sys.argv) > 2 else None
        print(f"Scanning{'  ' + entity if entity else ' all entities'} for contradictions...")
        
        contradictions = detector.scan_all(entity)
        
        if not contradictions:
            print("No contradictions found.")
        else:
            print(f"\nFound {len(contradictions)} potential contradictions:\n")
            for c in contradictions:
                print(f"  Entity: {c.entity}")
                print(f"  Old:    {c.old_fact[:80]}")
                print(f"  New:    {c.new_fact[:80]}")
                print(f"  Sim:    {c.similarity:.3f} ({c.conflict_type})")
                print()
    
    elif len(sys.argv) > 1 and sys.argv[1] == "unresolved":
        unresolved = detector.get_unresolved()
        if not unresolved:
            print("No unresolved contradictions.")
        else:
            for u in unresolved:
                print(f"  [{u['id']}] {u['conflict_type']}")
                print(f"    A: {u['old_fact'][:80]}")
                print(f"    B: {u['new_fact'][:80]}")
                print()
    
    else:
        print("Usage:")
        print("  python contradiction.py scan [entity]  - Scan for contradictions")
        print("  python contradiction.py unresolved      - Show unresolved")
