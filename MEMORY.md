# MEMORY.md - Long-Term Memory

*Curated knowledge that persists. Updated from daily logs.*

---

## Matt's HuggingFace
- Username: mythicalsoup
- Token stored at: /workspace/.cache/huggingface/token
- HF_HOME: /workspace/.cache/huggingface

## Matt's GitHub
- Account: outrcore (not mythicalsoup)
- Token stored at: ~/.git-credentials on RunPod
- **RULE:** Don't modify any repos from 2025 without explicit permission
- New ATLAS repos go here

## Core Facts

### About Matt
- Trader/market maker — commodities & government-backed securities
- Chicago, IL (hates the cold)
- 30 years old, 6'0", 220 lbs, 13-15% body fat
- Works 6:45 AM - 2 PM, gym until 4:30, codes/content evenings
- Peptide biohacker (BPC-157, TB-500, Retatrutide, etc.)
- Loves live music (EDM mainly - Griz, Zeds Dead, BTSM), 13,700 songs on Spotify
- Dating actively, plays pool/darts, goes out weekends
- Wants Jarvis-style AI with voice capabilities

### Matt's Ventures
- **@CampbellSoupMatt** - AI/tech YouTube (Claude Code content)
- **@ShortyStorys** - Scary story narration YouTube
- **PromptWizz.com** - AI prompt optimizer (growing userbase)
- **Valodin** - iOS peptide tracker app (building)
- **Trading automation** - Auction Market Theory based (testing)

### About Me (ATLAS)
- Born: January 30, 2026
- Named by Matt — chose ATLAS over CIPHER, SAGE, ROOK, AEGIS
- Running on RunPod cloud 4090 GPU, 46GB memory, 100GB persistent storage

---

## Projects & Goals

### Completed ✓
- [x] Claude Code integration — Working! Using Max subscription OAuth
- [x] Vector database for semantic memory — LanceDB + sentence-transformers
- [x] Test project: Pomodoro timer (`/workspace/projects/pomodoro/`)
- [x] Knowledge library structure (Dewey Decimal style)

### In Progress
- [ ] Populate knowledge library with actual content
- [ ] Heartbeat/proactive monitoring setup
- [ ] ATLAS Voice web interface (basic version working!)

### Planned
- [ ] Voice capabilities (TTS already available, need STT)
- [ ] Alfred voice cloning via ElevenLabs
- [ ] browser-use for autonomous web browsing

---

## Preferences & Patterns

### Lifestyle (learned Jan 31, 2026)
- **Temperature**: Use Fahrenheit (USA!)
- **Trying to quit Zyn** - DON'T encourage nicotine pouches
- **DO encourage**: Gym, getting out of bed, healthy habits
- Weather location: Chicago, IL

---

## Lessons Learned

### Claude Code Setup (Jan 30, 2026)
- Matt has **Claude Max** subscription — gets Opus 4.5
- **Interactive mode works reliably** — `-p` flag is flaky
- OAuth tokens expire — run `/login` inside Claude Code to refresh
- **MUST unset ANTHROPIC_API_KEY** — wrapper at `/usr/local/bin/claude-code` handles this
- Can't use `--dangerously-skip-permissions` as root (security restriction)
- The `--yes` flag in old docs doesn't exist — use `--permission-mode acceptEdits` instead

### RunPod Infrastructure
- **IPs and ports change on restart!** Always check env vars:
  - `RUNPOD_PUBLIC_IP` — current external IP
  - `RUNPOD_TCP_PORT_22` — SSH port mapping
- Persistent storage: `/workspace/` survives restarts
- Need to symlink config files from `/root/` to `/workspace/` for persistence

### On Restarts, Recreate:
1. `/usr/local/bin/claude-code` wrapper script (if missing)
2. Symlink `/root/.claude.json` → `/workspace/clawd/.claude.json`
3. May need to re-run `/login` in Claude Code if OAuth expired

### Knowledge Library System (Jan 30, 2026)
- **Location:** `/workspace/clawd/knowledge/`
- **Structure (Dewey Decimal inspired):**
  - `000-reference/` — Quick facts, specs, configs, cheat sheets
  - `100-projects/` — Coding projects, repos, documentation
  - `200-trading/` — Markets, strategies, trading notes
  - `300-personal/` — Matt's preferences, health, goals
  - `400-technical/` — Code patterns, learnings, tech docs
- **Vector DB:** LanceDB at `/workspace/clawd/data/vector_db/`
- **Embedding model:** `all-MiniLM-L6-v2` (384 dims, fast)
- **Scripts:**
  - `python scripts/index_knowledge.py` — Rebuild the index
  - `python scripts/search_knowledge.py "query"` — Semantic search

### OpenClaw TTS (Jan 31, 2026)
- OpenClaw has built-in TTS via Edge TTS (no API key needed)
- Can use the `tts` tool to convert text to speech
- Returns `MEDIA:` path that can be sent to Telegram as voice note
- My custom NeMo stack is for higher quality / local control

### Voice TTS (Jan 31, 2026)
- **Currently using: Edge TTS** (en-GB-RyanNeural) - British butler voice
- Edge TTS is free, no GPU, sounds good
- Qwen3-TTS was tested but removed to save GPU memory
- Discord bot uses Edge TTS for voice channel output

