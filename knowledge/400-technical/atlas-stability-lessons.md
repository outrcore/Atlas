# ATLAS Stability Lessons

*Hard-won lessons from crashes and stability issues. Don't repeat these mistakes!*

## Critical Rule: Don't Spawn 3+ Agents Simultaneously

### What Happened (Feb 1, 2026)
ATLAS spawned too many parallel agents:
- 3 subagents
- 6 Claude Code sessions
- All hitting Anthropic API simultaneously

### The Result
- Rate limits kicked in
- Timeouts
- Instability → Crash
- Had to be restarted manually

### The Fix
> "Lesson learned: Do work sequentially, not in parallel. One agent at a time max."

**Stability Rules Added to MEMORY.md:**
- ❌ Don't use `sessions_spawn` until the crash cause is understood
- ✅ Do complex work sequentially in main session instead
- ✅ Use Claude Code via exec for coding tasks (that's stable)

## Disk Space Causes Silent Crashes

### What Happened
Root filesystem was at **97%** capacity:
- PersonaPlex model: 16GB
- HuggingFace cache: 11GB
- Combined with temp files = full disk

### The Symptom
Silent crashes with no error messages. ATLAS would just stop responding. No logs, no indication of what went wrong.

### The Fix
1. Deleted PersonaPlex (16GB) - wasn't being actively used
2. Moved HuggingFace cache (11GB)
3. Result: 44% disk usage (from 97%)

### Prevention
- Watchdog daemon now monitors disk space
- Logs to `/workspace/clawd/logs/watchdog.log`
- Alerts before hitting critical thresholds

## Gateway Must Run in Screen Session

### What Happened
Gateway was running on `pts/5` (regular terminal, NOT in screen). When terminal window closes → gateway dies.

### The Symptom
ATLAS would become unresponsive whenever Matt closed his terminal or connection dropped.

### The Fix
```bash
# Start gateway in a persistent screen session
screen -dmS Jarvis
screen -S Jarvis -X stuff 'cd /workspace/Jarvis && pnpm openclaw gateway\n'
```

### Infrastructure Files Created
- `start-atlas.sh` - One-command restart
- `atlas-watchdog.sh` - Monitors gateway, auto-restarts if dead
- `post_start.sh` - Bootstrap after pod restart

## Sub-Agent Spawn Crashes Gateway

### What Happened
Testing `sessions_spawn` to create a sub-agent:
- Spawn completed successfully
- Sub-agent responded
- Then... crash. Gateway died silently.

### The Pattern
From Matt's perspective: ATLAS just "ghosted" - no error visible, just silence.

### Current Status
**Avoid `sessions_spawn` entirely** until root cause is identified. Use Claude Code via exec instead.

## Rate Limiting Recovery

### What Happened
401 errors during heavy API usage (overnight builds with multiple Claude Code sessions).

### The Symptom
Anthropic API authentication hiccups - temporary 401 errors leaking through to chat.

### The Solution
- Gateway handles retries automatically
- Space out rapid-fire requests
- Avoid parallel heavy operations
- Error handling catches and suppresses raw error messages

## Quick Reference: Stability Checklist

Before any major operation:
1. ☐ Check disk space (`df -h /`) - should be < 80%
2. ☐ Verify gateway is in screen (`screen -ls | grep Jarvis`)
3. ☐ Don't spawn multiple agents simultaneously
4. ☐ If spawning Claude Code, do ONE at a time
5. ☐ Watchdog running (`screen -ls | grep watchdog`)

---
*Created: 2026-02-04 | Source: Crash analysis and Telegram export*
