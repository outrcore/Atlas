# ATLAS Memory Architecture v2

*Designed: 2026-02-02 | Status: Phase 1 Complete*

## Overview

ATLAS uses a hierarchical memory system inspired by human cognition:

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY HIERARCHY                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: LONG-TERM CURATED                                 │
│  ├── MEMORY.md (persistent facts, preferences, lessons)     │
│  └── Knowledge Library (Dewey Decimal structured)           │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: SEMANTIC (Vector DB)                              │
│  └── LanceDB embeddings for similarity search               │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: CONSOLIDATION (Brain Daemon)                      │
│  └── Extraction, linking, clustering during "sleep"         │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: SHORT-TERM (Daily Logs)                           │
│  └── memory/YYYY-MM-DD.md raw activity logs                 │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Daily Logs (Layer 1)
- **Location:** `/workspace/clawd/memory/YYYY-MM-DD.md`
- **Purpose:** Raw capture of daily events, conversations, decisions
- **Retention:** 30+ days
- **Format:** Markdown with timestamps and categories

### 2. Brain Daemon (Layer 2)
- **Location:** `/workspace/clawd/brain/`
- **Purpose:** Background processing and consolidation
- **Schedule:** Every 5 minutes (maintenance), 30 minutes (prediction)
- **Tasks:**
  - Extract insights from conversations
  - Link related memories
  - Cluster similar content
  - Run memory promotion

### 3. Vector Database (Layer 3)
- **Location:** `/workspace/clawd/data/vector_db/`
- **Technology:** LanceDB + sentence-transformers (all-MiniLM-L6-v2)
- **Purpose:** Semantic search and similarity matching
- **Dimensions:** 384

### 4. Long-Term Memory (Layer 4)
- **MEMORY.md:** Curated facts, preferences, lessons learned
- **Knowledge Library:** `/workspace/clawd/knowledge/`
  - `000-reference/` — Quick facts, configs
  - `100-projects/` — Project documentation
  - `200-trading/` — Market notes
  - `300-personal/` — Matt's info
  - `400-technical/` — Code patterns

## Memory Promotion System

### Scoring Algorithm
```
promotion_score = (
    importance * 0.40 +      # Content signals
    emotion_weight * 0.25 +  # Emotional salience
    recency_weight * 0.15 +  # Time decay
    frequency * 0.20         # Repetition
)
```

### Categories
- `credential` — API keys, tokens (high importance)
- `preference` — User likes/dislikes
- `user_info` — Facts about Matt
- `decision` — Choices made
- `lesson` — Things learned
- `event` — Things that happened
- `fact` — General information
- `todo` — Action items

### Promotion Threshold
- Default: 0.6 (60% score required)
- Configurable via `--threshold` flag

## Research Foundation

### Recursive Language Models (RLMs)
- Paper: arxiv.org/abs/2512.24601
- Concept: Process arbitrarily long prompts via recursive self-calls
- Application: Consolidate large log files without context limits

### Hippocampus-Inspired Consolidation
- Fast buffer (daily logs) → Slow storage (MEMORY.md)
- "Sleep" processing during daemon maintenance
- Emotion-weighted retention (emotional memories persist longer)

### Dual Learning Rates
- Fast learning: Capture everything to daily logs
- Slow learning: Carefully promote to long-term storage

## Tools

### Manual Consolidation
```bash
python tools/consolidate_memory.py              # Default 7 days
python tools/consolidate_memory.py --days 14    # Last 14 days
python tools/consolidate_memory.py --dry-run    # Preview only
```

### Memory Search
```bash
python scripts/search_knowledge.py "query"
```

### Brain Daemon
```bash
python -m brain.daemon --mode daemon   # Run continuously
python -m brain.daemon --mode once     # Run once
python -m brain.daemon --status        # Show status
```

## Completed Phases

### Phase 2: LLM-Based Scoring ✅
*Completed: 2026-02-02*

**What was built:**
- `brain/llm_scorer.py` - LLMScorer and HybridScorer classes
- `tools/smart_consolidate.py` - CLI tool for smart consolidation

**Features:**
- Claude-based evaluation when API available
- Heuristic fallback for fast scoring
- Hybrid approach: LLM for ambiguous cases, heuristics for clear-cut
- Scoring prompt engineered for memory curation
- Entity and relationship extraction
- One-line summaries for each memory

