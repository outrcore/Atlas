#!/usr/bin/env python3
"""
ATLAS Briefing Generator
========================
Generates morning, evening, weekly, and monthly briefings.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

WORKSPACE = Path("/workspace/clawd")
MEMORY_DIR = WORKSPACE / "memory"
KNOWLEDGE_DIR = WORKSPACE / "knowledge"
PROJECTS_DIR = Path("/workspace/projects")


def get_recent_logs(days: int = 1) -> List[Path]:
    """Get log files from the last N days."""
    logs = []
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        log_file = MEMORY_DIR / f"{date.strftime('%Y-%m-%d')}.md"
        if log_file.exists():
            logs.append(log_file)
    return logs


def parse_log_highlights(log_file: Path) -> Dict[str, Any]:
    """Extract highlights from a daily log."""
    highlights = {
        "file": log_file.name,
        "tasks_completed": [],
        "lessons_learned": [],
        "decisions_made": [],
        "projects_touched": [],
        "interesting_facts": [],
    }
    
    try:
        content = log_file.read_text()
        lines = content.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            if any(x in line_lower for x in ['completed', 'finished', 'done', '✅', 'fixed']):
                highlights["tasks_completed"].append(line.strip()[:100])
            if any(x in line_lower for x in ['learned', 'lesson', 'realized', 'discovered']):
                highlights["lessons_learned"].append(line.strip()[:100])
            if any(x in line_lower for x in ['decided', 'decision', 'chose', 'going with']):
                highlights["decisions_made"].append(line.strip()[:100])
            if any(x in line_lower for x in ['project_alpha', 'wander', 'project', 'repo']):
                highlights["projects_touched"].append(line.strip()[:100])
                
    except Exception as e:
        highlights["error"] = str(e)
    
    return highlights


def get_staging_candidates() -> List[str]:
    """Get candidates from STAGING.md."""
    staging_file = MEMORY_DIR / "STAGING.md"
    candidates = []
    
    if staging_file.exists():
        content = staging_file.read_text()
        for line in content.split('\n'):
            if line.startswith('- '):
                candidates.append(line[2:].strip()[:100])
    
    return candidates[-20:]  # Last 20


def get_system_health() -> Dict[str, Any]:
    """Get basic system health info."""
    import subprocess
    
    health = {}
    
    # Disk usage
    try:
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if '/' in line and not line.startswith('Filesystem'):
                parts = line.split()
                if len(parts) >= 5:
                    health["disk_used"] = parts[4]
    except:
        health["disk_used"] = "unknown"
    
    # Screen sessions
    try:
        result = subprocess.run(['screen', '-ls'], capture_output=True, text=True)
        screens = [l.strip() for l in result.stdout.split('\n') if 'Detached' in l or 'Attached' in l]
        health["active_screens"] = len(screens)
        health["key_screens"] = [s.split('.')[1].split('\t')[0] for s in screens[:5]]
    except:
        health["active_screens"] = 0
    
    # GPU (if available)
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            if len(parts) == 2:
                used, total = int(parts[0]), int(parts[1])
                health["gpu_memory"] = f"{used}/{total} MB ({100*used//total}%)"
    except:
        pass
    
    return health


def get_git_activity(days: int = 1) -> List[Dict]:
    """Get recent git commits from projects."""
    import subprocess
    
    activity = []
    
    for project_dir in PROJECTS_DIR.iterdir():
        if (project_dir / '.git').exists():
            try:
                result = subprocess.run(
                    ['git', 'log', f'--since={days} days ago', '--oneline', '-5'],
                    cwd=project_dir,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    commits = result.stdout.strip().split('\n')
                    activity.append({
                        "project": project_dir.name,
                        "commits": len(commits),
                        "recent": commits[:3]
                    })
            except:
                pass
    
    return activity


def generate_morning_briefing() -> str:
    """Generate morning briefing content."""
    briefing = []
    briefing.append("🌅 **Morning Briefing**\n")
    
    # What I did overnight
    logs = get_recent_logs(1)
    if logs:
        highlights = parse_log_highlights(logs[0])
        if highlights["tasks_completed"]:
            briefing.append("**Overnight Work:**")
            for task in highlights["tasks_completed"][:5]:
                briefing.append(f"  • {task}")
            briefing.append("")
    
    # Git activity
    git_activity = get_git_activity(1)
    if git_activity:
        briefing.append("**Commits:**")
        for proj in git_activity[:3]:
            briefing.append(f"  • {proj['project']}: {proj['commits']} commits")
        briefing.append("")
    
    # System health
    health = get_system_health()
    briefing.append("**System Health:**")
    briefing.append(f"  • Disk: {health.get('disk_used', 'N/A')}")
    briefing.append(f"  • Screens: {health.get('active_screens', 0)} active")
    if health.get('gpu_memory'):
        briefing.append(f"  • GPU: {health['gpu_memory']}")
    briefing.append("")
    
    # Staging candidates to review
    candidates = get_staging_candidates()
    if candidates:
        briefing.append(f"**Memory Staging:** {len(candidates)} candidates to review")
    
    return '\n'.join(briefing)


def generate_evening_briefing() -> str:
    """Generate evening briefing content."""
    briefing = []
    briefing.append("🌆 **Evening Briefing**\n")
    
    # Day's highlights
    logs = get_recent_logs(1)
    if logs:
        highlights = parse_log_highlights(logs[0])
        
        if highlights["tasks_completed"]:
            briefing.append(f"**Completed Today:** {len(highlights['tasks_completed'])} tasks")
            for task in highlights["tasks_completed"][:5]:
                briefing.append(f"  • {task}")
            briefing.append("")
        
        if highlights["lessons_learned"]:
            briefing.append("**Lessons Learned:**")
            for lesson in highlights["lessons_learned"][:3]:
                briefing.append(f"  • {lesson}")
            briefing.append("")
    
    # Projects touched
    git_activity = get_git_activity(1)
    if git_activity:
        briefing.append("**Projects Touched:**")
        for proj in git_activity:
            briefing.append(f"  • {proj['project']}: {proj['commits']} commits")
            if proj['recent']:
                briefing.append(f"    Latest: {proj['recent'][0]}")
        briefing.append("")
    
    # Memory promotions
    candidates = get_staging_candidates()
    if candidates:
        briefing.append(f"**Memory Candidates:** {len(candidates)} items in staging")
        briefing.append("  Will review during next maintenance cycle")
    
    return '\n'.join(briefing)


def generate_weekly_summary() -> str:
    """Generate weekly summary content."""
    briefing = []
    briefing.append("📊 **Weekly Summary**\n")
    
    # Week's highlights
    logs = get_recent_logs(7)
    all_tasks = []
    all_lessons = []
    
    for log in logs:
        highlights = parse_log_highlights(log)
        all_tasks.extend(highlights["tasks_completed"])
        all_lessons.extend(highlights["lessons_learned"])
    
    briefing.append(f"**This Week:**")
    briefing.append(f"  • {len(all_tasks)} tasks completed")
    briefing.append(f"  • {len(all_lessons)} lessons learned")
    briefing.append(f"  • {len(logs)} days logged")
    briefing.append("")
    
    # Git activity for week
    git_activity = get_git_activity(7)
    if git_activity:
        total_commits = sum(p['commits'] for p in git_activity)
        briefing.append(f"**Code Activity:** {total_commits} total commits")
        for proj in git_activity[:5]:
            briefing.append(f"  • {proj['project']}: {proj['commits']} commits")
        briefing.append("")
    
    # Top lessons
    if all_lessons:
        briefing.append("**Key Learnings:**")
        for lesson in all_lessons[:5]:
            briefing.append(f"  • {lesson}")
    
    return '\n'.join(briefing)


def generate_monthly_summary() -> str:
    """Generate monthly summary content."""
    briefing = []
    briefing.append("📅 **Monthly Summary**\n")
    
    # Month's highlights
    logs = get_recent_logs(30)
    all_tasks = []
    all_lessons = []
    
    for log in logs:
        highlights = parse_log_highlights(log)
        all_tasks.extend(highlights["tasks_completed"])
        all_lessons.extend(highlights["lessons_learned"])
    
    briefing.append(f"**This Month:**")
    briefing.append(f"  • {len(all_tasks)} tasks completed")
    briefing.append(f"  • {len(all_lessons)} lessons learned")
    briefing.append(f"  • {len(logs)} days logged")
    briefing.append("")
    
    # Git activity for month
    git_activity = get_git_activity(30)
    if git_activity:
        total_commits = sum(p['commits'] for p in git_activity)
        briefing.append(f"**Code Activity:** {total_commits} total commits")
        for proj in sorted(git_activity, key=lambda x: x['commits'], reverse=True)[:5]:
            briefing.append(f"  • {proj['project']}: {proj['commits']} commits")
        briefing.append("")
    
    # Memory file stats
    memory_file = WORKSPACE / "MEMORY.md"
    if memory_file.exists():
        size = memory_file.stat().st_size
        briefing.append(f"**Memory Health:**")
        briefing.append(f"  • MEMORY.md: {size/1024:.1f} KB")
    
    return '\n'.join(briefing)


if __name__ == "__main__":
    import sys
    
    briefing_type = sys.argv[1] if len(sys.argv) > 1 else "morning"
    
    if briefing_type == "morning":
        print(generate_morning_briefing())
    elif briefing_type == "evening":
        print(generate_evening_briefing())
    elif briefing_type == "weekly":
        print(generate_weekly_summary())
    elif briefing_type == "monthly":
        print(generate_monthly_summary())
    else:
        print(f"Unknown briefing type: {briefing_type}")
        print("Usage: python briefing.py [morning|evening|weekly|monthly]")
