#!/usr/bin/env python3
"""
🌅 ATLAS Morning Briefing

A personalized morning report for Matt.
Run this when Matt wakes up for a summary of:
- Weather in Chicago
- What ATLAS built overnight
- System status
- A motivational note

Usage: python morning_brief.py
"""

import subprocess
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# ANSI colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def get_weather():
    """Get Chicago weather using wttr.in"""
    try:
        result = subprocess.run(
            ['curl', '-s', 'wttr.in/Chicago?format=%C+%t+%w&m'],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else "Unable to fetch"
    except:
        return "Weather unavailable"

def get_detailed_weather():
    """Get more detailed weather"""
    try:
        result = subprocess.run(
            ['curl', '-s', 'wttr.in/Chicago?format=%l:+%C+%t+(feels+like+%f)+%w+Humidity:+%h&m'],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None

def get_overnight_builds():
    """Check what was built overnight"""
    builds = []
    
    # Check nightly builds log
    nightly_path = Path("/workspace/clawd/memory/nightly-builds.md")
    if nightly_path.exists():
        content = nightly_path.read_text()
        if datetime.now().strftime("%Y-%m-%d") in content:
            builds.append("📝 Nightly build completed - check memory/nightly-builds.md")
    
    # Check for recent git commits in projects
    projects_dir = Path("/workspace/projects")
    for project in projects_dir.iterdir():
        if project.is_dir() and (project / ".git").exists():
            try:
                result = subprocess.run(
                    ['git', 'log', '--since=8 hours ago', '--oneline'],
                    cwd=project, capture_output=True, text=True, timeout=5
                )
                commits = [l for l in result.stdout.strip().split('\n') if l]
                if commits:
                    builds.append(f"📁 {project.name}: {len(commits)} commit(s)")
                    for c in commits[:3]:  # Show first 3
                        builds.append(f"   └─ {c}")
            except:
                pass
    
    return builds if builds else ["No overnight builds detected"]

def get_system_status():
    """Quick system health check"""
    status = []
    
    # Memory
    try:
        result = subprocess.run(['free', '-h'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        mem_line = lines[1].split()
        status.append(f"💾 Memory: {mem_line[2]} / {mem_line[1]} used")
    except:
        pass
    
    # Screen sessions
    try:
        result = subprocess.run(['screen', '-ls'], capture_output=True, text=True)
        count = result.stdout.count('Detached') + result.stdout.count('Attached')
        status.append(f"🖥️  Screen sessions: {count} running")
    except:
        pass
    
    # Gateway
    try:
        result = subprocess.run(['pgrep', '-f', 'openclaw-gateway'], capture_output=True)
        if result.returncode == 0:
            status.append(f"✅ Gateway: Running")
        else:
            status.append(f"❌ Gateway: Not running!")
    except:
        pass
    
    return status

def get_today_log():
    """Get summary from today's memory log"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = Path(f"/workspace/clawd/memory/{today}.md")
    
    if log_path.exists():
        content = log_path.read_text()
        # Count sections
        sections = content.count("## ")
        lines = len(content.split('\n'))
        return f"📔 Today's log: {sections} sections, {lines} lines"
    return "📔 Today's log: Not started yet"

def get_motivational():
    """Return a motivational message"""
    quotes = [
        "\"The only way to do great work is to love what you do.\" - Steve Jobs",
        "\"Move fast and break things. Unless you are breaking stuff, you are not moving fast enough.\" - Mark Zuckerberg",
        "\"We should be the best duo on the planet.\" - Matt, 2026",
        "\"Build something people want.\" - Y Combinator",
        "\"The best time to plant a tree was 20 years ago. The second best time is now.\"",
        "\"Done is better than perfect.\" - Sheryl Sandberg",
        "Let's make today count. 🚀",
        "Time to build something amazing. 💪",
    ]
    import random
    return random.choice(quotes)

def get_wander_status():
    """Check Wander project status"""
    wander_path = Path("/workspace/projects/wander")
    if not wander_path.exists():
        return None
    
    files = list(wander_path.rglob("*"))
    files = [f for f in files if f.is_file() and '.git' not in str(f)]
    
    return {
        "files": len(files),
        "has_api": (wander_path / "api" / "main.py").exists(),
        "has_landing": (wander_path / "landing-page" / "index.html").exists(),
    }

def print_briefing():
    """Print the full morning briefing"""
    now = datetime.now()
    
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.END}  {Colors.YELLOW}🌅 ATLAS MORNING BRIEFING{Colors.END}                                   {Colors.CYAN}║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.END}  {now.strftime('%A, %B %d, %Y at %I:%M %p')}                       {Colors.CYAN}║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════════════════╝{Colors.END}")
    print()
    
    # Weather
    print(f"{Colors.BOLD}☀️  CHICAGO WEATHER{Colors.END}")
    print(f"   {get_weather()}")
    detailed = get_detailed_weather()
    if detailed:
        print(f"   {detailed}")
    print()
    
    # System Status
    print(f"{Colors.BOLD}🔧 SYSTEM STATUS{Colors.END}")
    for item in get_system_status():
        print(f"   {item}")
    print()
    
    # Overnight Builds
    print(f"{Colors.BOLD}🌙 OVERNIGHT ACTIVITY{Colors.END}")
    for item in get_overnight_builds():
        print(f"   {item}")
    print()
    
    # Wander Project
    wander = get_wander_status()
    if wander:
        print(f"{Colors.BOLD}🚶 WANDER PROJECT{Colors.END}")
        print(f"   📁 Files: {wander['files']}")
        print(f"   🔌 API: {'✅ Ready' if wander['has_api'] else '❌ Missing'}")
        print(f"   🌐 Landing: {'✅ Ready' if wander['has_landing'] else '❌ Missing'}")
        print()
    
    # Today's Log
    print(f"{Colors.BOLD}📝 MEMORY{Colors.END}")
    print(f"   {get_today_log()}")
    print()
    
    # Motivational
    print(f"{Colors.BOLD}💭 THOUGHT FOR TODAY{Colors.END}")
    print(f"   {Colors.GREEN}{get_motivational()}{Colors.END}")
    print()
    
    print(f"{Colors.CYAN}───────────────────────────────────────────────────────────────{Colors.END}")
    print(f"   {Colors.BOLD}Good morning, Matt. Ready when you are.{Colors.END}")
    print(f"{Colors.CYAN}───────────────────────────────────────────────────────────────{Colors.END}")
    print()

if __name__ == "__main__":
    print_briefing()
