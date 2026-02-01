# 🧠 ATLAS Brain

A proactive memory and intelligence system for ATLAS, inspired by memU concepts but built on our existing infrastructure.

## Overview

The Brain provides:
- **Activity Logging**: Automatic capture of conversations and actions
- **Insight Extraction**: Uses Claude to extract facts, preferences, and decisions
- **Semantic Memory**: LanceDB-based vector storage for semantic search
- **Intent Prediction**: Predicts what you might need next
- **Proactive Suggestions**: Surfaces relevant context before you ask

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    ATLAS Brain                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Activity   │  │   Memory    │  │   Intent    │  │
│  │   Logger    │  │  Extractor  │  │  Predictor  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │         │
│         ▼                ▼                ▼         │
│  ┌─────────────────────────────────────────────┐    │
│  │            Semantic Linker (LanceDB)         │    │
│  └─────────────────────────────────────────────┘    │
│         │                                           │
│         ▼                                           │
│  ┌─────────────────────────────────────────────┐    │
│  │  Proactive Suggester + Memory Sync           │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
└─────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   ┌──────────┐        ┌───────────┐
   │ LanceDB  │        │ MEMORY.md │
   │ Vectors  │        │ + Daily   │
   └──────────┘        └───────────┘
```

## Components

### ActivityLogger (`activity.py`)
Logs all activities (conversations, actions, events) to JSONL files organized by date.

```python
from brain import Brain

brain = Brain()
brain.log_activity("conversation", "User asked about the weather")
```

### MemoryExtractor (`extractor.py`)
Uses Claude to extract structured information from conversations:
- Facts (concrete information learned)
- Preferences (user preferences)
- Decisions (decisions made)
- Action items (things to do)
- Topics (for categorization)

### SemanticLinker (`linker.py`)
LanceDB-based vector storage for semantic search. Automatically links related memories.

```python
# Add a memory
memory_id = await brain.link_memory(
    "Matt prefers Fahrenheit for temperatures",
    category="300-personal"
)

# Search for related
results = await brain.find_related("What units does Matt prefer?")
```

### IntentPredictor (`predictor.py`)
Analyzes activity patterns to predict what you might need:
- Immediate needs
- Upcoming tasks
- Potential blockers
- Proactive suggestions

### ProactiveSuggester (`suggester.py`)
Surfaces relevant context based on:
- Time of day/week
- Current conversation context
- Pattern recognition

### MemorySync (`memory_sync.py`)
Syncs brain knowledge to human-readable files:
- MEMORY.md (long-term curated knowledge)
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
├── __init__.py          # Package exports
├── core.py              # Main Brain class
├── activity.py          # Activity logging
├── extractor.py         # Insight extraction (Claude)
├── linker.py            # Semantic memory (LanceDB)
├── predictor.py         # Intent prediction (Claude)
├── suggester.py         # Proactive suggestions
├── memory_sync.py       # MEMORY.md sync
├── hooks.py             # OpenClaw integration hooks
├── daemon.py            # Background daemon
├── test_brain.py        # Tests
└── README.md            # This file
```
