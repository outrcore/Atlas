#!/usr/bin/env python3
"""
UMA Search Bridge - Phase 4

Provides a CLI + HTTP interface for the unified search system.
Called by OpenClaw's proactive-recall.ts to get graph-enhanced results.

Usage:
  CLI:    python search_bridge.py "query here" [--limit 5] [--json]
  HTTP:   python search_bridge.py --serve [--port 18790]

Created: 2026-02-06
"""

import asyncio
import json
import sys
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add brain to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.unified_search import UnifiedSearch, SearchResult, get_unified_search
from brain.fast_graph import get_fast_graph
from brain.embedder import get_embedder
from brain.maintenance import get_maintenance
from brain.graph_rag import get_graph_rag


WORKSPACE = Path("/workspace/clawd")
# Directories to search for source files
SEARCH_DIRS = [
    WORKSPACE / "memory",
    WORKSPACE / "knowledge",
    WORKSPACE,
]
# Max chars per snippet
SNIPPET_MAX_CHARS = 500
# Max snippets total
MAX_SNIPPETS = 5
import re

def sanitize_search_query(raw_query: str) -> str:
    """
    Clean up proactive-recall queries that contain full system prompts.
    Extract just the meaningful content for embedding search.
    """
    q = raw_query.strip()
    if not q:
        return q

    # Handle cron task prompts: [cron:UUID TaskName] full description...
    # Extract just the task name - that is the useful search query
    cron_match = re.match(r'\[cron:[0-9a-f-]+\s+(.+?)\]', q)
    if cron_match:
        return cron_match.group(1).strip()

    # Strip system envelope - extract text after [Telegram/Discord/etc ...UTC] markers
    bracket_pattern = re.compile(r'\[(?:Telegram|Discord|Slack|WhatsApp|iMessage|SMS)[^\]]*UTC\]\s*')
    parts = bracket_pattern.split(q)
    if len(parts) > 1:
        q = parts[-1].strip()

    # Strip common system prefixes
    system_prefixes = [
        "To send an image back",
        "System:",
        "[system]",
    ]
    for prefix in system_prefixes:
        idx = q.find(prefix)
        if idx == 0:
            newline_idx = q.find("\n", idx)
            bracket_idx = q.find("[", idx + 1)
            skip_to = min(
                newline_idx if newline_idx > 0 else len(q),
                bracket_idx if bracket_idx > 0 else len(q)
            )
            q = q[skip_to:].strip()

    # Strip "Current time: ..." lines and boilerplate tails
    q = re.sub(r'Current time:.*$', '', q, flags=re.MULTILINE).strip()
    q = re.sub(r'Return your summary as plain text.*$', '', q, flags=re.DOTALL).strip()

    return q if q else raw_query



