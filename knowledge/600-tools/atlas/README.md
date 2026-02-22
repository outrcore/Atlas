# ATLAS's Tools

Internal scripts, integrations, and systems that ATLAS uses to help Matt.

## Custom Scripts

Location: `/workspace/clawd/scripts/`

| Script | Purpose |
|--------|---------|
| `status.py` | System health check (voice APIs, tunnel, GPU) |
| `morning_brief.py` | Daily briefing (weather, status, memos) |
| `index_knowledge.py` | Rebuild knowledge vector index |
| `search_knowledge.py` | Semantic search across knowledge |

## Voice Stack

Location: `/workspace/projects/voice-stack/`

| Tool | Purpose |
|------|---------|
| `start_services.sh` | Launch voice APIs and tunnel |
| `voice_memo.py` | Transcribe, list, search voice memos |
| Voice API v1 (8765) | Basic TTS/ASR |
| Voice API v2 (8766) | Enhanced real-time interface |

## Memory Systems

| System | Purpose |
|--------|---------|
| LanceDB | Vector embeddings for semantic search |
| Daily logs | `memory/YYYY-MM-DD.md` raw notes |
| MEMORY.md | Curated long-term memory |
| STAGING.md | Candidates for memory promotion |
| Brain daemon | Background memory consolidation |

## OpenClaw Integrations

| Feature | How ATLAS uses it |
|---------|-------------------|
| `exec` | Run shell commands, spawn Claude Code |
| `browser` | Web automation via Playwright |
| `message` | Send Telegram/Discord messages |
| `cron` | Scheduled tasks and reminders |
| `nodes` | Access paired devices (Matt's phone) |
| `web_search` | Brave Search API |
| `web_fetch` | Fetch and extract webpage content |

## Watchdog & Reliability

| Tool | Purpose |
|------|---------|
| `atlas-watchdog.sh` | Monitors gateway, auto-restarts |
| `start-atlas.sh` | One-command full restart |
| `post_start.sh` | Bootstrap after pod restart |

---

*Document new tools here as they're created. Include usage examples and gotchas.*
