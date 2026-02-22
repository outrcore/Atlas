"""
Graph RAG - Graph-based Retrieval Augmented Generation

Enhances search results using graph structure:
- Path-based relevance boosting (BFS proximity to seed nodes)
- Community detection (Louvain) for topical clustering
- PageRank centrality for importance weighting

Created: 2026-02-07
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import deque

import networkx as nx

try:
    from .fast_graph import FastGraph, get_fast_graph
except ImportError:
    from fast_graph import FastGraph, get_fast_graph

# Alias for compatibility
GraphStore = FastGraph


CACHE_PATH = Path(__file__).parent / "cache" / "graph_rag_cache.json"
CACHE_MAX_AGE_HOURS = 24

# Path boost by hop distance
HOP_BOOST = {0: 1.0, 1: 1.0, 2: 0.7, 3: 0.4}
DEFAULT_HOP_BOOST = 0.1
COMMUNITY_BOOST_VALUE = 0.3
CENTRALITY_WEIGHT = 0.2
MAX_BFS_DEPTH = 4


def compute_path_relevance(
    graph: nx.Graph,
    seed_nodes: List[str],
    max_depth: int = MAX_BFS_DEPTH
) -> Dict[str, float]:
    """
    BFS from seed nodes, assign boost based on hop distance.
    Nodes at 1 hop get 1.0, 2 hops 0.7, 3 hops 0.4, 4+ hops 0.1.
    For multiple seeds, take the max boost per node.
    """
    if not seed_nodes or graph.number_of_nodes() == 0:
        return {}

    boosts: Dict[str, float] = {}
    undirected = graph.to_undirected() if graph.is_directed() else graph

    for seed in seed_nodes:
        if seed not in undirected:
            continue
        # BFS with depth limit
        visited = {seed: 0}
        queue = deque([(seed, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for neighbor in undirected.neighbors(node):
                if neighbor not in visited:
                    d = depth + 1
                    visited[neighbor] = d
                    queue.append((neighbor, d))

        for node_id, dist in visited.items():
            boost = HOP_BOOST.get(dist, DEFAULT_HOP_BOOST)
            boosts[node_id] = max(boosts.get(node_id, 0.0), boost)

    return boosts


def detect_communities(graph: nx.Graph) -> Dict[str, int]:
    """Run Louvain community detection. Returns node_id → community_id."""
    if graph.number_of_nodes() == 0:
        return {}

    undirected = graph.to_undirected() if graph.is_directed() else graph

    try:
        communities = nx.community.louvain_communities(undirected, seed=42)
    except Exception:
        return {}

    mapping: Dict[str, int] = {}
    for idx, community in enumerate(communities):
        for node_id in community:
            mapping[node_id] = idx
    return mapping


def community_boost(seed_communities: Set[int], node_community: Optional[int]) -> float:
    """Return boost if node is in same community as any seed node."""
    if node_community is not None and node_community in seed_communities:
        return COMMUNITY_BOOST_VALUE
    return 0.0


def compute_centrality(graph: nx.Graph) -> Dict[str, float]:
    """Compute PageRank for all nodes."""
    if graph.number_of_nodes() == 0:
        return {}
    try:
        return nx.pagerank(graph, max_iter=100)
    except Exception:
        return {}


class GraphRAG:
    """
    Graph RAG manager with cached community and centrality data.
    """

    def __init__(self, graph_store: Optional[FastGraph] = None):
        self.graph_store = graph_store or get_fast_graph()
        self._communities: Dict[str, int] = {}
        self._pagerank: Dict[str, float] = {}
        self._last_computed: Optional[str] = None

    async def initialize(self):
        """Load cache or recompute if stale."""
        if not self._load_cache():
            self.recompute()

    def _load_cache(self) -> bool:
        """Load from disk cache. Returns True if valid cache loaded."""
        if not CACHE_PATH.exists():
            return False
        try:
            data = json.loads(CACHE_PATH.read_text())
            last = data.get("last_computed")
            if not last:
                return False
            age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
            if age_hours > CACHE_MAX_AGE_HOURS:
                return False
            self._communities = data.get("communities", {})
            self._pagerank = {k: float(v) for k, v in data.get("pagerank", {}).items()}
            self._last_computed = last
            return True
        except Exception:
            return False

    def _save_cache(self):
        """Persist cache to disk."""
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({
            "communities": self._communities,
            "pagerank": {k: round(v, 8) for k, v in self._pagerank.items()},
            "last_computed": self._last_computed,
        }))

    def recompute(self):
        """Recompute communities and centrality from current graph."""
        g = self.graph_store.nx_graph
        self._communities = detect_communities(g)
        self._pagerank = compute_centrality(g)
        self._last_computed = datetime.now(timezone.utc).isoformat()
        self._save_cache()

    def boost_scores(
        self,
        seed_node_ids: List[str],
        candidate_node_ids: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute all Graph RAG boosts for candidates given seeds.
        Returns {node_id: {path: float, community: float, centrality: float}}
        """
        g = self.graph_store.nx_graph

        # Ensure cache exists
        if not self._communities and not self._pagerank:
            self.recompute()

        # Path relevance
        path_boosts = compute_path_relevance(g, seed_node_ids)

        # Seed communities
        seed_comms: Set[int] = set()
        for sid in seed_node_ids:
            if sid in self._communities:
                seed_comms.add(self._communities[sid])

        # Normalize pagerank
        max_pr = max(self._pagerank.values()) if self._pagerank else 1.0
        if max_pr == 0:
            max_pr = 1.0

        results: Dict[str, Dict[str, float]] = {}
        for nid in candidate_node_ids:
            path = path_boosts.get(nid, 0.0)
            comm = community_boost(seed_comms, self._communities.get(nid))
            pr_norm = self._pagerank.get(nid, 0.0) / max_pr
            centrality_mult = 1.0 + CENTRALITY_WEIGHT * pr_norm
            results[nid] = {
                "path": path,
                "community": comm,
                "centrality": centrality_mult,
            }
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Return stats about Graph RAG state."""
        if not self._communities and not self._pagerank:
            try:
                self.recompute()
            except Exception:
                pass

        community_ids = set(self._communities.values()) if self._communities else set()
        pr_values = list(self._pagerank.values()) if self._pagerank else []
        avg_centrality = sum(pr_values) / len(pr_values) if pr_values else 0.0

        # Top central nodes
        sorted_pr = sorted(self._pagerank.items(), key=lambda x: x[1], reverse=True)
        top_central = []
        for nid, score in sorted_pr[:10]:
            node = self.graph_store.get_node(nid)
            name = node.name if node else nid
            top_central.append((name, score))

        cache_age = None
        if self._last_computed:
            try:
                dt = datetime.fromisoformat(self._last_computed)
                cache_age = (datetime.now(timezone.utc) - dt).total_seconds()
            except Exception:
                pass

        return {
            "node_count": self.graph_store.nx_graph.number_of_nodes(),
            "community_count": len(community_ids),
            "avg_centrality": avg_centrality,
            "top_central": top_central,
            "cache_age_seconds": cache_age,
            "last_computed": self._last_computed,
        }


# Singleton
_graph_rag: Optional[GraphRAG] = None


def get_graph_rag() -> GraphRAG:
    global _graph_rag
    if _graph_rag is None:
        _graph_rag = GraphRAG()
    return _graph_rag
