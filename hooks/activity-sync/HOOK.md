---
name: activity-sync
description: "Syncs live activity to .activity.json for cross-platform context sharing"
homepage: ""
metadata:
  openclaw:
    emoji: "🔄"
    events: ["command", "agent:bootstrap", "gateway:startup"]
    requires: {}
    install: []
---

# Activity Sync Hook

Updates `.activity.json` whenever ATLAS processes a message or command.
This enables Discord-ATLAS to see what Telegram-ATLAS is currently doing.

## What it does

- On `command` events: Updates activity with the command being processed
- On `agent:bootstrap`: Marks session as starting
- On `gateway:startup`: Marks gateway as ready
- Writes to `/workspace/clawd/.activity.json`

## Output format

```json
{
  "current": "Processing message from Matt",
  "channel": "telegram",
  "sessionKey": "agent:main:main",
  "updated": "2026-01-31T21:45:00.000Z"
}
```

## Usage

Discord reads this file to know what Telegram-ATLAS is doing, enabling
seamless context sharing across platforms.

## Configuration

Enabled by default when hook is installed. No additional config needed.
