# memU Integration Design

*Integrating memU's proactive memory into ATLAS*

## Overview

memU provides automated memory management that complements our manual MEMORY.md system.

## Architecture

```
                    ┌─────────────────────┐
                    │       Matt          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    ATLAS (Main)     │
                    │  - Conversation     │
                    │  - Tool execution   │
                    │  - Responses        │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼─────────┐     │      ┌─────────▼─────────┐
    │   memU Agent      │◄────┴─────►│   MEMORY.md       │
    │  (Background)     │            │  (Daily notes)    │
    │                   │            │                   │
    │ - Activity log    │            │ - Manual updates  │
    │ - Intent predict  │            │ - Long-term mem   │
    │ - Auto-extract    │            │ - Preferences     │
    └─────────┬─────────┘            └───────────────────┘
              │
    ┌─────────▼─────────┐
    │  /memu_memory/    │
    │  - Embeddings     │
    │  - Activity store │
    │  - Clusters       │
    └───────────────────┘
```

## memU Capabilities

From the SDK:
- `add_activity_memory` - Log activities/conversations
- `link_related_memories` - Connect memories semantically
- `generate_memory_suggestions` - Proactive suggestions
- `update_memory_with_suggestions` - Apply suggestions
- `run_theory_of_mind` - **Predict user intent!** 
- `cluster_memories` - Organize by topic

## Integration Plan

### Phase 1: Background Logger
- Hook into session events
- Log all conversations to memU
- Store in `/workspace/clawd/memu_memory/`

### Phase 2: Intent Prediction
- Run `theory_of_mind` periodically
- Surface predictions in heartbeats
- "Matt might want X based on recent activity"

### Phase 3: Proactive Memory
- Generate suggestions automatically
- Link new info to existing knowledge
- Update MEMORY.md with insights

## Configuration

```python
from memu import MemoryAgent, OpenAIClient

# Use Anthropic via compatible client or OpenAI for embeddings
agent = MemoryAgent(
    llm_client=client,
    agent_id="atlas",
    user_id="matt", 
    memory_dir="/workspace/clawd/memu_memory",
    enable_embeddings=True  # Needs OpenAI key for embeddings
)
```

## Requirements
- OpenAI API key (for embeddings) or configure alternative
- Background process to run memU agent
- Hook into OpenClaw session events

## Questions
1. Use OpenAI for embeddings or local model?
2. Run as separate process or integrated?
3. Sync frequency for intent prediction?
