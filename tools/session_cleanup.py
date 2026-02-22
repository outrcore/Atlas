#!/usr/bin/env python3
"""
Session Cleanup Utility
Safely removes orphaned, deleted, and backup session files from OpenClaw.
Run with --dry-run first to preview what will be removed.

Usage:
    python tools/session_cleanup.py              # Dry run (preview only)
    python tools/session_cleanup.py --execute    # Actually delete files
"""

import os
import sys
import json
import glob
from datetime import datetime, timezone

SESSIONS_DIR = "/root/.openclaw/agents/main/sessions"
SESSIONS_JSON = os.path.join(SESSIONS_DIR, "sessions.json")


def get_active_session_ids():
    """Read sessions.json and return set of active session IDs."""
    if not os.path.exists(SESSIONS_JSON):
        print("⚠️  sessions.json not found")
        return set()

    with open(SESSIONS_JSON, "r") as f:
        data = json.load(f)

    active_ids = set()
    if isinstance(data, dict):
        for key, session in data.items():
            if isinstance(session, dict):
                sid = session.get("sessionId", "")
                if sid:
                    active_ids.add(sid)
                # Also check transcriptPath
                tp = session.get("transcriptPath", "")
                if tp:
                    # Extract session ID from filename
                    base = os.path.basename(tp).replace(".jsonl", "")
                    active_ids.add(base)
    return active_ids


def scan_sessions():
    """Scan sessions directory and categorize files."""
    if not os.path.exists(SESSIONS_DIR):
        print(f"❌ Sessions directory not found: {SESSIONS_DIR}")
        return None

    active_ids = get_active_session_ids()
    
    categories = {
        "deleted": [],       # *.deleted.* files
        "backup": [],        # *.bak, *.backup, *.corrupted.backup*
        "orphaned": [],      # .jsonl files not in sessions.json
        "active": [],        # Active session files
        "other": [],         # sessions.json, etc.
    }

    for entry in os.scandir(SESSIONS_DIR):
        if not entry.is_file():
            continue

        name = entry.name
        size = entry.stat().st_size
        mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
        info = {"name": name, "path": entry.path, "size": size, "mtime": mtime}

        if ".deleted." in name:
            categories["deleted"].append(info)
        elif name.endswith((".bak", ".backup")) or ".corrupted.backup" in name:
            categories["backup"].append(info)
        elif name == "sessions.json":
            categories["other"].append(info)
        elif name.endswith(".jsonl"):
            # Check if this session is active
            session_id = name.replace(".jsonl", "")
            if session_id in active_ids:
                categories["active"].append(info)
            else:
                categories["orphaned"].append(info)
        else:
            categories["other"].append(info)

    return categories


def format_size(size_bytes):
    """Format bytes to human-readable."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def main():
    execute = "--execute" in sys.argv

    print("=" * 60)
    print("🧹 ATLAS Session Cleanup Utility")
    print(f"📂 Directory: {SESSIONS_DIR}")
    print(f"🔧 Mode: {'EXECUTE (will delete!)' if execute else 'DRY RUN (preview only)'}")
    print("=" * 60)
    print()

    categories = scan_sessions()
    if categories is None:
        return

    # Summary
    total_removable = 0
    total_removable_size = 0

    for cat_name, label in [("deleted", "🗑️  Deleted files"), 
                             ("backup", "💾 Backup files"),
                             ("orphaned", "👻 Orphaned sessions")]:
        files = categories[cat_name]
        cat_size = sum(f["size"] for f in files)
        total_removable += len(files)
        total_removable_size += cat_size

        print(f"{label}: {len(files)} files ({format_size(cat_size)})")
        if files and len(files) <= 10:
            for f in sorted(files, key=lambda x: -x["size"]):
                print(f"  - {f['name']} ({format_size(f['size'])})")
        elif files:
            # Show top 5 by size
            for f in sorted(files, key=lambda x: -x["size"])[:5]:
                print(f"  - {f['name']} ({format_size(f['size'])})")
            print(f"  ... and {len(files) - 5} more")
        print()

    active = categories["active"]
    print(f"✅ Active sessions: {len(active)} files ({format_size(sum(f['size'] for f in active))})")
    print()

    print("-" * 60)
    print(f"📊 Total removable: {total_removable} files ({format_size(total_removable_size)})")
    print("-" * 60)

    if not execute:
        print()
        print("ℹ️  This was a dry run. To actually delete, run:")
        print("    python tools/session_cleanup.py --execute")
        return

    # Execute cleanup
    removed_count = 0
    removed_size = 0

    for cat_name in ["deleted", "backup", "orphaned"]:
        for f in categories[cat_name]:
            try:
                os.remove(f["path"])
                removed_count += 1
                removed_size += f["size"]
            except OSError as e:
                print(f"  ❌ Failed to remove {f['name']}: {e}")

    print()
    print(f"✅ Removed {removed_count} files, freed {format_size(removed_size)}")


if __name__ == "__main__":
    main()
