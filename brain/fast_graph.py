"""
Fast Graph - In-memory graph with NetworkX for fast traversal.

Hybrid approach:
- SQLite for persistence (source of truth)
- NetworkX for fast traversal (in-memory cache)

Created: 2026-02-06
"""

import networkx as nx
from typing import Optional, List, Dict, Any, Tuple, Set
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import json

try:
    from .graph import EntityGraph, Node, Edge
except ImportError:
    from graph import EntityGraph, Node, Edge


class FastGraph:
    """
    In-memory graph cache backed by SQLite.
    
    Uses NetworkX for O(1) traversal instead of O(n²) SQL queries.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        # SQLite backend for persistence
        self.sqlite_graph = EntityGraph(db_path)
        self.db_path = self.sqlite_graph.db_path
        
        # NetworkX in-memory graph
        self.nx_graph = nx.DiGraph()
        
        # Node data cache
        self._node_cache: Dict[str, Node] = {}
        
        # Load from SQLite on init
        self._load_from_sqlite()
    
    def _load_from_sqlite(self):
        """Load entire graph into memory from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Load all nodes
            nodes = conn.execute("SELECT * FROM nodes").fetchall()
            for row in nodes:
                node = Node(
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
                self._node_cache[node.id] = node
                self.nx_graph.add_node(
                    node.id,
                    type=node.type,
                    name=node.name,
                    importance=node.importance
                )
            
            # Load all edges
            edges = conn.execute("SELECT * FROM edges").fetchall()
            for row in edges:
                self.nx_graph.add_edge(
                    row['source_id'],
                    row['target_id'],
                    relation=row['relation'],
                    weight=row['weight'],
                    evidence=row['evidence'],
                    edge_id=row['id']
                )
        
        print(f"[FastGraph] Loaded {self.nx_graph.number_of_nodes()} nodes, " +
              f"{self.nx_graph.number_of_edges()} edges into memory")
    
    def reload(self):
        """Reload graph from SQLite."""
        self.nx_graph.clear()
        self._node_cache.clear()
        self._load_from_sqlite()
    
    # ─────────────────────────────────────────────────────────────
    # Node operations (write-through to SQLite)
    # ─────────────────────────────────────────────────────────────
    
    def add_node(
        self,
        type: str,
        name: str,
        metadata: Optional[Dict] = None,
        importance: float = 0.5,
        node_id: Optional[str] = None
    ) -> str:
        """Add node to both SQLite and memory."""
        # Write to SQLite
        node_id = self.sqlite_graph.add_node(type, name, metadata, importance, node_id)
        
        # Update memory
        node = self.sqlite_graph.get_node(node_id)
        if node:
            self._node_cache[node_id] = node
            self.nx_graph.add_node(
                node_id,
                type=type,
                name=name,
                importance=importance
            )
        
        return node_id
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get node from cache (O(1))."""
        return self._node_cache.get(node_id)
    
    def find_node(self, type: str, name: str) -> Optional[Node]:
        """Find node by type and name (O(n) but fast in memory)."""
        for node in self._node_cache.values():
            if node.type == type and node.name == name:
                return node
        return None
    
    def search_nodes(
        self,
        query: str,
        type: Optional[str] = None,
        limit: int = 10
    ) -> List[Node]:
        """Search nodes by name (fuzzy match)."""
        query_lower = query.lower()
        results = []
        
        for node in self._node_cache.values():
            if type and node.type != type:
                continue
            if query_lower in node.name.lower():
                results.append(node)
        
        # Sort by importance
        results.sort(key=lambda n: n.importance, reverse=True)
        return results[:limit]
    
    # ─────────────────────────────────────────────────────────────
    # Edge operations (write-through to SQLite)
    # ─────────────────────────────────────────────────────────────
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
        evidence: Optional[str] = None
    ) -> str:
        """Add edge to both SQLite and memory."""
        # Write to SQLite
        edge_id = self.sqlite_graph.add_edge(source_id, target_id, relation, weight, evidence)
        
        # Update memory
        self.nx_graph.add_edge(
            source_id,
            target_id,
            relation=relation,
            weight=weight,
            evidence=evidence,
            edge_id=edge_id
        )
        
        return edge_id
    
    def get_edges(
        self,
        node_id: str,
        direction: str = "both",
        relation: Optional[str] = None
    ) -> List[Edge]:
        """Get edges for a node (O(degree) - very fast)."""
        edges = []
        
        # Outgoing edges
        if direction in ("both", "outgoing"):
            for _, target, data in self.nx_graph.out_edges(node_id, data=True):
                if relation and data.get('relation') != relation:
                    continue
                edges.append(Edge(
                    id=data.get('edge_id', ''),
                    source_id=node_id,
                    target_id=target,
                    relation=data.get('relation', ''),
                    weight=data.get('weight', 1.0),
                    evidence=data.get('evidence')
                ))
        
        # Incoming edges
        if direction in ("both", "incoming"):
            for source, _, data in self.nx_graph.in_edges(node_id, data=True):
                if relation and data.get('relation') != relation:
                    continue
                edges.append(Edge(
                    id=data.get('edge_id', ''),
                    source_id=source,
                    target_id=node_id,
                    relation=data.get('relation', ''),
                    weight=data.get('weight', 1.0),
                    evidence=data.get('evidence')
                ))
        
        return edges
    
    # ─────────────────────────────────────────────────────────────
    # Fast graph traversal (NetworkX)
    # ─────────────────────────────────────────────────────────────
    
    def get_neighbors(
        self,
        node_id: str,
        depth: int = 1,
        relation: Optional[str] = None
    ) -> List[Tuple[Node, Edge, int]]:
        """
        Get neighboring nodes up to depth (FAST - uses NetworkX BFS).
        
        Returns list of (node, connecting_edge, depth) tuples.
        """
        if node_id not in self.nx_graph:
            return []
        
        results = []
        visited = {node_id}
        
        # BFS using NetworkX
        for current_depth in range(1, depth + 1):
            # Get all nodes at this depth
            if current_depth == 1:
                # Direct neighbors
                neighbors_at_depth = set()
                
                # Outgoing
                for neighbor in self.nx_graph.successors(node_id):
                    if neighbor not in visited:
                        edge_data = self.nx_graph.edges[node_id, neighbor]
                        if relation and edge_data.get('relation') != relation:
                            continue
                        neighbors_at_depth.add((neighbor, node_id, neighbor))
                
                # Incoming
                for neighbor in self.nx_graph.predecessors(node_id):
                    if neighbor not in visited:
                        edge_data = self.nx_graph.edges[neighbor, node_id]
                        if relation and edge_data.get('relation') != relation:
                            continue
                        neighbors_at_depth.add((neighbor, neighbor, node_id))
                
                for neighbor_id, src, tgt in neighbors_at_depth:
                    visited.add(neighbor_id)
                    node = self._node_cache.get(neighbor_id)
                    edge_data = self.nx_graph.edges[src, tgt]
                    
                    if node:
                        edge = Edge(
                            id=edge_data.get('edge_id', ''),
                            source_id=src,
                            target_id=tgt,
                            relation=edge_data.get('relation', ''),
                            weight=edge_data.get('weight', 1.0),
                            evidence=edge_data.get('evidence')
                        )
                        results.append((node, edge, current_depth))
            else:
                # Use NetworkX BFS for deeper levels
                for n in list(visited):
                    if n == node_id:
                        continue
                    for neighbor in self.nx_graph.successors(n):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            node = self._node_cache.get(neighbor)
                            if node:
                                edge_data = self.nx_graph.edges[n, neighbor]
                                edge = Edge(
                                    id=edge_data.get('edge_id', ''),
                                    source_id=n,
                                    target_id=neighbor,
                                    relation=edge_data.get('relation', ''),
                                    weight=edge_data.get('weight', 1.0)
                                )
                                results.append((node, edge, current_depth))
        
        return results
    
    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5
    ) -> Optional[List[Tuple[Node, Edge]]]:
        """
        Find shortest path between nodes (FAST - uses NetworkX).
        
        Returns path as list of (node, edge) tuples, or None if no path.
        """
        if source_id not in self.nx_graph or target_id not in self.nx_graph:
            return None
        
        if source_id == target_id:
            return []
        
        try:
            # Use NetworkX shortest path (very fast)
            path_nodes = nx.shortest_path(
                self.nx_graph.to_undirected(),
                source_id,
                target_id
            )
            
            if len(path_nodes) - 1 > max_depth:
                return None
            
            # Convert to (Node, Edge) tuples
            result = []
            for i in range(1, len(path_nodes)):
                prev_id = path_nodes[i-1]
                curr_id = path_nodes[i]
                
                node = self._node_cache.get(curr_id)
                
                # Get edge (try both directions)
                if self.nx_graph.has_edge(prev_id, curr_id):
                    edge_data = self.nx_graph.edges[prev_id, curr_id]
                    src, tgt = prev_id, curr_id
                else:
                    edge_data = self.nx_graph.edges[curr_id, prev_id]
                    src, tgt = curr_id, prev_id
                
                edge = Edge(
                    id=edge_data.get('edge_id', ''),
                    source_id=src,
                    target_id=tgt,
                    relation=edge_data.get('relation', ''),
                    weight=edge_data.get('weight', 1.0)
                )
                
                if node:
                    result.append((node, edge))
            
            return result
            
        except nx.NetworkXNoPath:
            return None
    
    def are_connected(self, node_id1: str, node_id2: str, max_depth: int = 3) -> bool:
        """Quick check if two nodes are connected (O(1) to O(n))."""
        if node_id1 not in self.nx_graph or node_id2 not in self.nx_graph:
            return False
        
        try:
            path_length = nx.shortest_path_length(
                self.nx_graph.to_undirected(),
                node_id1,
                node_id2
            )
            return path_length <= max_depth
        except nx.NetworkXNoPath:
            return False
    
    def connection_strength(self, node_id1: str, node_id2: str) -> float:
        """
        Get connection strength between nodes (0-1).
        1.0 = direct connection, 0.5 = 2 hops, 0.25 = 3 hops, 0 = no connection
        """
        if node_id1 not in self.nx_graph or node_id2 not in self.nx_graph:
            return 0.0
        
        if node_id1 == node_id2:
            return 1.0
        
        try:
            path_length = nx.shortest_path_length(
                self.nx_graph.to_undirected(),
                node_id1,
                node_id2
            )
            # Exponential decay
            return 1.0 / (2 ** (path_length - 1))
        except nx.NetworkXNoPath:
            return 0.0
    
    # ─────────────────────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        type_counts = {}
        for node in self._node_cache.values():
            type_counts[node.type] = type_counts.get(node.type, 0) + 1
        
        relation_counts = {}
        for _, _, data in self.nx_graph.edges(data=True):
            rel = data.get('relation', 'unknown')
            relation_counts[rel] = relation_counts.get(rel, 0) + 1
        
        return {
            "nodes": self.nx_graph.number_of_nodes(),
            "edges": self.nx_graph.number_of_edges(),
            "node_types": type_counts,
            "edge_types": relation_counts,
            "in_memory": True
        }


# Singleton for easy access
_fast_graph = None

def get_fast_graph() -> FastGraph:
    """Get or create the fast graph instance."""
    global _fast_graph
    if _fast_graph is None:
        _fast_graph = FastGraph()
    return _fast_graph


# CLI test
if __name__ == "__main__":
    import time
    
    print("Testing FastGraph vs SQLite performance...\n")
    
    # Load graphs
    fast = FastGraph()
    slow = EntityGraph()
    
    stats = fast.get_stats()
    print(f"Graph: {stats['nodes']} nodes, {stats['edges']} edges\n")
    
    # Find user node
    user_node = fast.find_node('person', 'User')
    if not user_node:
        print("User not found!")
        exit(1)
    
    # Test 1: Get neighbors
    print("Test 1: Get neighbors (depth=2)")
    
    start = time.time()
    for _ in range(10):
        fast_neighbors = fast.get_neighbors(user_node.id, depth=2)
    fast_time = (time.time() - start) * 100  # ms per call
    
    start = time.time()
    for _ in range(10):
        slow_neighbors = slow.get_neighbors(user_node.id, depth=2)
    slow_time = (time.time() - start) * 100
    
    print(f"  FastGraph: {fast_time:.1f}ms (found {len(fast_neighbors)} neighbors)")
    print(f"  SQLite:    {slow_time:.1f}ms (found {len(slow_neighbors)} neighbors)")
    print(f"  Speedup:   {slow_time/fast_time:.1f}x\n")
    
    # Test 2: Find path
    project_beta = fast.find_node('project', 'ProjectBeta')
    if project_beta:
        print("Test 2: Find path (User → ProjectBeta)")
        
        start = time.time()
        for _ in range(10):
            fast_path = fast.find_path(user_node.id, project_beta.id)
        fast_time = (time.time() - start) * 100
        
        start = time.time()
        for _ in range(10):
            slow_path = slow.find_path(user_node.id, project_beta.id)
        slow_time = (time.time() - start) * 100
        
        print(f"  FastGraph: {fast_time:.1f}ms")
        print(f"  SQLite:    {slow_time:.1f}ms")
        print(f"  Speedup:   {slow_time/fast_time:.1f}x\n")
    
    # Test 3: Connection strength
    print("Test 3: Connection strength check")
    start = time.time()
    for _ in range(100):
        strength = fast.connection_strength(user_node.id, project_beta.id if project_beta else user_node.id)
    fast_time = (time.time() - start) * 10
    print(f"  FastGraph: {fast_time:.2f}ms per 100 checks")
    print(f"  Strength User→ProjectBeta: {strength}")
