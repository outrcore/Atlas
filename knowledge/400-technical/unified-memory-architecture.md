# Unified Memory Architecture (UMA)

*A hybrid memory system combining knowledge graphs, vector embeddings, and multi-dimensional scoring for AI agents.*

**Status:** Core Implementation Complete (Phases 1-3 + Tiered Search)
**Created:** 2026-02-06
**Inspired by:** Claude Code team insights, Mem0, Claudia, AiCMS research

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED MEMORY ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │   SOURCE    │    │   ENTITY    │    │   VECTOR    │                 │
│  │   FILES     │◄──►│   GRAPH     │◄──►│   INDEX     │                 │
│  │             │    │             │    │             │                 │
│  │ • Daily logs│    │ • 284 Nodes │    │ • LanceDB   │                 │
│  │ • Knowledge │    │ • 521 Edges │    │ • Embeddings│                 │
│  │ • MEMORY.md │    │ • SQLite +  │    │ • Chunks    │                 │
│  │             │    │   NetworkX  │    │             │                 │
│  └─────────────┘    └─────────────┘    └─────────────┘                 │
│         │                  │                  │                         │
│         └──────────────────┼──────────────────┘                         │
│                            ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    QUERY ORCHESTRATOR (3 Tiers)                    │  │
│  │  Tier 1: Entity cache check (~1ms)                                │  │
│  │  Tier 2: Graph traversal + Vector search (~300ms)                 │  │
│  │  Tier 3: Agentic file drill-down (~600ms total)                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                            │                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    QUALITY SYSTEMS                                 │  │
│  │  • Contradiction detection (same-day filtering)                   │  │
│  │  • Multi-dimensional scoring (5 dimensions)                       │  │
│  │  • Local GPU embeddings (BGE-Large, 1024-dim)                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                            │                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    MEMORY MAINTENANCE (TODO)                       │  │
│  │  • Decay (reduce old scores)      • Hebbian (boost on access)    │  │
│  │  • Consolidation (merge similar)  • Health dashboard             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Tiered Query Flow

```
Message arrives
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 1: Entity Cache Check (~1ms)                          │
│  • 263 entity names cached in TypeScript (5min TTL)         │
│  • Check for memory keywords ("remember", "what did", etc.) │
│  • No HTTP call needed - pure string matching               │
│  Result: Skip (no entities) or Escalate to Tier 2           │
└─────────────────────────────────────────────────────────────┘
      │ entities found
      ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 2: Full UMA Search (~300ms)                           │
│  • HTTP call to bridge (127.0.0.1:18790/search)             │
│  • Graph traversal via NetworkX (~1ms)                      │
│  • Vector search via LanceDB                                │
│  • Multi-dimensional scoring (semantic, recency,            │
│    relationship, importance, reliability)                    │
│  • Real cosine similarity via BGE-Large GPU embeddings      │
│  Result: High confidence (≥0.7) → done, or Escalate        │
└─────────────────────────────────────────────────────────────┘
      │ confidence < 0.7
      ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 3: Agentic Drill-Down (~300ms extra)                  │
│  • HTTP call to bridge (127.0.0.1:18790/drilldown)          │
│  • Reads actual source files referenced by Tier 2 results   │
│  • Greps memory/ and knowledge/ for entity mentions         │
│  • Returns text snippets with line numbers                  │
│  Result: Rich context from real files                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Entity Graph Store (`brain/graph.py` + `brain/fast_graph.py`)

**Storage:** SQLite for persistence, NetworkX for fast in-memory traversal

- **SQLite** (`brain/graph.db`): Durable storage, CRUD operations, SQL queries
- **NetworkX** (`brain/fast_graph.py`): In-memory cache, ~1ms BFS vs 500ms SQLite BFS

**Schema:**
```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- person, project, decision, concept, date, tool, location, event
    name TEXT NOT NULL,
    metadata JSON,
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decay_score REAL DEFAULT 1.0
);

CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES nodes(id),
    target_id TEXT REFERENCES nodes(id),
    relation TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, relation)
);

