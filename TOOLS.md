# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## Claude

- **Command:** `claude` (wrapper at `/usr/local/bin/claude`)
- **Why wrapper?** Unsets `ANTHROPIC_API_KEY` which conflicts with OpenClaw's token
- **Auth:** OAuth token via Matt's **Claude Max** subscription (persists ~1 year)
- **Token location:** `/workspace/clawd/.claude/.credentials.json` (persistent storage)
- **Model:** Opus 4.5 (Max tier)
- **Projects dir:** `/workspace/projects/`

### Usage Notes
- **Interactive mode is reliable** — just run `claude`, then type your task
- **`-p` flag is flaky** — fails if OAuth token expired
- **Permission flags:** `--permission-mode acceptEdits` (auto-approve edits, still asks for bash)
- **Can't use `--dangerously-skip-permissions` as root** (security restriction)

### If OAuth Ever Expires (~1 year)
1. Run `claude` interactively
2. Type `/login`
3. Select option 1 (Claude subscription)
4. Open URL in browser, authorize, paste code back

## RunPod Server

- **IP:** Changes on restart! Check `$RUNPOD_PUBLIC_IP`
- **SSH Port:** Changes on restart! Check `$RUNPOD_TCP_PORT_22`
- **User:** root
- **GPU:** 4090 (46GB memory, 100GB storage)
- **Persistent storage:** `/workspace/` (survives restarts)

### Current Connection (may be stale)
```bash
ssh root@$RUNPOD_PUBLIC_IP -p $RUNPOD_TCP_PORT_22
```

## VNC Access (if needed)

- Port 5900 via SSH tunnel
- Start: `screen -dmS vnc` + Xvfb/x11vnc commands
- Connect: `ssh -L 5900:localhost:5900 root@$RUNPOD_PUBLIC_IP -p $RUNPOD_TCP_PORT_22`

## Knowledge Library

- **Location:** `/workspace/clawd/knowledge/`
- **Categories:**
  - `000-reference/` — Quick facts, configs, cheat sheets
  - `100-projects/` — Project docs
  - `200-trading/` — Market notes
  - `300-personal/` — Matt's info
  - `400-technical/` — Code patterns

### Commands
```bash
# Rebuild vector index (after adding content)
python /workspace/clawd/scripts/index_knowledge.py

# Semantic search
python /workspace/clawd/scripts/search_knowledge.py "your query" [limit] [category]
```

### Adding Knowledge
Just drop `.md` files in the appropriate folder and run the indexer.

## ATLAS Custom Scripts

### Status Check
```bash
python /workspace/clawd/scripts/status.py
```
Shows: Voice APIs, tunnel URL, GPU status, screen sessions

### Morning Briefing
```bash
python /workspace/clawd/scripts/morning_brief.py
```
Shows: Weather (Chicago), system status, recent memos

### Voice Services Startup (after RunPod restart)
```bash
/workspace/projects/voice-stack/start_services.sh
```
Starts: Voice API v1 (8765), v2 (8766), Cloudflare tunnel

### Voice Memo System
```bash
python /workspace/projects/voice-stack/voice_memo.py transcribe <audio.wav>
python /workspace/projects/voice-stack/voice_memo.py list [limit]
python /workspace/projects/voice-stack/voice_memo.py search <query>
```
Memos stored in: `/workspace/clawd/memory/voice_memos/`

---

Add whatever helps you do your job. This is your cheat sheet.