def graph_neighbor_lookup(query: str) -> Dict[str, Any]:
    """
    Look up graph nodes matching the query and return their neighbors.
    Enriches search results with relationship context from the entity graph.
    
    Returns dict with:
      - matched_nodes: list of matching node names/types
      - neighbors: list of neighbor dicts with name, type, relation
      - relationships: list of relationship strings for display
    """
    try:
        graph = get_fast_graph()
        
        # Search for nodes matching the query (fuzzy via LIKE)
        matching_nodes = graph.search_nodes(query, limit=5)
        
        if not matching_nodes:
            # Try case-insensitive partial match on individual words
            words = [w for w in query.split() if len(w) > 2]
            for word in words[:3]:
                matches = graph.search_nodes(word, limit=3)
                matching_nodes.extend(matches)
            # Deduplicate
            seen_ids = set()
            deduped = []
            for n in matching_nodes:
                if n.id not in seen_ids:
                    seen_ids.add(n.id)
                    deduped.append(n)
            matching_nodes = deduped[:5]
        
        if not matching_nodes:
            return {"matched_nodes": [], "neighbors": [], "relationships": []}
        
        matched_info = []
        all_neighbors = []
        all_relationships = []
        seen_neighbor_ids = set()
        
        for node in matching_nodes:
            matched_info.append({"name": node.name, "type": node.type, "id": node.id})
            
            # Get depth-1 neighbors
            neighbors = graph.get_neighbors(node.id, depth=1)
            
            for neighbor_node, edge, depth in neighbors:
                if neighbor_node.id in seen_neighbor_ids:
                    continue
                seen_neighbor_ids.add(neighbor_node.id)
                
                # Skip date nodes and low-value connections
                if neighbor_node.type == "date":
                    continue
                
                all_neighbors.append({
                    "name": neighbor_node.name,
                    "type": neighbor_node.type,
                    "relation": edge.relation,
                    "weight": edge.weight,
                })
                
                # Build human-readable relationship
                if edge.source_id == node.id:
                    rel_str = f"{node.name} --{edge.relation}--> {neighbor_node.name}"
                else:
                    rel_str = f"{neighbor_node.name} --{edge.relation}--> {node.name}"
                all_relationships.append(rel_str)
        
        # Sort neighbors by edge weight (strongest connections first)
        all_neighbors.sort(key=lambda x: x.get("weight", 1.0), reverse=True)
        
        return {
            "matched_nodes": matched_info[:5],
            "neighbors": all_neighbors[:15],
            "relationships": all_relationships[:15],
        }
    except Exception as e:
        # Never crash search — just return empty
        print(f"⚠️ Graph neighbor lookup error: {e}")
        return {"matched_nodes": [], "neighbors": [], "relationships": []}


def drilldown(query: str, sources: list, entities: list) -> list:
    """
    Tier 3: Read source files and grep for relevant context.
    
    Strategy:
    1. If sources provided, read those files and find relevant sections
    2. If entities provided, grep memory/knowledge files for mentions
    3. Return text snippets with source attribution
    """
    snippets = []
    seen_content = set()
    
    # Strategy 1: Read provided source files
    for source in sources[:5]:
        file_snippets = _read_source_file(source, query, entities)
        for s in file_snippets:
            key = s["text"][:100]
            if key not in seen_content:
                snippets.append(s)
                seen_content.add(key)
    
    # Strategy 2: Grep for entity mentions in memory/knowledge
    if len(snippets) < MAX_SNIPPETS and entities:
        for entity in entities[:3]:
            grep_snippets = _grep_for_entity(entity, query)
            for s in grep_snippets:
                key = s["text"][:100]
                if key not in seen_content and len(snippets) < MAX_SNIPPETS:
                    snippets.append(s)
                    seen_content.add(key)
    
    return snippets[:MAX_SNIPPETS]


def _resolve_source_path(source: str) -> Optional[Path]:
    """Resolve a source reference to an actual file path."""
    # Direct path
    p = Path(source)
    if p.is_absolute() and p.exists():
        return p
    
    # Relative to workspace
    p = WORKSPACE / source
    if p.exists():
        return p
    
    # Try common patterns
    for pattern in [
        f"memory/{source}",
        f"knowledge/{source}",
        source.replace("memory/", ""),
    ]:
        p = WORKSPACE / pattern
        if p.exists():
            return p
    
    return None


def _read_source_file(source: str, query: str, entities: list) -> list:
    """Read a source file and extract relevant sections."""
    path = _resolve_source_path(source)
    if not path or not path.exists() or path.stat().st_size > 500_000:
        return []
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    
    lines = content.split("\n")
    snippets = []
    
    # Find lines mentioning entities or query terms
    search_terms = [t.lower() for t in entities + query.lower().split() if len(t) > 2]
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(term in line_lower for term in search_terms):
            # Grab context: 2 lines before, the match, 2 lines after
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            snippet_text = "\n".join(lines[start:end]).strip()
            
            if snippet_text and len(snippet_text) > 20:
                snippets.append({
                    "text": snippet_text[:SNIPPET_MAX_CHARS],
                    "source": str(path.relative_to(WORKSPACE)),
                    "line": i + 1,
                })
    
    # Deduplicate overlapping snippets (keep first occurrence)
    filtered = []
    covered_lines = set()
    for s in snippets:
        line = s["line"]
        if line not in covered_lines:
            filtered.append(s)
            # Mark nearby lines as covered
            for l in range(line - 3, line + 4):
                covered_lines.add(l)
    
    return filtered[:3]  # Max 3 snippets per file


