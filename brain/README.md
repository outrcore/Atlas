# Brain v2 — ATLAS Memory System

A 5-phase memory pipeline providing persistent, searchable, graph-aware memory for the ATLAS AI agent. Wakes up fresh each session but remembers everything through structured storage.

## What It Does

**Non-technical:** ATLAS has no built-in memory between conversations. Brain v2 gives it long-term memory — automatically extracting important facts from conversations, connecting them in a knowledge graph, making them searchable, and proactively surfacing relevant context.

**Technical:** 5-phase pipeline: raw logging → Claude Sonnet entity extraction → SQLite graph DB (1,437 nodes, 22K+ edges) → LanceDB vector index (882 memories + 620 knowledge chunks) with Nomic embeddings → unified search bridge (vectors + graph neighbors + scoring). Runs as a background daemon with 5-minute maintenance cycles.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       Brain v2 Pipeline                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Phase 1: EXTRACTION                                           │
│  ┌──────────────┐    ┌──────────────────┐                      │
│  │ Daily Logs   │───→│ Sonnet Extractor  │──→ Entities,        │
│  │ memory/*.md  │    │ (Claude Sonnet)   │   Relations,        │
│  └──────────────┘    └──────────────────┘   Facts              │
│                                                                │
│  Phase 2: GRAPH                                                │
│  ┌──────────────────┐    ┌──────────────┐                      │
│  │ Extracted         │───→│ SQLite Graph │  1,437 nodes         │
│  │ Entities/Rels     │    │ (graph.db)   │  22K+ edges          │
│  └──────────────────┘    └──────────────┘                      │
│                                                                │
│  Phase 3: VECTOR                                               │
│  ┌──────────────────┐    ┌──────────────┐                      │
│  │ Knowledge docs   │───→│ LanceDB      │  882 memories        │
│  │ + extracted facts │    │ Nomic v1.5   │  620 knowledge chunks│
│  └──────────────────┘    └──────────────┘                      │
│                                                                │
│  Phase 4: SEARCH                                               │
│  ┌──────────────────┐    ┌──────────────┐                      │
│  │ Query            │───→│ Unified      │──→ Vector results     │
│  │                  │    │ Search Bridge │   + Graph neighbors   │
│  └──────────────────┘    │ (port 18790) │   + Scored/ranked     │
│                          └──────────────┘                      │
│                                                                │
│  Phase 5: MAINTENANCE                                          │
│  ┌──────────────────┐                                          │
│  │ Daemon (5 min)   │  - Extract new files (max 3/cycle)       │
│  │ brain-daemon     │  - Re-index knowledge after graph changes│
│  │ screen session   │  - Clean STAGING.md weekly (>100 lines)  │
│  └──────────────────┘  - Track processed files by name + size  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌──────────────┐              ┌───────────────┐
  │ graph.db     │              │ LanceDB       │
  │ (SQLite)     │              │ (vector_store/)│
  └──────────────┘              └───────────────┘
```

## Key Technical Decisions

1. **LanceDB over Pinecone/Weaviate:** Local-first, no API costs, GPU-accelerated. Stores vectors alongside metadata in columnar format.
2. **Nomic v1.5 embeddings:** 768 dimensions, 8192 token context. Runs locally on GPU via sentence-transformers. No external API dependency.
3. **SQLite for graph (not Neo4j):** Lightweight, zero-config, file-based. 1,437 nodes and 22K edges is well within SQLite's capabilities.
4. **Claude Sonnet for extraction:** Best balance of quality and cost. Extracts entities, relations, facts, preferences, and decisions from raw text.
5. **Unified search bridge on port 18790:** Single endpoint that combines vector similarity, graph neighbor expansion, and scoring. OpenClaw's memory_search routes through this.
6. **autoInject/autoExtract OFF:** OpenClaw's built-in memory hooks caused issues. Our custom UMA (Unified Memory Architecture) handles everything through the search bridge.

## Components

### Core (`core.py`)
Main Brain class. Orchestrates all phases. Entry point for daemon operations.
- `run_maintenance()` — called every 5 min by daemon
- `_run_graph_extraction()` — processes max 3 new/changed files per cycle
- `_clean_staging_if_due()` — auto-archives STAGING.md weekly

### Entity Extraction (`sonnet_extractor.py`)
Uses Claude Sonnet to extract structured entities from daily logs and conversation text.
Tracks processed files by name + size in `brain_data/extraction_state.json`.

### Graph Database (`graph.py`, `graph_extractor.py`, `fast_graph.py`)
SQLite-based knowledge graph. Stores entities as nodes with typed relationships as edges.
- `graph_neighbor_lookup()` in `search_bridge.py` enriches vector results with entity neighbors
- `enrich_graph.py` and `enrich_v2.py` add deeper relationship extraction
- `backfill_graph.py` processes historical files

### Vector Store (`embedder.py`, `linker.py`, `vector_store/`)
LanceDB with Nomic embeddings. Indexes both brain memories and knowledge library documents.
- 882 brain memories + 620 knowledge chunks (as of Feb 2026)
- Auto-reindex triggered after graph extraction finds new nodes
- Knowledge indexer: `reindex.py`, `auto_index.py`

### Search Bridge (`search_bridge.py`, `unified_search.py`)
HTTP server on port 18790. Accepts queries and returns ranked results combining:
- Vector similarity (cosine distance)
- Graph neighbor expansion (related entities)
- LLM-based relevance scoring (`llm_scorer.py`)

### Proactive Recall (`proactive_recall.py`)
Surfaces relevant context before it's asked for. Loaded at session start.

### Activity Logger (`activity.py`)
Logs all activities to JSONL files organized by date.

### Memory Sync (`memory_sync.py`, `memory_promotion.py`)
Syncs brain knowledge to human-readable files:
- MEMORY.md (long-term curated knowledge, manually promoted)
- STAGING.md (candidates for review, auto-populated)
- Daily notes (memory/YYYY-MM-DD.md)

## Usage

### Basic Usage

```python
from brain import Brain
import asyncio

async def main():
    brain = Brain()
    await brain.initialize()
    
    # Log an activity
    brain.log_activity("conversation", "Discussed project plans")
    
    # Extract insights from a conversation
    insights = await brain.extract_insights(conversation_text)
    
    # Find related memories
    related = await brain.find_related("project plans")
    
    # Get predictions
    predictions = await brain.predict_intent()

asyncio.run(main())
```

### Running the Daemon

```bash
# Run continuously
python -m brain.daemon --mode daemon

# Run once (maintenance only)
python -m brain.daemon --mode once

# Run prediction only
python -m brain.daemon --predict

# Show status
python -m brain.daemon --status
```

### Session Hooks

```python
from brain import hooks

# Log a message
await hooks.on_session_message("user", "Hello!")

# Get context for a message
context = await hooks.get_context_for_message("What's the weather?")

# On session end (triggers extraction)
await hooks.on_session_end(session_id, messages)
```

## Configuration

The brain uses these paths by default:
- Workspace: `/workspace/clawd`
- Brain data: `/workspace/clawd/brain_data`
- Vector DB: `/workspace/clawd/data/vector_db`
- Knowledge: `/workspace/clawd/knowledge`
- Memory: `/workspace/clawd/memory`

## Dewey Decimal Categories

The brain integrates with our knowledge library structure:
- `000-reference`: Quick facts, configs, cheat sheets
- `100-projects`: Coding projects, documentation
- `200-trading`: Market notes, strategies
- `300-personal`: Preferences, health, goals
- `400-technical`: Code patterns, learnings

## Known Limitations

1. **Embeddings**: Currently uses fallback hash embeddings due to huggingface-hub version conflict with Qwen TTS. Semantic search quality is limited until resolved.

2. **Requires API Key**: Extraction and prediction require ANTHROPIC_API_KEY.

## Testing

```bash
python brain/test_brain.py
```

## Files

```
brain/
├── __init__.py              # Package exports
├── core.py                  # Main Brain class, orchestrates all phases
├── daemon.py                # Background daemon (5-min cycles)
├── hooks.py                 # OpenClaw integration hooks
│
│ ── Extraction ──
├── extractor.py             # Basic insight extraction
├── sonnet_extractor.py      # Claude Sonnet entity extraction (primary)
├── cheap_extractor.py       # Budget extraction for high-volume
│
│ ── Graph ──
├── graph.py                 # SQLite graph DB operations
├── graph_extractor.py       # Extract entities → graph
├── fast_graph.py            # Optimized graph queries
├── graph_rag.py             # Graph-enhanced RAG
├── backfill_graph.py        # Process historical files
├── enrich_graph.py          # Deeper relationship extraction
├── enrich_v2.py             # V2 enrichment pipeline
├── seed_graph.py            # Initial graph seeding
│
│ ── Vector ──
├── embedder.py              # Nomic v1.5 embedding generation
├── linker.py                # LanceDB vector operations
├── reindex.py               # Full re-index of vector store
│
│ ── Search ──
├── search_bridge.py         # Unified search HTTP server (port 18790)
├── unified_search.py        # Combined vector + graph search
├── llm_scorer.py            # LLM-based relevance scoring
├── scorer.py                # Heuristic scoring
│
│ ── Intelligence ──
├── activity.py              # Activity logging
├── predictor.py             # Intent prediction (Claude)
├── suggester.py             # Proactive context suggestions
├── proactive_recall.py      # Pre-session context loading
├── reflection.py            # Self-reflection analysis
├── contradiction.py         # Detect contradictory memories
├── alerts.py                # Alert generation
├── agent_council.py         # Multi-agent memory council
├── task_planner.py          # Task planning from memory
│
│ ── Sync ──
├── memory_sync.py           # Sync to MEMORY.md / daily notes
├── memory_promotion.py      # Promote staging → long-term
├── smart_consolidation.py   # Deduplicate and merge memories
├── tiered_synthesis.py      # Multi-tier memory synthesis
│
│ ── Integration ──
├── rlm_integration.py       # Recursive Language Model integration
├── rlm_processor.py         # RLM processing pipeline
│
│ ── Data ──
├── graph.db                 # SQLite graph (1,437 nodes, 22K+ edges)
├── lancedb/                 # LanceDB vector store directory
├── vector_store/            # Additional vector data
├── cache/                   # Embedding cache
│
│ ── Testing ──
├── test_brain.py            # Tests
├── examples/                # Usage examples
└── README.md                # This file
```

## Current Stats (Feb 2026)

| Metric | Value |
|--------|-------|
| Graph nodes | 1,437 |
| Graph edges | 22,000+ |
| Brain memories | 882 |
| Knowledge chunks | 620 |
| Embedding model | Nomic v1.5 (768 dims) |
| Extraction model | Claude Sonnet |
| Daemon interval | 5 minutes |
| Search port | 18790 |
