# 🌐 Atlas

**A personal AI assistant workspace built on [OpenClaw](https://openclaw.com).**

Atlas is an opinionated framework for running a persistent, proactive AI assistant that remembers you, learns over time, and actually gets things done. It includes a memory system (Brain), custom tools, a knowledge library, and operational scripts — everything you need to go from "AI chatbot" to "AI partner."

---

## What's Included

| Module | Description |
|--------|-------------|
| **brain/** | Memory system — vector search, knowledge graphs, extraction, consolidation, proactive recall |
| **tools/** | Custom tools — web research (Perplexity), browsing (Playwright), health checks, content generation |
| **scripts/** | Utility scripts — knowledge indexing, status checks, morning briefings, brain maintenance |
| **ops/** | Operational tools — session management, monitoring, task dispatch |
| **skills/** | Skill definitions for browser automation and Claude Code integration |
| **knowledge/** | Dewey Decimal-organized knowledge library (reference, projects, technical, lessons) |
| **memory/** | Daily log files — your AI's working memory across sessions |

### Core Config Files

| File | Purpose |
|------|---------|
| `SOUL.md` | Your AI's personality, voice, and behavioral rules |
| `USER.md` | Information about you (created from template) |
| `TOOLS.md` | Your local tool configs, API keys, server details (created from template) |
| `MEMORY.md` | AI's curated long-term memory (created from template) |
| `AGENTS.md` | Workspace rules — how the AI operates, memory architecture, safety guidelines |
| `HEARTBEAT.md` | Periodic task checklist the AI runs on its own |
| `IDENTITY.md` | Quick identity reference |
| `.claude.json` | Claude Code project config |

---

## Quick Start (macOS)

### 1. Prerequisites

```bash
# Install Node.js 22+
brew install node

# Install Python 3.11+ (for brain/tools)
brew install python@3.11
```

### 2. Install OpenClaw

```bash
npx openclaw@latest setup
```

Follow the prompts. This creates `~/.openclaw/` and sets up the gateway daemon.

### 3. Clone Atlas into your workspace

```bash
cd ~/.openclaw
git clone https://github.com/YOUR_USER/Atlas.git workspace
cd workspace
```

> **Tip:** Fork this repo first, then clone your fork so you can push your own changes.

### 4. Create your personal files from templates

```bash
cp USER.template.md USER.md
cp TOOLS.template.md TOOLS.md
cp MEMORY.template.md MEMORY.md
```

### 5. Customize

- **`SOUL.md`** — Edit to define your AI's personality. This is the most fun part. Make it yours.
- **`USER.md`** — Fill in your info so your AI knows who you are, what you do, your preferences.
- **`TOOLS.md`** — Add your API keys, server details, and tool-specific notes.
- **`HEARTBEAT.md`** — Configure what your AI should check periodically (email, calendar, etc).

### 6. Get an API key

Go to [console.anthropic.com](https://console.anthropic.com) and create an API key. You'll need this for the AI model.

### 7. Configure OpenClaw

```bash
openclaw setup
```

Add your Anthropic API key when prompted.

### 8. Connect a channel

```bash
openclaw channels login
```

Connect Telegram, Discord, or another supported channel. This is how you'll talk to your AI.

### 9. Install Python dependencies (for brain/tools)

```bash
pip install lancedb sentence-transformers anthropic requests playwright
python -m playwright install chromium
```

### 10. Start

```bash
openclaw gateway
```

Your AI is now live. Message it through your connected channel.

---

## Project Structure

```
Atlas/
├── SOUL.md                 # AI personality & behavioral rules
├── AGENTS.md               # Workspace operating manual
├── HEARTBEAT.md            # Periodic task checklist
├── IDENTITY.md             # Quick identity reference
├── .claude.json             # Claude Code project config
│
├── brain/                  # 🧠 Memory system
│   ├── core.py             # Vector DB operations (store/search/consolidate)
│   ├── daemon.py           # Background memory consolidation daemon
│   ├── extractor.py        # Extract facts from conversations
│   ├── hooks.py            # Session lifecycle hooks
│   ├── linker.py           # Cross-reference and link memories
│   ├── predictor.py        # Predict what context might be needed
│   ├── proactive_recall.py # Surface relevant memories automatically
│   ├── search_bridge.py    # Unified search across all memory layers
│   ├── graph.py            # Knowledge graph operations
│   └── ...                 # 30+ modules for memory management
│
├── tools/                  # 🔧 Custom tools
│   ├── research.py         # Web research via Perplexity API
│   ├── browse.py           # Web browsing via Playwright
│   ├── health_check.py     # System health monitoring
│   ├── watchdog.py         # Process watchdog
│   ├── briefing.py         # Daily briefing generator
│   └── ...                 # 30+ tools
│
├── scripts/                # 📜 Utility scripts
│   ├── index_knowledge.py  # Build vector index from knowledge/ files
│   ├── search_knowledge.py # Semantic search over knowledge base
│   ├── status.py           # System status check
│   ├── morning_brief.py    # Morning briefing script
│   └── ...
│
├── ops/                    # ⚙️ Operations
│   ├── dispatch.py         # Task routing and dispatch
│   ├── monitor.py          # System monitoring
│   └── session_start.py    # Session initialization
│
├── knowledge/              # 📚 Knowledge library (Dewey Decimal)
│   ├── 000-reference/      # Quick facts, configs, cheat sheets
│   ├── 100-projects/       # Project documentation
│   ├── 200-trading/        # Domain-specific knowledge (example)
│   ├── 300-personal/       # Personal context files
│   ├── 400-technical/      # Code patterns, architecture docs
│   ├── 500-atlas/          # AI system lessons & capabilities
│   └── 600-tools/          # Tool ecosystem documentation
│
├── memory/                 # 📝 Daily logs
│   └── example-day-1.md    # Example format for daily logs
│
├── skills/                 # 🎯 Skill definitions
│   ├── browser-use/        # Browser automation skill
│   └── claude-code/        # Claude Code integration skill
│
└── templates/              # 📋 Setup templates
    ├── USER.template.md
    ├── TOOLS.template.md
    └── MEMORY.template.md
```

---

## Brain Module (Memory System)

The brain is what makes Atlas different from a stateless chatbot. It's a multi-layer memory system:

| Layer | File/Location | Purpose |
|-------|---------------|---------|
| **Instant Recall** | `MEMORY.md` | Curated facts, credentials, active refs (<20KB) |
| **Daily Logs** | `memory/YYYY-MM-DD.md` | Raw session logs, what happened each day |
| **Staging** | `memory/STAGING.md` | Candidates for promotion to long-term memory |
| **Knowledge Base** | `knowledge/` | Organized reference docs (Dewey Decimal) |
| **Vector DB** | `data/vector_db/` | Semantic search over all memories (auto-generated) |
| **Knowledge Graph** | `brain/graph.db` | Entity relationships and connections (auto-generated) |

### Key Brain Features
- **Automatic extraction** — Facts are pulled from conversations automatically
- **Proactive recall** — Relevant memories surface before you ask
- **Consolidation** — The daemon merges and deduplicates memories over time
- **Graph enrichment** — Entities and relationships are mapped and linked
- **Multi-layer search** — Searches across vector DB, graph, and markdown files

---

## Customization Guide

### Personality (SOUL.md)
This is the most important file. It defines:
- How your AI talks (formal? casual? sarcastic?)
- What it prioritizes (proactive vs reactive)
- Its name, emoji, vibe
- Hard rules (what it won't do)

### Knowledge Library
Drop `.md` files into the appropriate `knowledge/` subfolder:
```bash
# After adding new knowledge files:
python scripts/index_knowledge.py
```

### Adding Tools
Tools are Python scripts in `tools/`. They're self-contained — add a new `.py` file and your AI can use it. Reference it in `TOOLS.md` so your AI knows it exists.

### Heartbeat Tasks
Edit `HEARTBEAT.md` to define what your AI should check periodically:
- Email inbox
- Calendar events
- System health
- Anything you want monitored

---

## Requirements

- **Node.js 22+** (for OpenClaw)
- **Python 3.11+** (for brain/tools)
- **Anthropic API key** (for the AI model)
- **OpenClaw account** (free at [openclaw.com](https://openclaw.com))

### Optional
- Perplexity API key (for `tools/research.py`)
- Playwright + Chromium (for `tools/browse.py`)
- GPU server (for local embeddings — not required, uses API by default)

---

## FAQ

**Q: Can I use a different AI model?**
A: OpenClaw supports multiple models. Configure in `openclaw setup`.

**Q: Where do I put my API keys?**
A: In a `.env` file (gitignored) or in `TOOLS.md` (also gitignored). Never commit secrets.

**Q: How do I add my own knowledge?**
A: Drop markdown files in `knowledge/` and run `python scripts/index_knowledge.py`.

**Q: Can I run this on Linux?**
A: Yes. Replace `brew install` with your package manager. Everything else is the same.

**Q: How do I talk to my AI?**
A: Through whatever channel you connect (Telegram, Discord, etc.) via `openclaw channels login`.

---

## License

MIT — Use it, fork it, make it yours.

---

*Built with [OpenClaw](https://openclaw.com) and Claude.*
