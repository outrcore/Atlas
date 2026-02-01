# HEARTBEAT.md - Periodic Tasks

When this heartbeat fires, check the following:

## 🧠 Brain Maintenance (Every heartbeat)
Run brain maintenance to process recent conversations:
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

## 📊 Quick Status Check
- Voice server running? `screen -ls | grep atlas-voice`
- GPU memory OK? (< 95%)
- Any errors in logs?

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