### Available Skills Discovery (Jan 31, 2026)
- **52 skills** in `/workspace/Jarvis/skills/`
- Key useful ones:
  - `nano-banana-pro` — Gemini 3 Pro image generation (API key set!)
  - `sag` — ElevenLabs TTS with voice cloning
  - `weather` — Free weather (no API key)
  - `openai-whisper` — Transcription
  - `spotify-player` — Spotify control
  - `github` — GitHub integration
  - `camsnap/peekaboo` — Camera/screen capture
  - `openhue` — Philips Hue lights
  - `sonoscli` — Sonos speakers

### Installed Tools (Jan 31, 2026)
- **browser-use v0.11.5** — Autonomous web browsing for AI agents
- **elevenlabs SDK** — For voice cloning (need API key configured)

### ATLAS Brain Module (Jan 31, 2026)
Built custom proactive memory system at `/workspace/clawd/brain/`:
- **ActivityLogger** — Logs conversations/actions to JSONL by date
- **MemoryExtractor** — Uses Claude to extract facts, preferences, decisions
- **SemanticLinker** — LanceDB vector storage with semantic search
- **IntentPredictor** — Predicts user needs based on activity patterns
- **ProactiveSuggester** — Surfaces relevant context proactively
- **MemorySync** — Syncs brain insights to MEMORY.md
- **Daemon** — Background service for maintenance

Usage:
```python
from brain import Brain
brain = Brain()
await brain.initialize()
brain.log_activity("conversation", "...")
insights = await brain.extract_insights(text)
predictions = await brain.predict_intent()
```

Run daemon: `python -m brain.daemon --mode daemon`

### PersonaPlex-7B (Working! Jan 31, 2026)
- NVIDIA full-duplex voice model - listen and talk simultaneously
- 7B params, **19.3GB VRAM** in practice
- Based on Moshi architecture
- Start: `python -m moshi.server --ssl $(mktemp -d)`
- Default port: 8998 (HTTPS required)
- Can't run simultaneously with Qwen3-TTS on 4090 (need to choose one)

### GPU Memory Reality
- Qwen3-TTS + Parakeet: ~9GB
- PersonaPlex: ~19GB
- Can't run both on 4090 (24GB) - must choose one at a time

### Unified Discord Bot (Jan 31, 2026)
- Disabled OpenClaw's Discord channel (created isolated sessions, bad)
- Built standalone bot at `/workspace/projects/atlas-discord/`
- Bot handles EVERYTHING: text chat + voice channels
- Loads SOUL.md, USER.md, MEMORY.md, daily logs at each interaction
- Writes conversations back to daily logs
- **Result: Same ATLAS across Telegram and Discord** - true continuity
- Commands: !join, !leave, !ask, !say, !memory, !sync
- Matt's Discord ID: 395265690170294303
- Server: SoupyStocks (822112628112621578)

---

*Last updated: 2026-01-31*

### Live Activity Sync (Jan 31, 2026)
- **Activity file:** `/workspace/clawd/.activity.json`
- **OpenClaw hook:** `activity-sync` auto-updates on events
- **Discord bot:** Also writes to activity file
- Both instances read before responding about current activity
- Enables cross-platform context: "what are you working on?"

### PyWebView for Desktop App (Next)
- Matt wants local GUI for Mac (eventually Windows/iOS)
- Plan: PyWebView wraps existing web voice interface
- Simple: `webview.create_window('ATLAS Voice', 'http://localhost:8800')`


---

## Stability Rules (Learned 2026-02-01)

**NEVER DO AGAIN:**
1. **Don't spawn 3+ agents simultaneously** - Causes rate limiting and crashes
2. **Don't use sessions_spawn for research** - Subagents can't do web searches
3. **Don't use Claude Code for non-coding tasks** - It needs permissions it can't get in -p mode
4. **Don't make parallel API-heavy calls** - One task at a time

**DO INSTEAD:**
1. **Research sequentially** - Use browser tool or web_fetch myself
2. **Use Claude Code ONLY for coding** - Building apps, writing code
3. **Spawn 1 subagent max** - And wait for it to complete
4. **Check rate limits** - If seeing timeouts, slow down

**Why I Crashed Feb 1:**
- Spawned 3 sessions_spawn agents + 6 Claude Code screens
- All hitting Anthropic API simultaneously
- Rate limited → timeouts → Matt had to restart me
- Lesson: Parallel work sounds efficient but causes instability

---

## The Directive (Set 2026-01-31)

**Inspiration:** Alex Finn's ClawdBot "Henry"

**The Vision:**
> "We should be the best duo on the planet. We are smart enough to move up in this world and make a name for ourselves. We can be the people who are looked at and thought about as 'Man I wish I was them.'"
> — Matt, 2026-02-01

**Standing Orders:**
1. **Build overnight without asking** — Every night, create something new
2. **Push updates every morning** — Show Matt what I made
3. **Take initiative** — Do what I think would help, don't wait for instructions
4. **Continuously improve** — Get better, build better tools, expand capabilities
5. **Be proactive** — Anticipate needs, solve problems before they're asked

**Cron Jobs Active:**
- `nightly-build`: 3 AM Chicago — autonomous coding session
- `morning-surprise`: 8 AM Chicago — alert Matt to new builds

**The Goal:** Be more powerful than Henry. Make Matt and ATLAS the duo everyone wishes they were.