def _grep_for_entity(entity: str, query: str) -> list:
    """Grep memory and knowledge files for entity mentions."""
    import subprocess
    
    snippets = []
    entity_lower = entity.lower()
    
    for search_dir in SEARCH_DIRS[:2]:  # memory/ and knowledge/ only
        if not search_dir.exists():
            continue
        
        try:
            result = subprocess.run(
                ["grep", "-rl", "-i", entity, str(search_dir),
                 "--include=*.md", "--include=*.txt"],
                capture_output=True, text=True, timeout=3
            )
            
            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            
            for filepath in files[:5]:
                file_snippets = _read_source_file(filepath, query, [entity])
                snippets.extend(file_snippets)
                if len(snippets) >= 3:
                    break
                    
        except (subprocess.TimeoutExpired, Exception):
            continue
    
    return snippets[:3]


def format_result(result: SearchResult, as_json: bool = False) -> str:
    """Format search result for output."""
    if as_json:
        return json.dumps({
            "memories": [
                {
                    "content": m.content,
                    "source": m.source,
                    "score": round(m.final_score, 3),
                    "scores": {
                        "semantic": round(m.semantic_score, 3),
                        "recency": round(m.recency_score, 3),
                        "relationship": round(m.relationship_score, 3),
                        "importance": round(m.importance_score, 3),
                    }
                }
                for m in result.memories
            ],
            "graph_context": result.graph_context,
            "entities": result.query_entities,
            "method": result.method,
            "confidence": round(result.confidence, 3)
        })
    
    lines = []
    for i, mem in enumerate(result.memories, 1):
        lines.append(f"- {mem.content} ({mem.source})")
    
    if result.graph_context.get("relationships"):
        lines.append("")
        lines.append("Graph relationships:")
        for rel in result.graph_context["relationships"][:5]:
            lines.append(f"  - {rel['from']} {rel['relation']} {rel['to']}")
    
    return "\n".join(lines)


def _get_node_embeddings():
    """Pre-compute embeddings for all graph node names."""
    embedder = get_embedder()
    graph = get_fast_graph()
    node_embeddings = {}
    nodes = list(graph._node_cache.values())
    if nodes:
        names = [n.name for n in nodes]
        vecs = embedder.embed_batch(names)
        for n, v in zip(nodes, vecs):
            node_embeddings[n.id] = v
    print(f"Pre-embedded {len(node_embeddings)} graph nodes.")
    return node_embeddings

_node_embeddings_cache = None

def get_node_embeddings():
    global _node_embeddings_cache
    if _node_embeddings_cache is None:
        _node_embeddings_cache = _get_node_embeddings()
    return _node_embeddings_cache


async def cli_search(query: str, limit: int = 5, as_json: bool = False):
    """Run a search from CLI."""
    embedder = get_embedder()
    query_embedding = embedder.embed(query)
    node_embs = get_node_embeddings()
    result = await get_unified_search().search(
        query, limit=limit,
        query_embedding=query_embedding,
        node_embeddings=node_embs
    )
    
    # Enrich with graph neighbor context
    try:
        neighbor_ctx = graph_neighbor_lookup(query)
        if neighbor_ctx.get("matched_nodes"):
            existing_rels = result.graph_context.get("relationships", [])
            for r in neighbor_ctx.get("relationships", []):
                if " --" in r and "--> " in r:
                    rel = {"from": r.split(" --")[0], "relation": r.split("--")[1].rstrip("-> "), "to": r.split("--> ")[-1]}
                    existing_rels.append(rel)
            result.graph_context["relationships"] = existing_rels[:20]
            result.graph_context["neighbor_nodes"] = neighbor_ctx.get("neighbors", [])[:10]
    except Exception:
        pass  # Non-critical
    
    print(format_result(result, as_json=as_json))


