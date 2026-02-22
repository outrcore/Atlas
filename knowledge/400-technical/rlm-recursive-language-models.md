# RLM - Recursive Language Models

*Research that Matt shared for ATLAS to integrate.*

## Paper Reference

- **Title:** Recursive Language Models
- **ArXiv:** https://arxiv.org/abs/2512.24601
- **PDF:** https://arxiv.org/pdf/2512.24601
- **GitHub:** https://github.com/alexzhang13/rlm

## Key Concepts

### The Core Idea
> "Process arbitrarily long prompts by treating them as an external environment. LLM can examine, decompose, and recursively call itself over snippets."

### Performance
- Works **2 orders of magnitude beyond context windows**
- RLM-Qwen3-8B outperforms base model by **28.3%**

### How It Works
1. Take a long input that exceeds context window
2. Chunk it into manageable pieces
3. LLM processes each chunk
4. Recursively consolidate results
5. Final synthesis from consolidated chunks

## Why This Matters for ATLAS

### Memory Consolidation Use Case
> "This directly applies to memory consolidation — I could recursively process my daily logs, extract patterns, and synthesize knowledge even when the raw data exceeds my context window."

### Practical Applications
- Process entire weeks/months of daily logs
- Extract cross-references between days
  - "You mentioned X on Monday and Y on Thursday — they're related"
- Synthesize knowledge from massive amounts of text
- Deep research on topics requiring lots of context

## Integration with ATLAS Brain

### Where It Fits
```
Human Memory Layers → ATLAS Implementation
─────────────────────────────────────────
Sensory/Short-term  → Daily logs (memory/YYYY-MM-DD.md)
Consolidation       → Brain daemon + RLM processing
Semantic           → Vector DB (LanceDB)
Long-term          → MEMORY.md (curated)
```

### RLM Phase in Brain v2
**Phase 3: RLM Integration**
> "Process entire weeks of logs by recursively chunking and consolidating. Extract cross-references between days."

### Implementation Location
- Library cloned to: `/workspace/projects/rlm`
- Research tool built: `/workspace/clawd/tools/rlm_research.py`
- Consolidation tool: `/workspace/clawd/tools/rlm_consolidate.py`

## Cron Schedule for RLM Processing

```
4:00 AM (Daily)   → Daily synthesis - process yesterday
5:00 AM (Weekly)  → Deep memory synthesis - RLM consolidation of the week
```

## Research Notes from Matt

From the conversation when Matt shared the paper:
> "Last thing I will leave you with is this, new research about something called RLM, maybe you can look into it and build on it or integrate it..."

Matt's directive:
> "Figure out how to implement the RLM stuff we have talked about. These two together integrated into your core system is going to be very powerful. But we need to make sure it is done right."

---
*Created: 2026-02-04 | Source: Telegram export analysis*
