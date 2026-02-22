# ATLAS Memory Architecture - The 4 Layers

*Human-inspired memory system designed for ATLAS.*

## The Human Memory Model

Human memory works in layers:

| Layer | Function | Retention |
|-------|----------|-----------|
| 1. Sensory | Everything you perceive | Most forgotten quickly |
| 2. Short-term | Active working memory | Minutes to hours |
| 3. Long-term | Consolidated, meaningful memories | Permanent |
| 4. Semantic | Facts and knowledge, searchable by association | Permanent |

## ATLAS Implementation

### Layer 1: Sensory/Short-term → Raw Logs
**Location:** `memory/YYYY-MM-DD.md`

- Everything captured: conversations, actions, events
- Activity logger writes to JSONL by date
- Most will be forgotten (filtered out)
- This is the "hippocampus" - quick capture

### Layer 2: Consolidation → Brain Daemon
**Process:** Extraction during "sleep" (overnight processing)

What happens during consolidation:
- Brain daemon extracts what matters
- Scoring algorithm evaluates each memory:
  - **Importance (40%)** - Keywords like "decision", "lesson", "Matt wants", API keys
  - **Emotion (25%)** - Excited, frustrated, proud → sticks longer (like humans!)
  - **Recency (15%)** - Last 24h = 1.0, last week = 0.8, etc.
  - **Frequency (20%)** - Repeated info = probably important
- Threshold: 0.6 — anything above gets promoted
- Categories: credential, preference, user_info, decision, lesson, event, fact, todo

### Layer 3: Semantic → Vector DB
**Location:** LanceDB (brain_data/)

- Searchable by association, not just keywords
- "What temperature units does Matt prefer?" → finds "Matt prefers Fahrenheit"
- Embeddings enable semantic similarity
- Auto-links related memories

### Layer 4: Long-term → MEMORY.md + Dewey Library
**Location:** 
- `MEMORY.md` - Instant recall, curated facts (<20KB)
- `knowledge/` - Dewey Decimal organized docs

Rules for MEMORY.md:
- **Only load in main session** (security)
- **Manually curated ONLY** - brain daemon writes to STAGING.md
- Keep under 20KB
- NOT a log, NOT a knowledge base
- Periodically review STAGING.md and promote worthy items

## The Flow

```
Raw Input                    Consolidation                 Long-Term
─────────                    ─────────────                 ─────────
                                   ↓
Daily Logs          →    Brain Daemon (sleep)    →    MEMORY.md
memory/YYYY-MM-DD.md      Extracts & scores            Curated facts
                          every 5 min                   
                                   ↓
                          Vector DB (LanceDB)
                          Semantic search
                                   ↓
                          Proactive Recall
                          (before I respond)
```

## Inspired By

### Hippocampus-Inspired Memory Research
- Humans have fast/slow memory systems
- **Hippocampus** = quick capture (daily logs)
- **Neocortex** = slow consolidation (MEMORY.md)
- **Sleep** = when consolidation happens (nightly daemon)
- Emotional memories get priority (25% weight)

### Dual Learning Rates
- Fast learning: Capture everything immediately
- Slow learning: Carefully curate what sticks

## Tiered Synthesis Schedule

```
4:00 AM (Daily)   → Fresh consolidation of yesterday
4:00 AM (Sunday)  → Weekly pattern detection
5:00 AM (1st)     → Monthly project/goal tracking
```

- Daily catches fresh stuff, prevents loss
- Weekly spots patterns: "You mentioned X every day this week"
- Monthly sees projects evolve: "iWander went from idea → MVP"

## Key Insight

> "What do you think is the best option for what we are trying to do here (trying to make you have a human like brain and remember everything)?"

The answer: **All four layers working together.** 

Without raw capture, everything downstream starves. Without consolidation, logs become noise. Without semantic search, retrieval is keyword-only. Without curated long-term, nothing is truly permanent.

---
*Created: 2026-02-04 | Source: Telegram export analysis*