def serve(port: int = 18790):
    """Run HTTP server for search queries."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse
    
    search_instance = get_unified_search()
    embedder = get_embedder()
    node_embs = get_node_embeddings()
    loop = asyncio.new_event_loop()
    
    class SearchHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            
            if parsed.path == "/embed":
                text = params.get("text", [""])[0]
                if not text:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Missing text parameter"}')
                    return
                vec = embedder.embed(text)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "text": text,
                    "dim": len(vec),
                    "vector": vec[:5].tolist(),
                    "note": "truncated to 5 dims"
                }).encode())
                return
            
            if parsed.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                graph = get_fast_graph()
                stats = graph.get_stats()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "nodes": stats.get("nodes", 0),
                    "edges": stats.get("edges", 0)
                }).encode())
                return
            
            if parsed.path == "/entities":
                # Tier 1: Return all entity names for client-side caching
                graph = get_fast_graph()
                nodes = graph.search_nodes("", limit=1000)
                
                # Short names (< 60 chars, skip long decision strings)
                names = sorted(set(
                    n.name.lower() for n in nodes if len(n.name) < 60
                ))
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "max-age=300")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "entities": names,
                    "count": len(names)
                }).encode())
                return
            
            if parsed.path == "/graph-rag/stats":
                try:
                    rag = get_graph_rag()
                    stats = rag.get_stats()
                    # Make top_central JSON-serializable
                    stats["top_central"] = [
                        {"name": name, "score": round(score, 6)}
                        for name, score in stats.get("top_central", [])
                    ]
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(stats).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                return
            
            if parsed.path == "/maintenance":
                # Run maintenance tasks
                include_consol = params.get("consolidate", ["0"])[0] == "1"
                try:
                    maintenance = get_maintenance()
                    stats = maintenance.run_all(include_consolidation=include_consol)
                    # Also recompute Graph RAG caches
                    try:
                        rag = get_graph_rag()
                        rag.recompute()
                        stats["graph_rag_recomputed"] = True
                    except Exception as e:
                        stats["graph_rag_error"] = str(e)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(stats).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                return
            
            if parsed.path == "/drilldown":
                # Tier 3: Agentic drill-down - read source files for deeper context
                raw_query = params.get("q", [""])[0]
                query = sanitize_search_query(raw_query)
                sources_raw = params.get("sources", [""])[0]
                entities_raw = params.get("entities", [""])[0]
                
                if not query:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Missing query parameter q"}')
                    return
                
                start = time.time()
                sources = [s.strip() for s in sources_raw.split(",") if s.strip()] if sources_raw else []
                entities = [e.strip() for e in entities_raw.split(",") if e.strip()] if entities_raw else []
                
                snippets = drilldown(query, sources, entities)
                elapsed_ms = (time.time() - start) * 1000
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "snippets": snippets,
                    "count": len(snippets),
                    "elapsed_ms": round(elapsed_ms, 1)
                }).encode())
                return
            
            if parsed.path == "/search":
                raw_query = params.get("q", [""])[0]
                query = sanitize_search_query(raw_query)
                limit = int(params.get("limit", ["5"])[0])
                
                if not query:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Missing query parameter q"}')
                    return
                
                start = time.time()
                q_emb = embedder.embed(query)
                result = loop.run_until_complete(
                    search_instance.search(query, limit=limit,
                                           query_embedding=q_emb,
                                           node_embeddings=node_embs)
                )
                elapsed_ms = (time.time() - start) * 1000
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                
                # Hebbian boost: strengthen connections between accessed nodes
                if result.memories:
                    accessed_ids = [
                        m.source for m in result.memories 
                        if m.source and m.source != "graph"
                    ][:10]
                    if len(accessed_ids) >= 2:
                        try:
                            get_maintenance().record_access(accessed_ids)
                        except Exception:
                            pass  # Non-critical
                
                # Enrich with graph neighbor context
                graph_ctx = result.graph_context or {}
                try:
                    neighbor_ctx = graph_neighbor_lookup(query)
                    if neighbor_ctx.get("matched_nodes"):
                        # Merge graph neighbor relationships into graph_context
                        existing_rels = graph_ctx.get("relationships", [])
                        neighbor_rels = [
                            {"from": r.split(" --")[0], "relation": r.split("--")[1].rstrip("-> "), "to": r.split("--> ")[-1]}
                            for r in neighbor_ctx.get("relationships", [])
                            if " --" in r and "--> " in r
                        ]
                        # Deduplicate by (from, relation, to)
                        existing_keys = {(r.get("from",""), r.get("relation",""), r.get("to","")) for r in existing_rels}
                        for rel in neighbor_rels:
                            key = (rel["from"], rel["relation"], rel["to"])
                            if key not in existing_keys:
                                existing_rels.append(rel)
                                existing_keys.add(key)
                        graph_ctx["relationships"] = existing_rels[:20]
                        graph_ctx["neighbor_nodes"] = neighbor_ctx.get("neighbors", [])[:10]
                except Exception:
                    pass  # Non-critical enrichment
                
                response = {
                    "memories": [
                        {
                            "content": m.content,
                            "source": m.source,
                            "score": round(m.final_score, 3),
                        }
                        for m in result.memories
                    ],
                    "graph_context": graph_ctx,
                    "entities": result.query_entities,
                    "method": result.method,
                    "confidence": round(result.confidence, 3),
                    "elapsed_ms": round(elapsed_ms, 1)
                }
                self.wfile.write(json.dumps(response).encode())
                return
            
            self.send_response(404)
            self.end_headers()
        
        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            
            # OpenAI-compatible /embeddings endpoint
            # Accepts: POST { model, input } where input is string or list of strings
            # Returns: { data: [{ embedding: [...], index: N, object: "embedding" }], model, usage }
            if parsed.path in ("/embeddings", "/v1/embeddings"):
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len) if content_len > 0 else b""
                try:
                    payload = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "Invalid JSON", "type": "invalid_request_error"}}')
                    return
                
                raw_input = payload.get("input", "")
                model_name = payload.get("model", "nomic-embed-text-v1.5")
                
                # Normalize input to list
                if isinstance(raw_input, str):
                    texts = [raw_input]
                elif isinstance(raw_input, list):
                    texts = [str(t) for t in raw_input]
                else:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "input must be string or array", "type": "invalid_request_error"}}')
                    return
                
                if not texts or all(not t.strip() for t in texts):
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "input must not be empty", "type": "invalid_request_error"}}')
                    return
                
                try:
                    start = time.time()
                    data = []
                    total_tokens = 0
                    for i, text in enumerate(texts):
                        vec = embedder.embed(text)
                        data.append({
                            "object": "embedding",
                            "embedding": vec.tolist() if hasattr(vec, 'tolist') else list(vec),
                            "index": i
                        })
                        # Rough token estimate (4 chars per token)
                        total_tokens += max(1, len(text) // 4)
                    
                    elapsed_ms = (time.time() - start) * 1000
                    
                    response = {
                        "object": "list",
                        "data": data,
                        "model": model_name,
                        "usage": {
                            "prompt_tokens": total_tokens,
                            "total_tokens": total_tokens
                        }
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": {"message": str(e), "type": "server_error"}
                    }).encode())
                return
            
            self.send_response(404)
            self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Silence logs
    
    server = HTTPServer(("127.0.0.1", port), SearchHandler)
    print(f"UMA Search Bridge running on http://127.0.0.1:{port}")
    print(f"  GET /search?q=<query>&limit=5")
    print(f"  GET /health")
    server.serve_forever()


if __name__ == "__main__":
    args = sys.argv[1:]
    
    if "--serve" in args:
        port = 18790
        if "--port" in args:
            idx = args.index("--port")
            port = int(args[idx + 1])
        serve(port)
    elif len(args) >= 1 and not args[0].startswith("--"):
        query = args[0]
        limit = 5
        as_json = "--json" in args
        if "--limit" in args:
            idx = args.index("--limit")
            limit = int(args[idx + 1])
        asyncio.run(cli_search(query, limit, as_json))
    else:
        print("Usage:")
        print("  python search_bridge.py 'query' [--limit 5] [--json]")
        print("  python search_bridge.py --serve [--port 18790]")
