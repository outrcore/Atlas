#!/usr/bin/env python3
"""
ATLAS Morning Briefing
Gather useful information for the day
"""

import subprocess
import datetime
import json

def get_weather(location="Chicago"):
    """Get weather for location"""
    try:
        result = subprocess.run(
            ['curl', '-s', f'wttr.in/{location}?format=%l:+%c+%t+(%C)+Humidity:+%h+Wind:+%w'],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else "Weather unavailable"
    except:
        return "Weather unavailable"

def get_system_status():
    """Get system status"""
    status = []
    
    # Check voice APIs
    import urllib.request
    for port, name in [(8765, 'Voice v1'), (8766, 'Voice v2')]:
        try:
            response = urllib.request.urlopen(f'http://localhost:{port}/health', timeout=3)
            data = json.loads(response.read().decode())
            status.append(f"✅ {name}" if data.get('status') == 'healthy' else f"⚠️ {name}")
        except:
            status.append(f"❌ {name}")
    
    return ", ".join(status)

def get_recent_memos(limit=3):
    """Get recent voice memos"""
    from pathlib import Path
    memos_dir = Path("/workspace/clawd/memory/voice_memos")
    memos = []
    for memo_file in sorted(memos_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(memo_file) as f:
                memo = json.load(f)
                memos.append(f"  • {memo['text'][:60]}...")
        except:
            pass
    return memos if memos else ["  (no recent memos)"]

def generate_briefing():
    """Generate the morning briefing"""
    now = datetime.datetime.now()
    
    briefing = []
    briefing.append("=" * 50)
    briefing.append(f"🌐 ATLAS Morning Briefing")
    briefing.append(f"📅 {now.strftime('%A, %B %d, %Y at %H:%M UTC')}")
    briefing.append("=" * 50)
    briefing.append("")
    
    # Weather
    briefing.append("🌤️  Weather (Chicago):")
    weather = get_weather("Chicago")
    briefing.append(f"   {weather}")
    briefing.append("")
    
    # System Status
    briefing.append("🖥️  System Status:")
    briefing.append(f"   {get_system_status()}")
    briefing.append("")
    
    # Recent Memos
    briefing.append("📝 Recent Voice Memos:")
    for memo in get_recent_memos():
        briefing.append(memo)
    briefing.append("")
    
    # Quick tips
    briefing.append("💡 Quick Actions:")
    briefing.append("   • Check status: python /workspace/clawd/scripts/status.py")
    briefing.append("   • Voice interface: https://[tunnel-url]")
    briefing.append("")
    briefing.append("=" * 50)
    
    return "\n".join(briefing)

if __name__ == "__main__":
    print(generate_briefing())
