# ATLAS Tools

Utility scripts for ATLAS agent operations.

## orchestrate.py - Multi-Agent Orchestration

Spawns and monitors multiple sub-agents, aggregates results, logs metrics.

### Quick Start

```python
from orchestrate import Orchestrator

orch = Orchestrator()

# Define tasks
tasks = [
    {"label": "research-llm", "task": "Research latest LLM developments", "timeout": 300},
    {"label": "research-agents", "task": "Research multi-agent patterns", "timeout": 300},
]

# Run in parallel
results = orch.run_parallel(tasks)

# Results structure:
# {"research-llm": {"status": "complete", "output_path": "...", "tokens": 5000, ...}, ...}
```

### Task Definition

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | str | Yes | Unique task identifier |
| `task` | str | Yes | Task prompt/description |
| `timeout` | int | No | Max seconds (default: 300) |
| `model` | str | No | Model override |
| `context` | str | No | Additional context to inject |

### Status Markers

Agents should use these markers in their output:
- `[STATUS:STARTING]` - When beginning work
- `[STATUS:PROGRESS]` - For milestone updates  
- `[STATUS:BLOCKER]` - If stuck and needs help
- `[STATUS:COMPLETE]` - When finished

### Monitoring Existing Sessions

```python
from orchestrate import poll_existing_sessions

# Monitor sessions you've already spawned
results = poll_existing_sessions(
    labels=["research-x", "research-y"],
    timeout=300
)
```

### Convenience Functions

```python
from orchestrate import spawn_research_agents, aggregate_results

# Quick research across multiple topics
results = spawn_research_agents([
    "Topic A to research",
    "Topic B to research"
], timeout=300)

# Combine results into single document
summary = aggregate_results(results)
```

### Metrics Logging

All runs are logged to `/workspace/clawd/logs/agent_metrics.jsonl`:

```json
{
  "timestamp": "2026-02-03T12:00:00",
  "label": "task-name",
  "status": "complete",
  "session_id": "uuid-here",
  "runtime_seconds": 45.2,
  "tokens_input": 1000,
  "tokens_output": 500,
  "tokens_total": 1500,
  "cost_usd": 0.015
}
```

### Output Files

Results are saved to `/workspace/clawd/outputs/{label}.md`

---

## memory_bridge.py - Sub-Agent Context Sharing

Bridge for sub-agents to access ATLAS's shared memory and share findings.

### Quick Start

```python
from memory_bridge import MemoryBridge, enrich_prompt, what_do_we_know

# Create bridge
bridge = MemoryBridge()

# Get context for a task
context = bridge.get_context_for_task(
    task="Research trading algorithms",
    include_recent_days=3,
    include_long_term=True,
    max_tokens=2000
)

# Log findings back
bridge.log_finding(
    task_id="research-123",
    finding="Discovered X is better than Y",
    importance="high"  # high/medium/low
)
```

### Helper Functions

```python
# Enrich a prompt with relevant context
from memory_bridge import enrich_prompt

enriched = enrich_prompt(
    task="Research momentum trading",
    prompt="Find the best momentum indicators..."
)

# Check what ATLAS knows about a topic
from memory_bridge import what_do_we_know

info = what_do_we_know("iWander project")
info_detailed = what_do_we_know("trading", detailed=True)

# Log findings (convenience wrapper)
from memory_bridge import log_agent_finding

log_agent_finding(
    task_id="research-001",
    finding="RSI divergence works best in ranging markets",
    importance="high",
    tags=["trading", "technical-analysis"]
)
```

### Orchestrator Integration

```python
from memory_bridge import create_enriched_task, spawn_with_context
from orchestrate import Orchestrator

# Create task with auto-injected context
task = create_enriched_task(
    label="research-momentum",
    task="Research momentum trading strategies"
)

orch = Orchestrator()
results = orch.run_parallel([task])

# Or spawn directly with context
result = spawn_with_context(
    label="analyze-market",
    task="Analyze current crypto market"
)
```

### Scratchpad (Shared State)

```python
from memory_bridge import get_scratchpad_value, set_scratchpad_value

# Read/write shared state
set_scratchpad_value("current_research", {"topic": "LLMs", "status": "in_progress"})
state = get_scratchpad_value("current_research")

# Full scratchpad access
bridge = MemoryBridge()
data = bridge.read_scratchpad()
bridge.write_scratchpad({"key": "value"}, expected_version=data["_version"])
```

### CLI Usage

```bash
# Search memory
python memory_bridge.py search "trading algorithms" --days 5 --tokens 1500

# What do we know about something
python memory_bridge.py know "iWander" --detailed

# Log a finding
python memory_bridge.py log task-123 "Found that X works better" --importance high

# View recent findings
python memory_bridge.py findings --limit 10 --importance high

# Scratchpad operations
python memory_bridge.py scratch show
python memory_bridge.py scratch get current_task
python memory_bridge.py scratch set status '"active"'
```

### Findings Log

Sub-agent findings are stored in `/workspace/clawd/memory/agent_findings.jsonl`.

ATLAS can review these and promote important findings to daily logs or MEMORY.md.

---

## research.py - Perplexity Research

Quick research via Perplexity API (use instead of broken web_search).

```bash
python research.py "your question here"
python research.py "detailed topic" --detailed
```

## browse.py - Playwright Web Fetch

Reliable web fetching with Playwright.

```bash
python browse.py "https://example.com"
python browse.py "https://example.com" --screenshot /tmp/out.png
```
