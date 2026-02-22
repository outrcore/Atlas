# HEARTBEAT.md - Periodic Tasks

When this heartbeat fires, check the following:

## 🏥 Health Check (Every heartbeat - FIRST!)
Run health check to catch issues early:
```bash
python /workspace/clawd/tools/health_check.py
```
If status is WARNING or CRITICAL, alert Matt unless it's late night.

## 🔐 Auth Check (Every heartbeat)
Check OAuth/API key status:
```bash
python /workspace/clawd/tools/auth_monitor.py
```
Alert Matt if:
- OAuth token expired or expiring soon (< 2 hours)
- OAuth profile in cooldown (means it failed)
- Currently using API key instead of OAuth (costs money)

**If OAuth needs refresh:** Tell Matt to run on the server:
```bash
# Generate new setup-token (requires browser auth)
claude setup-token
# Then paste into OpenClaw
openclaw models auth paste-token --provider anthropic
```

## 🧠 Brain Maintenance (Every heartbeat)

### 1. Check brain daemon is running:
```bash
screen -ls | grep brain-daemon
```
If not running, restart it:
```bash
screen -dmS brain-daemon python -m brain.daemon --mode daemon
```

### 2. Run maintenance:
```bash
cd /workspace/clawd && python -c "
import asyncio
from brain import Brain

async def maintain():
    brain = Brain()
    await brain.initialize()
    await brain.run_maintenance()
    print('Brain maintenance complete')

asyncio.run(maintain())
" 2>/dev/null
```

### 3. Memory Management
- **Daily logs:** Write important context to `/workspace/clawd/memory/YYYY-MM-DD.md`
- **STAGING review:** Check `/workspace/clawd/memory/STAGING.md` every few heartbeats
  - If good candidates, manually promote to MEMORY.md or knowledge library
  - Delete noise and duplicates
- **MEMORY.md:** Only manually curated essentials (<20KB limit!)
  - Don't auto-append — brain daemon writes to STAGING.md now
  - Keep it small: credentials, core facts, active project refs

## 📊 Quick Status Check
- Voice server running? `screen -ls | grep atlas-voice`
- GPU memory OK? (< 95%)
- Any errors in logs?

## 🎯 Orchestration Check (Every heartbeat)
Check active work and sub-agents:
```bash
python /workspace/clawd/ops/dispatch.py status
python /workspace/clawd/ops/monitor.py
```
- Update task statuses based on monitor output
- If a sub-agent finished, check its results via `sessions_history`
- Complete tasks that are done: `python ops/dispatch.py complete <id> --result "..."`
- If training completed, auto-launch next variant

## 🧠 UMA Maintenance (Every few heartbeats)
Run memory maintenance (decay + Hebbian boosting):
```bash
curl -s http://127.0.0.1:18790/maintenance | python -m json.tool 2>/dev/null
```
Run consolidation less frequently (once a day max):
```bash
curl -s "http://127.0.0.1:18790/maintenance?consolidate=1" | python -m json.tool 2>/dev/null
```
Only alert if consolidation merged nodes or if errors occur.

## 📚 Knowledge Index (Every few heartbeats)
Re-index knowledge library if files have changed:
```bash
python /workspace/clawd/scripts/auto_index.py
```
Only re-indexes when files actually changed - fast no-op otherwise.

## 🔧 Project Monitor (Every few heartbeats)
Check project status for issues:
```bash
cd /workspace/clawd && python tools/project_monitor.py --alerts-only 2>/dev/null
```
Alert Matt if there are critical issues (uncommitted changes > 10, projects behind remote, etc.).

## 🔔 Only Alert If:
- Something needs Matt's attention
- An action item is overdue
- System issue detected

## ⏰ Time-Aware Behavior
- **Morning (7-10 AM CST)**: Can offer daily briefing if interesting
- **Evening (after 6 PM CST)**: Can summarize the day if asked
- **Night (11 PM - 7 AM CST)**: Heartbeats disabled via activeHours

## 📝 Rules
1. If nothing needs attention → reply `HEARTBEAT_OK`
2. Don't repeat old tasks from prior chats
3. Keep alerts brief and actionable
4. Don't message just to message