**Usage:**
```bash
python tools/smart_consolidate.py --dry-run     # Preview
python tools/smart_consolidate.py --days 14     # Last 14 days
python tools/smart_consolidate.py --verbose     # Show details
```

### Phase 3: RLM Integration ✅
*Completed: 2026-02-02*

**What was built:**
- `brain/rlm_processor.py` - RLMProcessor and MemoryRLM classes
- `tools/rlm_consolidate.py` - CLI tool for RLM processing

**Features:**
- Recursive chunking of long logs (3000 chars per chunk)
- Hierarchical consolidation (Level 0 → Level N summaries)
- Cross-reference detection across multiple days
- Entity extraction and tracking
- Key fact extraction
- Adapts recursion depth to input size

**Architecture:**
```
Level 0: Raw text chunks (2000-3000 chars each)
Level 1: Summaries of chunks
Level 2: Summaries of summaries
...
Level N: Final consolidated summary
```

**Usage:**
```bash
python tools/rlm_consolidate.py                    # Consolidate 7 days
python tools/rlm_consolidate.py --days 30          # Consolidate 30 days
python tools/rlm_consolidate.py --xref             # Cross-reference analysis
python tools/rlm_consolidate.py --output summary.md  # Save to file
```

**Test Results:**
- Processed 4 log files (33,741 chars) in 0.01s
- 3 levels of recursion
- Found 55 entities, 3 recurring across multiple days
- Identified cross-references: Claude, Matt, Daily Log

### Phase 4: Agent Council ✅
*Completed: 2026-02-02*

**What was built:**
- `brain/agent_council.py` - AgentCouncil and Agent classes
- `tools/council_review.py` - CLI tool for council review

**Agent Roles:**
- 📚 **Archivist** - Wants to keep everything for future reference
- 🗑️ **Minimalist** - Aggressive pruning, high bar for keeping
- 🔍 **Analyst** - Looks for patterns and insights
- 🛡️ **Guardian** - Protects sensitive and personal info

**How It Works:**
1. Each agent evaluates memories independently
2. Votes are weighted (Guardian 2x for credentials, Analyst 1.3x for lessons)
3. Consensus threshold 70% for auto-decision
4. Weighted voting for close calls

**Usage:**
```bash
python tools/council_review.py --dry-run       # Preview
python tools/council_review.py --days 14       # Review 14 days
python tools/council_review.py --verbose       # Show all votes
```

**Test Results:**
- 146 candidates reviewed
- 138 kept (94.5%), 8 discarded (5.5%)
- Correctly weighted credentials (Guardian 2x)
- Properly filtered heartbeat checks

### Phase 5: Proactive Recall ✅
*Completed: 2026-02-02*

**What was built:**
- `brain/proactive_recall.py` - ProactiveRecaller and MemoryIndex classes
- Convenience function `get_proactive_context(query)`

**Features:**
- Semantic search using vector DB embeddings
- Keyword search in MEMORY.md
- Entity extraction and matching
- Temporal context (recent 24-48h memories)
- Context injection string builder
- "Remember when..." suggestions

**Search Types:**
1. **Semantic** - Vector similarity via LanceDB
2. **Keyword** - Direct text matching in MEMORY.md
3. **Entity** - Finds specific names, projects, paths mentioned
4. **Temporal** - Recent daily log entries

**Usage:**
```python
from brain import ProactiveRecaller, get_proactive_context

# Quick context injection
context = await get_proactive_context("Mac Studio config")

# Full control
recaller = ProactiveRecaller()
result = await recaller.recall("What did we work on?")
print(result.suggested_context)
```

**Test Results:**
- "Mac Studio configuration" → Found goal info (80% relevance)
- "Memory consolidation" → Found architecture docs
- "Claude Code" → Found usage notes

---

## All Phases Complete! 🎉

Brain v2 is now a full memory consolidation pipeline:
1. **Phase 1** - Base memory promotion (heuristics)
2. **Phase 2** - LLM-based smart scoring
3. **Phase 3** - RLM recursive processing for long logs
4. **Phase 4** - Agent council for quality control
5. **Phase 5** - Proactive recall before responding

---

## Future Enhancements

---

*This architecture enables ATLAS to maintain persistent, searchable, human-like memory across sessions.*
