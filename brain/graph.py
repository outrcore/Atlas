"""
Entity Graph Store - UMA Phase 1

SQLite-based knowledge graph for storing entities and relationships.
Part of the Unified Memory Architecture (UMA).

Created: 2026-02-06 (Nightly Build)
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class NodeType(Enum):
    PERSON = "person"
    PROJECT = "project"
    DECISION = "decision"
    CONCEPT = "concept"
    DATE = "date"
    TOOL = "tool"
    LOCATION = "location"
    EVENT = "event"


class EdgeType(Enum):
    CREATED = "created"
    DECIDED = "decided"
    WORKS_ON = "works_on"
    MENTIONED_IN = "mentioned_in"
    RELATED_TO = "related_to"
    HAPPENED_ON = "happened_on"
    LOCATED_IN = "located_in"
    COLLABORATED_WITH = "collaborated_with"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"


@dataclass
class Node:
    id: str
    type: str
    name: str
    metadata: Dict[str, Any]
    importance: float = 0.5
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    created_at: Optional[datetime] = None
    decay_score: float = 1.0


@dataclass
class Edge:
    id: str
    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0
    evidence: Optional[str] = None
    created_at: Optional[datetime] = None


class EntityGraph:
    """SQLite-based entity graph for UMA."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "graph.db"
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Nodes table
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    metadata JSON,
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    decay_score REAL DEFAULT 1.0
                );
                
                -- Edges table
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT REFERENCES nodes(id),
                    target_id TEXT REFERENCES nodes(id),
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    evidence TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_id, target_id, relation)
                );
                
                -- Memory links (connect graph to vector chunks)
                CREATE TABLE IF NOT EXISTS memory_links (
                    node_id TEXT REFERENCES nodes(id),
                    chunk_id TEXT,
                    relevance REAL DEFAULT 1.0,
                    PRIMARY KEY (node_id, chunk_id)
                );
                
                -- Contradictions tracking
                CREATE TABLE IF NOT EXISTS contradictions (
                    id TEXT PRIMARY KEY,
                    memory_a TEXT,
                    memory_b TEXT,
                    conflict_type TEXT,
                    resolution TEXT,
                    resolved_at TIMESTAMP
                );
                
                -- Indexes for fast lookups
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
                CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
            """)
    
    # ─────────────────────────────────────────────────────────────
    # Node CRUD
    # ─────────────────────────────────────────────────────────────
    
    def add_node(
        self,
        type: str,
        name: str,
        metadata: Optional[Dict] = None,
        importance: float = 0.5,
        node_id: Optional[str] = None
    ) -> str:
        """Add a node to the graph. Returns node ID."""
        node_id = node_id or str(uuid.uuid4())[:8]
        metadata = metadata or {}
        
        with sqlite3.connect(self.db_path) as conn:
            # Check for existing node with same type+name
            existing = conn.execute(
                "SELECT id FROM nodes WHERE type = ? AND name = ?",
                (type, name)
            ).fetchone()
            
            if existing:
                # Update existing node
                conn.execute("""
                    UPDATE nodes 
                    SET metadata = json_patch(metadata, ?),
                        importance = MAX(importance, ?),
                        access_count = access_count + 1,
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (json.dumps(metadata), importance, existing[0]))
                return existing[0]
            
            # Insert new node
            conn.execute("""
                INSERT INTO nodes (id, type, name, metadata, importance)
                VALUES (?, ?, ?, ?, ?)
            """, (node_id, type, name, json.dumps(metadata), importance))
            
        return node_id
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            
            if row:
                return Node(
                    id=row['id'],
                    type=row['type'],
                    name=row['name'],
                    metadata=json.loads(row['metadata'] or '{}'),
                    importance=row['importance'],
                    access_count=row['access_count'],
                    last_accessed=row['last_accessed'],
                    created_at=row['created_at'],
                    decay_score=row['decay_score']
                )
        return None
    
    def find_node(self, type: str, name: str) -> Optional[Node]:
        """Find a node by type and name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM nodes WHERE type = ? AND name = ?",
                (type, name)
            ).fetchone()
            
            if row:
                return Node(
                    id=row['id'],
                    type=row['type'],
                    name=row['name'],
                    metadata=json.loads(row['metadata'] or '{}'),
                    importance=row['importance'],
                    access_count=row['access_count'],
                    last_accessed=row['last_accessed'],
                    created_at=row['created_at'],
                    decay_score=row['decay_score']
                )
        return None
    
    def search_nodes(
        self,
        query: str,
        type: Optional[str] = None,
        limit: int = 10
    ) -> List[Node]:
        """Search nodes by name (fuzzy match)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if type:
                rows = conn.execute("""
                    SELECT * FROM nodes 
                    WHERE type = ? AND name LIKE ?
                    ORDER BY importance DESC, access_count DESC
                    LIMIT ?
                """, (type, f"%{query}%", limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM nodes 
                    WHERE name LIKE ?
                    ORDER BY importance DESC, access_count DESC
                    LIMIT ?
                """, (f"%{query}%", limit)).fetchall()
            
            return [Node(
                id=r['id'],
                type=r['type'],
                name=r['name'],
                metadata=json.loads(r['metadata'] or '{}'),
                importance=r['importance'],
                access_count=r['access_count'],
                last_accessed=r['last_accessed'],
                created_at=r['created_at'],
                decay_score=r['decay_score']
            ) for r in rows]
    
    def update_node(
        self,
        node_id: str,
        metadata: Optional[Dict] = None,
        importance: Optional[float] = None
    ):
        """Update a node's metadata or importance."""
        with sqlite3.connect(self.db_path) as conn:
            if metadata:
                conn.execute("""
                    UPDATE nodes 
                    SET metadata = json_patch(metadata, ?)
                    WHERE id = ?
                """, (json.dumps(metadata), node_id))
            
            if importance is not None:
                conn.execute("""
                    UPDATE nodes SET importance = ? WHERE id = ?
                """, (importance, node_id))
    
    def delete_node(self, node_id: str):
        """Delete a node and its edges."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?", 
                        (node_id, node_id))
            conn.execute("DELETE FROM memory_links WHERE node_id = ?", (node_id,))
            conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
    
    def touch_node(self, node_id: str):
        """Update access count and last_accessed timestamp."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE nodes 
                SET access_count = access_count + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (node_id,))
    
    # ─────────────────────────────────────────────────────────────
    # Edge CRUD
    # ─────────────────────────────────────────────────────────────
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
        evidence: Optional[str] = None
    ) -> str:
        """Add an edge between two nodes. Returns edge ID."""
        edge_id = str(uuid.uuid4())[:8]
        
        with sqlite3.connect(self.db_path) as conn:
            # Check for existing edge
            existing = conn.execute("""
                SELECT id, weight FROM edges 
                WHERE source_id = ? AND target_id = ? AND relation = ?
            """, (source_id, target_id, relation)).fetchone()
            
            if existing:
                # Strengthen existing edge (Hebbian: edges that fire together...)
                new_weight = min(existing[1] + 0.1, 2.0)
                conn.execute("""
                    UPDATE edges SET weight = ?, evidence = COALESCE(?, evidence)
                    WHERE id = ?
                """, (new_weight, evidence, existing[0]))
                return existing[0]
            
            # Insert new edge
            conn.execute("""
                INSERT INTO edges (id, source_id, target_id, relation, weight, evidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (edge_id, source_id, target_id, relation, weight, evidence))
            
        return edge_id
    
    def get_edges(
        self,
        node_id: str,
        direction: str = "both",
        relation: Optional[str] = None
    ) -> List[Edge]:
        """Get edges connected to a node."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if direction == "outgoing":
                query = "SELECT * FROM edges WHERE source_id = ?"
                params = [node_id]
            elif direction == "incoming":
                query = "SELECT * FROM edges WHERE target_id = ?"
                params = [node_id]
            else:  # both
                query = "SELECT * FROM edges WHERE source_id = ? OR target_id = ?"
                params = [node_id, node_id]
            
            if relation:
                query += " AND relation = ?"
                params.append(relation)
            
            rows = conn.execute(query, params).fetchall()
            
            return [Edge(
                id=r['id'],
                source_id=r['source_id'],
                target_id=r['target_id'],
                relation=r['relation'],
                weight=r['weight'],
                evidence=r['evidence'],
                created_at=r['created_at']
            ) for r in rows]
    
    def delete_edge(self, edge_id: str):
        """Delete an edge."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
    
    # ─────────────────────────────────────────────────────────────
    # Graph Traversal
    # ─────────────────────────────────────────────────────────────
    
    def get_neighbors(
        self,
        node_id: str,
        depth: int = 1,
        relation: Optional[str] = None
    ) -> List[Tuple[Node, Edge, int]]:
        """Get neighboring nodes up to a certain depth.
        Returns list of (node, connecting_edge, depth) tuples.
        """
        visited = {node_id}
        results = []
        current_level = [node_id]
        
        for d in range(1, depth + 1):
            next_level = []
            
            for nid in current_level:
                edges = self.get_edges(nid, direction="both", relation=relation)
                
                for edge in edges:
                    # Get the other node
                    other_id = edge.target_id if edge.source_id == nid else edge.source_id
                    
                    if other_id not in visited:
                        visited.add(other_id)
                        node = self.get_node(other_id)
                        if node:
                            results.append((node, edge, d))
                            next_level.append(other_id)
            
            current_level = next_level
        
        return results
    
    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5
    ) -> Optional[List[Tuple[Node, Edge]]]:
        """Find shortest path between two nodes using BFS."""
        if source_id == target_id:
            return []
        
        visited = {source_id}
        queue = [(source_id, [])]  # (current_node, path)
        
        while queue:
            current_id, path = queue.pop(0)
            
            if len(path) >= max_depth:
                continue
            
            edges = self.get_edges(current_id, direction="both")
            
            for edge in edges:
                other_id = edge.target_id if edge.source_id == current_id else edge.source_id
                
                if other_id == target_id:
                    node = self.get_node(other_id)
                    return path + [(node, edge)]
                
                if other_id not in visited:
                    visited.add(other_id)
                    node = self.get_node(other_id)
                    if node:
                        queue.append((other_id, path + [(node, edge)]))
        
        return None
    
    # ─────────────────────────────────────────────────────────────
    # Memory Links
    # ─────────────────────────────────────────────────────────────
    
    def link_memory(self, node_id: str, chunk_id: str, relevance: float = 1.0):
        """Link a node to a vector DB chunk."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_links (node_id, chunk_id, relevance)
                VALUES (?, ?, ?)
            """, (node_id, chunk_id, relevance))
    
    def get_linked_chunks(self, node_id: str) -> List[Tuple[str, float]]:
        """Get vector chunks linked to a node."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT chunk_id, relevance FROM memory_links
                WHERE node_id = ? ORDER BY relevance DESC
            """, (node_id,)).fetchall()
            return [(r[0], r[1]) for r in rows]
    
    def get_nodes_for_chunk(self, chunk_id: str) -> List[Tuple[str, float]]:
        """Get nodes linked to a vector chunk."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT node_id, relevance FROM memory_links
                WHERE chunk_id = ? ORDER BY relevance DESC
            """, (chunk_id,)).fetchall()
            return [(r[0], r[1]) for r in rows]
    
    # ─────────────────────────────────────────────────────────────
    # Maintenance
    # ─────────────────────────────────────────────────────────────
    
    def apply_decay(self, decay_rate: float = 0.01):
        """Apply decay to all nodes based on time since last access."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE nodes
                SET decay_score = MAX(0.1, decay_score - ? * 
                    (julianday('now') - julianday(COALESCE(last_accessed, created_at))))
                WHERE last_accessed IS NOT NULL OR created_at IS NOT NULL
            """, (decay_rate,))
    
    def boost_node(self, node_id: str, boost: float = 0.1):
        """Boost a node's decay score (Hebbian reinforcement)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE nodes
                SET decay_score = MIN(2.0, decay_score + ?)
                WHERE id = ?
            """, (boost, node_id))
    
    # ─────────────────────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        with sqlite3.connect(self.db_path) as conn:
            node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            
            type_counts = dict(conn.execute("""
                SELECT type, COUNT(*) FROM nodes GROUP BY type
            """).fetchall())
            
            relation_counts = dict(conn.execute("""
                SELECT relation, COUNT(*) FROM edges GROUP BY relation
            """).fetchall())
            
            return {
                "nodes": node_count,
                "edges": edge_count,
                "node_types": type_counts,
                "edge_types": relation_counts
            }
    
    def visualize_ascii(self, center_node_id: str, depth: int = 1) -> str:
        """Generate ASCII visualization of graph around a node."""
        center = self.get_node(center_node_id)
        if not center:
            return f"Node {center_node_id} not found"
        
        lines = [f"[{center.type}] {center.name}"]
        
        neighbors = self.get_neighbors(center_node_id, depth=depth)
        for node, edge, d in neighbors:
            indent = "  " * d
            arrow = "→" if edge.source_id == center_node_id else "←"
            lines.append(f"{indent}{arrow} ({edge.relation}) [{node.type}] {node.name}")
        
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# CLI for testing
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    graph = EntityGraph()
    
    if len(sys.argv) < 2:
        print("Usage: python graph.py [stats|add|search|viz] ...")
        print("\nCommands:")
        print("  stats              - Show graph statistics")
        print("  add <type> <name>  - Add a node")
        print("  search <query>     - Search nodes")
        print("  viz <node_id>      - Visualize around a node")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "stats":
        stats = graph.get_stats()
        print(f"Nodes: {stats['nodes']}")
        print(f"Edges: {stats['edges']}")
        print(f"Node types: {stats['node_types']}")
        print(f"Edge types: {stats['edge_types']}")
    
    elif cmd == "add" and len(sys.argv) >= 4:
        node_type = sys.argv[2]
        name = " ".join(sys.argv[3:])
        node_id = graph.add_node(node_type, name)
        print(f"Added node: {node_id}")
    
    elif cmd == "search" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        nodes = graph.search_nodes(query)
        for n in nodes:
            print(f"[{n.type}] {n.name} (id={n.id}, importance={n.importance})")
    
    elif cmd == "viz" and len(sys.argv) >= 3:
        node_id = sys.argv[2]
        print(graph.visualize_ascii(node_id, depth=2))
    
    else:
        print(f"Unknown command: {cmd}")
