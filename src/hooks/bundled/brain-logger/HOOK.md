---
name: brain-logger
description: "Log all messages to ATLAS brain activity system"
metadata:
  {
    "openclaw":
      {
        "emoji": "🧠",
        "events": ["agent:bootstrap", "command:new", "gateway:startup"],
        "install": [{ "id": "bundled", "kind": "bundled", "label": "Bundled with OpenClaw" }],
      },
  }
---

# Brain Logger Hook

Logs all session activity to the ATLAS brain system for memory continuity.

## What It Does

- Logs messages to `/workspace/clawd/brain_data/activity/YYYY-MM-DD.jsonl`
- Appends to daily memory at `/workspace/clawd/memory/YYYY-MM-DD.md`
- Tracks session starts/ends and gateway events

## Why It Exists

ATLAS needs persistent memory across sessions. This hook ensures all conversations
are captured in the brain activity log for later processing by the brain daemon.
