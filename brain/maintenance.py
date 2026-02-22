"""
Memory Maintenance - UMA

Handles decay, Hebbian boosting, and consolidation.
Designed to run periodically via the brain daemon.

Decay philosophy (mirrors human memory):
- Facts/decisions/tools/people/projects: barely decay, floor at 0.5
- Events/mentions: moderate decay, floor at 0.1
- Dates: faster decay, floor at 0.1
- Hebbian boosting rewards nodes accessed together
- "Neurons that fire together, wire together"

Created: 2026-02-06
"""

import sqlite3
import math
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
from pathlib import Path
from collections import defaultdict

try:
    from .graph import EntityGraph
except ImportError:
    from graph import EntityGraph


# ─────────────────────────────────────────────────────────────
# Decay Configuration
# ─────────────────────────────────────────────────────────────

# Half-life in days per node type (how long until score halves)
DECAY_HALF_LIFE = {
    "person": 365,      # People barely fade
    "project": 365,     # Projects barely fade
    "tool": 365,        # Stack knowledge persists
    "decision": 180,    # Decisions are durable
    "concept": 120,     # Concepts fade slowly
    "event": 45,        # Events fade moderately
    "location": 180,    # Locations persist
    "date": 30,         # Date references fade faster
}

# Minimum decay_score per type (floor - never goes below this)
DECAY_FLOOR = {
    "person": 0.5,
    "project": 0.5,
    "tool": 0.5,
    "decision": 0.5,
    "concept": 0.3,
    "event": 0.1,
    "location": 0.3,
    "date": 0.1,
}

DEFAULT_HALF_LIFE = 90
DEFAULT_FLOOR = 0.2

# ─────────────────────────────────────────────────────────────
# Hebbian Configuration
# ─────────────────────────────────────────────────────────────

# How much to boost edge weight when co-accessed (additive)
HEBBIAN_BOOST = 0.1

# Max edge weight (prevent runaway boosting)
HEBBIAN_MAX_WEIGHT = 5.0

# How much to boost node importance on access
ACCESS_IMPORTANCE_BOOST = 0.02

# Max node importance
MAX_IMPORTANCE = 1.0


