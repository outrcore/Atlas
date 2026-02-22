#!/usr/bin/env python3
"""
Weekly Digest Generator
Reads past 7 days of memory logs + git activity across projects,
produces a clean Monday morning summary.

Usage:
    python tools/weekly_digest.py              # Current week
    python tools/weekly_digest.py --days 14    # Past 14 days
    python tools/weekly_digest.py --output /tmp/digest.md  # Save to file
"""

import os
import sys
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

CLAWD_DIR = Path("/workspace/clawd")
MEMORY_DIR = CLAWD_DIR / "memory"
PROJECTS_DIR = Path("/workspace/projects")
NIGHTLY_BUILDS = MEMORY_DIR / "nightly-builds.md"

# Projects to scan (name, path)
PROJECTS = [
    ("ProjectAlpha", PROJECTS_DIR / "wander"),
    ("ProjectDelta", PROJECTS_DIR / "project_delta"),
    ("HyperClaude Trading", PROJECTS_DIR / "HyperClaude-AMT-Atlas"),
    ("ATLAS Desktop", PROJECTS_DIR / "atlas-desktop-app"),
    ("ProjectBeta", None),  # Remote only — skip git
    ("OpenClaw Config", CLAWD_DIR),
]


def get_date_range(days=7):
    """Get date range for the digest."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    return start, end


def read_memory_logs(start, end):
    """Read daily memory logs for the date range."""
    logs = {}
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        log_path = MEMORY_DIR / f"{date_str}.md"
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8", errors="replace")
            logs[date_str] = content
        current += timedelta(days=1)
    return logs


def get_git_activity(project_name, project_path, start, end):
    """Get git commits for a project in the date range."""
    if project_path is None or not project_path.exists():
        return []

    git_dir = project_path / ".git"
    if not git_dir.exists():
        return []

    since = start.strftime("%Y-%m-%d")
    until = (end + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--no-merges",
             f"--since={since}", f"--until={until}"],
            capture_output=True, text=True, cwd=str(project_path), timeout=10
        )
        commits = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        # Filter out auto-generated commits (sitemaps, etc.)
        meaningful = [c for c in commits if not re.match(r'^[a-f0-9]+ chore: Auto-update', c)]
        return meaningful
    except Exception:
        return []


def extract_highlights(logs):
    """Extract key highlights from daily logs."""
    highlights = []
    decisions = []
    issues = []

    for date, content in sorted(logs.items()):
        lines = content.split("\n")
        for line in lines:
            lower = line.lower().strip()
            # Skip empty lines and headers
            if not lower or lower.startswith("#"):
                continue
            # Look for notable patterns
            if any(kw in lower for kw in ["built", "launched", "deployed", "shipped", "created", "implemented"]):
                highlights.append((date, line.strip().lstrip("- ")))
            elif any(kw in lower for kw in ["decision:", "decided", "pivot", "switched to"]):
                decisions.append((date, line.strip().lstrip("- ")))
            elif any(kw in lower for kw in ["bug", "fix", "broke", "error", "issue", "failed"]):
                issues.append((date, line.strip().lstrip("- ")))

    return highlights, decisions, issues


def get_nightly_builds(start, end):
    """Extract nightly build entries for the date range."""
    if not NIGHTLY_BUILDS.exists():
        return []

    content = NIGHTLY_BUILDS.read_text(encoding="utf-8", errors="replace")
    builds = []

    # Find entries matching our date range
    for date_match in re.finditer(r'## (\d{4}-\d{2}-\d{2})', content):
        date_str = date_match.group(1)
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if start <= entry_date <= end:
                # Get text until next ## or end
                start_pos = date_match.end()
                next_section = content.find("\n## ", start_pos)
                if next_section == -1:
                    entry_text = content[start_pos:].strip()
                else:
                    entry_text = content[start_pos:next_section].strip()

                # Look for **Built: Title** pattern first, fall back to first content line
                built_match = re.search(r'\*\*(?:Built|Task)[:\s]*(.+?)\*\*', entry_text)
                if built_match:
                    builds.append((date_str, built_match.group(1).strip()))
                else:
                    for line in entry_text.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("```"):
                            clean = re.sub(r'\*+', '', line).strip().lstrip("- ")
                            if clean:
                                builds.append((date_str, clean))
                            break
        except ValueError:
            continue

    return builds


def count_log_entries(logs):
    """Count conversation entries per day (by ### headers)."""
    daily_counts = {}
    for date, content in sorted(logs.items()):
        # Count unique ### section headers as distinct sessions
        sections = len(re.findall(r'^### ', content, re.MULTILINE))
        daily_counts[date] = max(sections, 1)
    return daily_counts


def generate_digest(days=7):
    """Generate the weekly digest."""
    start, end = get_date_range(days)
    start_str = start.strftime("%b %d")
    end_str = end.strftime("%b %d, %Y")
    day_name = datetime.utcnow().strftime("%A")

    logs = read_memory_logs(start, end)
    highlights, decisions, issues = extract_highlights(logs)
    daily_counts = count_log_entries(logs)
    nightly_builds = get_nightly_builds(start, end)

    lines = []
    lines.append(f"# Weekly Digest: {start_str} – {end_str}")
    lines.append(f"*Generated {day_name} {datetime.utcnow().strftime('%H:%M UTC')}*")
    lines.append("")

    # Activity overview
    active_days = len(logs)
    total_interactions = sum(daily_counts.values())
    lines.append(f"## Activity")
    lines.append(f"- **{active_days}/{days} days** with logged activity")
    lines.append(f"- **{total_interactions}** conversation sessions tracked")
    lines.append("")

    # Git activity per project
    lines.append("## Project Commits")
    any_commits = False
    for name, path in PROJECTS:
        commits = get_git_activity(name, path, start, end)
        if commits:
            any_commits = True
            lines.append(f"### {name} ({len(commits)} commits)")
            for c in commits[:10]:  # Cap at 10
                lines.append(f"- `{c}`")
            if len(commits) > 10:
                lines.append(f"- *...and {len(commits) - 10} more*")
            lines.append("")

    if not any_commits:
        lines.append("*No meaningful commits this period.*")
        lines.append("")

    # Nightly builds
    if nightly_builds:
        lines.append("## Nightly Builds")
        for date, summary in nightly_builds:
            # Clean up raw formatting artifacts
            clean = re.sub(r'\*+', '', summary).strip()
            if clean and clean != "(09:00 UTC)":
                lines.append(f"- **{date}:** {clean}")
            else:
                lines.append(f"- **{date}:** *(build logged, see nightly-builds.md)*")
        lines.append("")

    # Key highlights (deduplicated, spread across days, top 12)
    if highlights:
        seen = set()
        by_date = defaultdict(list)
        for date, h in highlights:
            key = h[:40].lower()
            if key not in seen:
                seen.add(key)
                by_date[date].append(h)

        # Take up to 2 per day to avoid one day dominating
        unique = []
        for date in sorted(by_date.keys()):
            for h in by_date[date][:2]:
                unique.append((date, h))

        lines.append("## Highlights")
        for date, h in unique[:12]:
            display = h[:120] + "..." if len(h) > 120 else h
            lines.append(f"- [{date}] {display}")
        lines.append("")

    # Decisions (spread across days)
    if decisions:
        seen_d = set()
        by_date_d = defaultdict(list)
        for date, d in decisions:
            key = d[:40].lower()
            if key not in seen_d:
                seen_d.add(key)
                by_date_d[date].append(d)

        unique_d = []
        for date in sorted(by_date_d.keys()):
            for d in by_date_d[date][:2]:
                unique_d.append((date, d))

        lines.append("## Key Decisions")
        for date, d in unique_d[:8]:
            display = d[:120] + "..." if len(d) > 120 else d
            lines.append(f"- [{date}] {display}")
        lines.append("")

    # Issues encountered (spread across days)
    if issues:
        seen_i = set()
        by_date_i = defaultdict(list)
        for date, i in issues:
            key = i[:40].lower()
            if key not in seen_i:
                seen_i.add(key)
                by_date_i[date].append(i)

        unique_i = []
        for date in sorted(by_date_i.keys()):
            for i in by_date_i[date][:2]:
                unique_i.append((date, i))

        lines.append("## Issues & Fixes")
        for date, i in unique_i[:8]:
            display = i[:120] + "..." if len(i) > 120 else i
            lines.append(f"- [{date}] {display}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Next digest: {(end + timedelta(days=7)).strftime('%b %d, %Y')}*")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate weekly digest")
    parser.add_argument("--days", type=int, default=7, help="Number of days to cover")
    parser.add_argument("--output", "-o", type=str, help="Output file (default: stdout)")
    args = parser.parse_args()

    digest = generate_digest(args.days)

    if args.output:
        Path(args.output).write_text(digest, encoding="utf-8")
        print(f"Digest written to {args.output}")
    else:
        print(digest)


if __name__ == "__main__":
    main()