CREATE TABLE contradictions (
    id TEXT PRIMARY KEY,
    memory_a TEXT,
    memory_b TEXT,
    conflict_type TEXT,
    resolution TEXT,
    resolved_at TIMESTAMP
);
```

**Current Stats (2026-02-06):**
- 284 nodes (128 tools, 90 decisions, 46 projects, 10 people)
- 521 edges
- Backfilled from 8 daily logs (Jan 30 - Feb 6)

### Entity Extraction (`brain/graph_extractor.py` + `brain/sonnet_extractor.py`)

- **Sonnet Extractor**: Claude Sonnet for high-quality entity/relationship extraction
- **Graph Extractor**: Wraps Sonnet, normalizes names, infers relationships, checks contradictions
- **Auto-extraction**: Runs via `auto-memory.ts` hook after every conversation

### Local GPU Embeddings (`brain/embedder.py`)

- **Model:** BAAI/bge-large-en-v1.5 (1.3GB VRAM, 1024 dimensions)
- **Hardware:** NVIDIA RTX 4090 (24GB VRAM)
- **Speed:** 0.3ms/text encoding, ~12s initial load
- **Pattern:** Singleton with LRU cache
- **Pre-embeds** all 284 graph nodes on bridge startup
- **Zero API cost** - runs locally forever

### Multi-Dimensional Scorer (`brain/scorer.py`)

Five scoring dimensions, weighted:

| Dimension | Weight | Source |
|-----------|--------|--------|
| Semantic similarity | 30% | Cosine similarity via BGE-Large embeddings |
| Recency | 20% | Exponential decay (~30 day half-life) |
| Graph proximity | 25% | BFS distance from query entities |
| Importance | 15% | Node importance + access frequency |
| Source reliability | 10% | Source type weighting (decisions > logs) |

### Contradiction Detection (`brain/contradiction.py`)

- **Threshold:** 0.80 similarity = potential contradiction
- **Auto-resolve:** 0.90+ similarity = clear update (old fact superseded)
- **Same-day filter:** High similarity on same day = corroboration, not contradiction (handles instruction→completion pattern)
- **Resolution:** Auto-supersede clear updates, flag ambiguous for review
- **CLI:** `python brain/contradiction.py scan [entity]`, `python brain/contradiction.py unresolved`

### Search Bridge (`brain/search_bridge.py`)

HTTP server decoupling Python UMA from TypeScript OpenClaw runtime.

**Endpoints:**
| Endpoint | Purpose |
|----------|---------|
| `GET /search?q=...&limit=N` | Tier 2: Full graph+vector search |
| `GET /drilldown?q=...&sources=...&entities=...` | Tier 3: File reading + grep |
| `GET /entities` | Tier 1: Entity name list (5min cache) |
| `GET /embed?text=...` | Debug: Test embedding |
| `GET /health` | Health check with node/edge counts |

**Runtime:** Screen session `uma-bridge`, port 18790, localhost only

### Unified Search (`brain/unified_search.py`)

Orchestrates graph traversal + vector search + scoring:
1. Extract entities from query
2. Parallel: graph neighbors + LanceDB vector search
3. Merge candidates, deduplicate
4. Score via MultiDimensionalScorer
5. Return ranked results with confidence

### Integration (`proactive-recall.ts`)

Wired into OpenClaw's proactive recall system:
- `shouldRunFullUmaSearch()` - Tier 1 entity cache check
- `tryUmaSearchFull()` - Tier 2 full search via HTTP bridge
- `tryDrilldown()` - Tier 3 agentic file reading
- Falls back gracefully if bridge is down (2s/3s timeouts)

---

## File Structure (Actual)

```
brain/
├── __init__.py
├── graph.py              # Entity graph SQLite CRUD
├── fast_graph.py         # NetworkX in-memory cache (~1ms BFS)
├── graph_extractor.py    # Extract entities → populate graph
├── sonnet_extractor.py   # Claude Sonnet extraction prompts
├── cheap_extractor.py    # Fast/cheap extraction (unused currently)
├── embedder.py           # BGE-Large GPU embedding singleton
├── scorer.py             # Multi-dimensional scoring (5 dims)
├── unified_search.py     # Orchestrator: graph + vector + scoring
├── search_bridge.py      # HTTP server (port 18790)
├── contradiction.py      # Conflict detection + same-day filtering
├── backfill_graph.py     # One-time: backfill graph from daily logs
├── seed_graph.py         # One-time: seed initial graph data
├── hooks.py              # OpenClaw hook integration
├── linker.py             # Vector operations (LanceDB)
├── daemon.py             # Background processing
├── core.py               # Brain orchestrator
├── extractor.py          # Legacy extractor
└── graph.db              # SQLite database (284 nodes, 521 edges)
```

**OpenClaw integration files:**
```
Jarvis/src/agents/pi-embedded-runner/run/
├── proactive-recall.ts   # Tier 1/2/3 orchestration
├── auto-memory.ts        # Auto-extraction after conversations
└── auto-rag.ts           # RAG system
```

---

## Implementation Status

### ✅ Completed

| Phase | What | Files |
|-------|------|-------|
| Phase 1: Graph Store | SQLite + NetworkX, CRUD, pathfinding, backfill from 8 daily logs | graph.py, fast_graph.py, backfill_graph.py |
| Phase 2: Extraction | Sonnet-based extraction, auto after every session, name normalization | graph_extractor.py, sonnet_extractor.py |
| Phase 3: Scoring | 5-dimension scorer, real cosine similarity via GPU embeddings | scorer.py, embedder.py |
| Phase 4: Integration | HTTP bridge, proactive-recall wiring, 2s/3s timeouts, silent fallback | search_bridge.py, proactive-recall.ts |
| Tier 1: Fast Cache | Entity name cache in TypeScript, memory keyword detection, ~1ms | proactive-recall.ts |
| Tier 2: Full Search | Graph + vector + scoring via bridge, ~300ms | search_bridge.py, unified_search.py |
| Tier 3: Drill-Down | File reading + grep when confidence < 0.7, ~300ms extra | search_bridge.py, proactive-recall.ts |
| Contradiction Detection | Same-day filtering, auto-supersede, ambiguous flagging | contradiction.py |

### ❌ Not Yet Implemented

| Item | Priority | Description |
|------|----------|-------------|
| **Scheduled decay** | High | Reduce old/unaccessed node scores over time. Code exists in graph.py but not wired to daemon. |
| **Hebbian boosting** | High | Strengthen connections accessed together. Code exists but not triggered. |
| **Consolidation** | Medium | Merge memories with >0.95 similarity. Reduces graph bloat. |
| **Memory health dashboard** | Low | Stats, visualization, health metrics. |
| **3D brain visualization** | Low | Like Claudia's `/brain` command. |
| **Scorer weight tuning** | Low | Optimize weights based on real usage data. |

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Tier 1 latency | < 5ms | ~1ms ✅ |
| Tier 2 latency | < 500ms | ~300ms ✅ |
| Tier 3 latency | < 2s total | ~600ms ✅ |
| Semantic similarity quality | Real cosine sim | BGE-Large 1024-dim ✅ |
| Graph coverage | > 90% entities | 284 nodes from 8 days ✅ |
| Contradiction false positives | < 20% | ~1 after tuning ✅ |

---

## Key Architectural Decisions

| Decision | Why |
|----------|-----|
| SQLite + NetworkX hybrid | SQLite for persistence, NetworkX for ~1ms BFS (vs 500ms SQLite) |
| HTTP bridge (not in-process) | Decouples Python ML from TypeScript runtime. Clean failure isolation. |
| BGE-Large over MiniLM | 0.798 vs 0.567 similarity on test queries. Quality worth 1.3GB VRAM. |
| Sonnet for extraction | Quality over cost. Kimi K2.5 was 100x cheaper but too lossy. |
| Same-day contradiction filter | Matt's instruction + ATLAS confirmation aren't contradictions - they're corroboration. |
| 0.80/0.90 thresholds | 0.75 had too many false positives (different facts about same entity). 0.80 clean. |

---

## Research References

**Boris Cherny (Claude Code creator):**
> "Agentic search over the repo (glob/grep/read) consistently worked better on real-world codebases than RAG + vector DB."

**Carlo Kuijer (AiCMS):**
> "Embeddings + graph structure outperforms flat RAG."

**Tausifur Rahman:**
> "We have been over-engineering Vector DBs for problems that actually require better Reasoning, not just better Retrieval."

### Related Projects
- **Mem0** - Dual storage (vector + graph), multi-dimensional scoring
- **Claudia** - Relationship-focused memory with 3D visualization
- **AiCMS** - 7-dimensional memory scoring

---

## Future Enhancements

### Liquid Neural Networks (Post-stabilization)
Replace hard-coded decay rates with learned time dynamics. MIT CSAIL research - tiny interpretable networks (~19 neurons) for continuous-time decisions.

### Other Future Items
- NEAT for evolving scorer weights
- 3D brain visualization
- Commitment tracking and reminders
- Cross-session memory sharing

---

*Last updated: 2026-02-06 (post-implementation)*