class MemoryMaintenance:
    """Background maintenance for the UMA graph."""
    
    def __init__(self, graph: Optional[EntityGraph] = None):
        self.graph = graph or EntityGraph()
        self._access_log: List[Tuple[float, List[str]]] = []  # (timestamp, [node_ids])
    
    # ─────────────────────────────────────────────────────────
    # Decay
    # ─────────────────────────────────────────────────────────
    
    def run_decay(self) -> Dict[str, int]:
        """
        Apply time-based decay to all nodes.
        Nodes not accessed recently lose decay_score, but never below their type floor.
        
        Returns stats dict.
        """
        now = datetime.now()
        decayed = 0
        skipped = 0
        at_floor = 0
        
        with sqlite3.connect(self.graph.db_path) as conn:
            rows = conn.execute("""
                SELECT id, type, decay_score, last_accessed, created_at
                FROM nodes
                WHERE decay_score > 0
            """).fetchall()
            
            for node_id, node_type, current_score, last_accessed_str, created_at_str in rows:
                # Determine last activity time
                last_active = None
                if last_accessed_str:
                    try:
                        if isinstance(last_accessed_str, (int, float)):
                            last_active = datetime.fromtimestamp(last_accessed_str, tz=now.tzinfo or None)
                        else:
                            last_active = datetime.fromisoformat(str(last_accessed_str).replace('Z', '+00:00').replace('+00:00', ''))
                    except (ValueError, TypeError, AttributeError, OSError):
                        pass
                if not last_active and created_at_str:
                    try:
                        if isinstance(created_at_str, (int, float)):
                            last_active = datetime.fromtimestamp(created_at_str, tz=now.tzinfo or None)
                        else:
                            last_active = datetime.fromisoformat(str(created_at_str).replace('Z', '+00:00').replace('+00:00', ''))
                    except (ValueError, TypeError, AttributeError, OSError):
                        last_active = now  # Fallback
                if not last_active:
                    last_active = now
                
                # Calculate days since last activity
                age_days = max(0, (now - last_active).total_seconds() / 86400)
                
                # Get type-specific half-life and floor
                half_life = DECAY_HALF_LIFE.get(node_type, DEFAULT_HALF_LIFE)
                floor = DECAY_FLOOR.get(node_type, DEFAULT_FLOOR)
                
                # Exponential decay: score = e^(-λt) where λ = ln(2)/half_life
                decay_lambda = math.log(2) / half_life
                new_score = math.exp(-decay_lambda * age_days)
                
                # Apply floor
                new_score = max(new_score, floor)
                
                # Only update if meaningfully different (avoid churn)
                if abs(new_score - current_score) > 0.01:
                    conn.execute(
                        "UPDATE nodes SET decay_score = ? WHERE id = ?",
                        (round(new_score, 4), node_id)
                    )
                    decayed += 1
                    if new_score <= floor + 0.01:
                        at_floor += 1
                else:
                    skipped += 1
        
        stats = {
            "total": len(rows) if 'rows' in dir() else 0,
            "decayed": decayed,
            "skipped": skipped,
            "at_floor": at_floor,
            "timestamp": now.isoformat(),
        }
        print(f"[maintenance] Decay: {decayed} updated, {skipped} unchanged, {at_floor} at floor")
        return stats
    
    # ─────────────────────────────────────────────────────────
    # Hebbian Boosting
    # ─────────────────────────────────────────────────────────
    
    def record_access(self, node_ids: List[str]):
        """
        Record that these nodes were accessed together (co-activation).
        Call this when search results are returned.
        """
        if len(node_ids) < 2:
            return
        
        self._access_log.append((time.time(), node_ids))
        
        # Keep log bounded
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-500:]
    
    def run_hebbian(self, node_ids: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Strengthen connections between co-accessed nodes.
        
        If node_ids provided, boost those specific nodes.
        Otherwise, process the access log.
        
        Returns stats dict.
        """
        edges_boosted = 0
        nodes_boosted = 0
        
        if node_ids:
            groups = [(node_ids,)]
        else:
            groups = [(ids,) for _, ids in self._access_log]
            self._access_log.clear()
        
        with sqlite3.connect(self.graph.db_path) as conn:
            for (ids,) in groups:
                # Boost edges between all pairs
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        # Try both directions
                        for src, tgt in [(ids[i], ids[j]), (ids[j], ids[i])]:
                            result = conn.execute("""
                                UPDATE edges 
                                SET weight = MIN(weight + ?, ?)
                                WHERE source_id = ? AND target_id = ?
                            """, (HEBBIAN_BOOST, HEBBIAN_MAX_WEIGHT, src, tgt))
                            if result.rowcount > 0:
                                edges_boosted += 1
                
                # Boost node importance and access count
                for node_id in ids:
                    conn.execute("""
                        UPDATE nodes 
                        SET access_count = access_count + 1,
                            last_accessed = ?,
                            importance = MIN(importance + ?, ?)
                        WHERE id = ?
                    """, (datetime.now().isoformat(), ACCESS_IMPORTANCE_BOOST, MAX_IMPORTANCE, node_id))
                    nodes_boosted += 1
        
        stats = {
            "edges_boosted": edges_boosted,
            "nodes_boosted": nodes_boosted,
            "timestamp": datetime.now().isoformat(),
        }
        if edges_boosted > 0 or nodes_boosted > 0:
            print(f"[maintenance] Hebbian: {edges_boosted} edges boosted, {nodes_boosted} nodes accessed")
        return stats
    
    # ─────────────────────────────────────────────────────────
    # Consolidation
    # ─────────────────────────────────────────────────────────
    
    def run_consolidation(self, similarity_threshold: float = 0.95) -> Dict[str, int]:
        """
        Merge highly similar nodes (near-duplicates).
        Keeps the node with higher importance, transfers edges from the other.
        
        Returns stats dict.
        """
        try:
            from .embedder import get_embedder
        except ImportError:
            from embedder import get_embedder
        
        embedder = get_embedder()
        merged = 0
        
        with sqlite3.connect(self.graph.db_path) as conn:
            # Get all decision nodes (most likely to have duplicates)
            rows = conn.execute("""
                SELECT id, name, importance, decay_score
                FROM nodes
                WHERE type = 'decision'
                AND decay_score > 0.1
                ORDER BY importance DESC
            """).fetchall()
            
            if len(rows) < 2:
                return {"merged": 0}
            
            # Embed all names
            names = [r[1] for r in rows]
            embeddings = embedder.embed_batch(names)
            
            # Find pairs above threshold
            merged_ids = set()
            
            for i in range(len(rows)):
                if rows[i][0] in merged_ids:
                    continue
                for j in range(i + 1, len(rows)):
                    if rows[j][0] in merged_ids:
                        continue
                    
                    sim = float(embedder.cosine_similarity(embeddings[i], embeddings[j]))
                    
                    if sim >= similarity_threshold:
                        # Keep the one with higher importance
                        keep_id = rows[i][0]
                        remove_id = rows[j][0]
                        keep_name = rows[i][1]
                        remove_name = rows[j][1]
                        
                        # Transfer edges from removed node to kept node
                        conn.execute("""
                            UPDATE OR IGNORE edges SET source_id = ? WHERE source_id = ?
                        """, (keep_id, remove_id))
                        conn.execute("""
                            UPDATE OR IGNORE edges SET target_id = ? WHERE target_id = ?
                        """, (keep_id, remove_id))
                        
                        # Delete orphaned edges (duplicates after transfer)
                        conn.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?",
                                     (remove_id, remove_id))
                        
                        # Reduce removed node's score (soft delete)
                        conn.execute("""
                            UPDATE nodes SET decay_score = 0.0, 
                                            metadata = json_set(COALESCE(metadata, '{}'), '$.merged_into', ?)
                            WHERE id = ?
                        """, (keep_id, remove_id))
                        
                        merged_ids.add(remove_id)
                        merged += 1
                        print(f"[maintenance] Consolidated: '{remove_name[:50]}' → '{keep_name[:50]}' (sim={sim:.3f})")
        
        stats = {
            "merged": merged,
            "timestamp": datetime.now().isoformat(),
        }
        if merged > 0:
            print(f"[maintenance] Consolidation: {merged} nodes merged")
        return stats
    
    # ─────────────────────────────────────────────────────────
    # Full Maintenance Run
    # ─────────────────────────────────────────────────────────
    
    def run_all(self, include_consolidation: bool = False) -> Dict[str, Any]:
        """
        Run all maintenance tasks.
        
        Args:
            include_consolidation: Whether to run consolidation (heavier, less frequent)
        """
        print(f"[maintenance] Starting full maintenance run...")
        start = time.time()
        
        results = {
            "decay": self.run_decay(),
            "hebbian": self.run_hebbian(),
        }
        
        if include_consolidation:
            results["consolidation"] = self.run_consolidation()
        
        elapsed = time.time() - start
        results["elapsed_seconds"] = round(elapsed, 2)
        print(f"[maintenance] Complete in {elapsed:.1f}s")
        
        return results


# ─────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────

_instance: Optional[MemoryMaintenance] = None

def get_maintenance() -> MemoryMaintenance:
    global _instance
    if _instance is None:
        _instance = MemoryMaintenance()
    return _instance


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json
    
    maintenance = MemoryMaintenance()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "decay":
            stats = maintenance.run_decay()
            print(json.dumps(stats, indent=2))
        
        elif cmd == "hebbian":
            # Test: boost a few known nodes
            print("No access log to process. Use 'all' for full run.")
        
        elif cmd == "consolidation":
            stats = maintenance.run_consolidation()
            print(json.dumps(stats, indent=2))
        
        elif cmd == "all":
            include_consol = "--consolidate" in sys.argv
            stats = maintenance.run_all(include_consolidation=include_consol)
            print(json.dumps(stats, indent=2))
        
        elif cmd == "stats":
            # Show current decay distribution
            import sqlite3
            db_path = Path(__file__).parent / "graph.db"
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("""
                    SELECT type, 
                           COUNT(*) as count,
                           ROUND(AVG(decay_score), 3) as avg_decay,
                           ROUND(MIN(decay_score), 3) as min_decay,
                           ROUND(AVG(importance), 3) as avg_importance,
                           SUM(access_count) as total_accesses
                    FROM nodes
                    GROUP BY type
                    ORDER BY count DESC
                """).fetchall()
                
                print(f"{'Type':<12} {'Count':>6} {'Avg Decay':>10} {'Min Decay':>10} {'Avg Imp':>8} {'Accesses':>9}")
                print("-" * 60)
                for r in rows:
                    print(f"{r[0]:<12} {r[1]:>6} {r[2]:>10} {r[3]:>10} {r[4]:>8} {r[5]:>9}")
        
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("Usage:")
        print("  python maintenance.py decay          - Run decay")
        print("  python maintenance.py consolidation   - Merge near-duplicates")
        print("  python maintenance.py all [--consolidate]  - Run all")
        print("  python maintenance.py stats           - Show decay distribution")
