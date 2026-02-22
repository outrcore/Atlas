#!/usr/bin/env python3
"""
ATLAS Orchestration Dispatch System

Lightweight task tracking + sub-agent orchestration.
Designed to be called from ATLAS's main session or via cron jobs.

Usage:
    python ops/dispatch.py status              # Show all active work
    python ops/dispatch.py add <title> [--priority high|normal|low] [--type project|task|research]
    python ops/dispatch.py update <id> <status> [--note "..."]
    python ops/dispatch.py complete <id> [--result "..."]
    python ops/dispatch.py log                 # Show recent completed work
    python ops/dispatch.py clean               # Archive completed tasks older than 24h
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

OPS_DIR = Path(__file__).parent
TASKS_FILE = OPS_DIR / "tasks.json"
ARCHIVE_FILE = OPS_DIR / "archive.json"

# ── Data Layer ────────────────────────────────────────────

def _load_tasks() -> dict:
    if TASKS_FILE.exists():
        return json.loads(TASKS_FILE.read_text())
    return {"active": [], "completed": []}

def _save_tasks(data: dict):
    TASKS_FILE.write_text(json.dumps(data, indent=2))

def _load_archive() -> list:
    if ARCHIVE_FILE.exists():
        return json.loads(ARCHIVE_FILE.read_text())
    return []

def _save_archive(data: list):
    ARCHIVE_FILE.write_text(json.dumps(data, indent=2))

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _gen_id(tasks: list) -> str:
    """Generate a short incremental ID like T001, T002, etc."""
    existing = [t.get("id", "") for t in tasks]
    nums = []
    for eid in existing:
        if eid.startswith("T") and eid[1:].isdigit():
            nums.append(int(eid[1:]))
    next_num = max(nums, default=0) + 1
    return f"T{next_num:03d}"


# ── Commands ──────────────────────────────────────────────

def cmd_status():
    """Show all active work with status indicators."""
    data = _load_tasks()
    active = data.get("active", [])
    completed = data.get("completed", [])

    if not active and not completed:
        print("📭 No tracked work. Queue is empty.")
        return

    if active:
        print("═══ ACTIVE WORK ═══")
        print()
        for task in active:
            status_icon = {
                "queued": "⏳",
                "dispatched": "🚀",
                "running": "⚙️",
                "blocked": "🚫",
                "review": "👀",
            }.get(task.get("status", "queued"), "❓")

            priority_mark = ""
            if task.get("priority") == "high":
                priority_mark = " 🔴"
            elif task.get("priority") == "low":
                priority_mark = " 🔵"

            task_type = task.get("type", "task").upper()
            print(f"  {status_icon} [{task['id']}] {task['title']}{priority_mark}")
            print(f"     Type: {task_type} | Status: {task['status']} | Created: {task.get('created', '?')[:16]}")

            if task.get("agent"):
                print(f"     Agent: {task['agent']}")
            if task.get("notes"):
                for note in task["notes"][-2:]:  # last 2 notes
                    print(f"     📝 {note['time'][:16]}: {note['text']}")
            print()

    # Show recently completed (last 5)
    if completed:
        recent = completed[-5:]
        print(f"═══ RECENTLY COMPLETED ({len(completed)} total) ═══")
        print()
        for task in reversed(recent):
            print(f"  ✅ [{task['id']}] {task['title']}")
            if task.get("result"):
                print(f"     Result: {task['result'][:100]}")
            print()


def cmd_add(title: str, priority: str = "normal", task_type: str = "task"):
    """Add a new task to the active queue."""
    data = _load_tasks()
    all_tasks = data.get("active", []) + data.get("completed", [])
    task_id = _gen_id(all_tasks)

    task = {
        "id": task_id,
        "title": title,
        "type": task_type,
        "priority": priority,
        "status": "queued",
        "created": _now_iso(),
        "updated": _now_iso(),
        "agent": None,
        "session_key": None,
        "notes": [],
        "result": None,
    }

    data.setdefault("active", []).append(task)
    _save_tasks(data)
    print(f"✅ Added [{task_id}] {title} (priority: {priority}, type: {task_type})")
    return task_id


def cmd_update(task_id: str, status: str, note: str = None, agent: str = None, session_key: str = None):
    """Update a task's status and optionally add a note."""
    data = _load_tasks()

    for task in data.get("active", []):
        if task["id"] == task_id:
            task["status"] = status
            task["updated"] = _now_iso()
            if agent:
                task["agent"] = agent
            if session_key:
                task["session_key"] = session_key
            if note:
                task.setdefault("notes", []).append({
                    "time": _now_iso(),
                    "text": note,
                })
            _save_tasks(data)
            print(f"✅ Updated [{task_id}] → {status}")
            return

    print(f"❌ Task {task_id} not found in active tasks")


def cmd_complete(task_id: str, result: str = None):
    """Move a task from active to completed."""
    data = _load_tasks()

    for i, task in enumerate(data.get("active", [])):
        if task["id"] == task_id:
            task["status"] = "complete"
            task["completed_at"] = _now_iso()
            task["updated"] = _now_iso()
            if result:
                task["result"] = result

            data.setdefault("completed", []).append(task)
            data["active"].pop(i)
            _save_tasks(data)
            print(f"✅ Completed [{task_id}] {task['title']}")
            return

    print(f"❌ Task {task_id} not found in active tasks")


def cmd_log(limit: int = 20):
    """Show completed task log."""
    data = _load_tasks()
    completed = data.get("completed", [])

    if not completed:
        print("📭 No completed tasks.")
        return

    print(f"═══ COMPLETED WORK ({len(completed)} total) ═══\n")
    for task in reversed(completed[-limit:]):
        duration = ""
        if task.get("created") and task.get("completed_at"):
            try:
                c = datetime.fromisoformat(task["created"])
                d = datetime.fromisoformat(task["completed_at"])
                mins = (d - c).total_seconds() / 60
                if mins < 60:
                    duration = f" ({mins:.0f}m)"
                else:
                    duration = f" ({mins/60:.1f}h)"
            except:
                pass

        print(f"  ✅ [{task['id']}] {task['title']}{duration}")
        if task.get("result"):
            print(f"     → {task['result'][:120]}")
        print()


def cmd_clean():
    """Archive completed tasks older than 24h."""
    data = _load_tasks()
    completed = data.get("completed", [])
    archive = _load_archive()

    now = time.time()
    keep = []
    archived = 0

    for task in completed:
        try:
            completed_at = datetime.fromisoformat(task.get("completed_at", task.get("updated", "")))
            age_hours = (datetime.now(timezone.utc) - completed_at).total_seconds() / 3600
            if age_hours > 24:
                archive.append(task)
                archived += 1
            else:
                keep.append(task)
        except:
            keep.append(task)

    data["completed"] = keep
    _save_tasks(data)
    _save_archive(archive)
    print(f"📦 Archived {archived} tasks. {len(keep)} recent completed tasks remain.")


def cmd_summary() -> str:
    """Generate a one-line summary for chat headers."""
    data = _load_tasks()
    active = data.get("active", [])

    if not active:
        return ""

    running = [t for t in active if t["status"] in ("running", "dispatched")]
    queued = [t for t in active if t["status"] == "queued"]

    parts = []
    for t in running[:3]:
        icon = "⚙️" if t["status"] == "running" else "🚀"
        parts.append(f"{icon} {t['title'][:30]}")

    if queued:
        parts.append(f"📋 {len(queued)} queued")

    return " | ".join(parts)


# ── CLI ───────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        cmd_status()
        return

    command = args[0]

    if command == "status":
        cmd_status()

    elif command == "add":
        if len(args) < 2:
            print("Usage: dispatch.py add <title> [--priority high|normal|low] [--type project|task|research]")
            return
        title = args[1]
        priority = "normal"
        task_type = "task"
        for i, a in enumerate(args[2:], 2):
            if a == "--priority" and i + 1 < len(args):
                priority = args[i + 1]
            elif a == "--type" and i + 1 < len(args):
                task_type = args[i + 1]
        cmd_add(title, priority, task_type)

    elif command == "update":
        if len(args) < 3:
            print("Usage: dispatch.py update <id> <status> [--note '...'] [--agent '...']")
            return
        task_id = args[1]
        status = args[2]
        note = None
        agent = None
        session_key = None
        for i, a in enumerate(args[3:], 3):
            if a == "--note" and i + 1 < len(args):
                note = args[i + 1]
            elif a == "--agent" and i + 1 < len(args):
                agent = args[i + 1]
            elif a == "--session" and i + 1 < len(args):
                session_key = args[i + 1]
        cmd_update(task_id, status, note, agent, session_key)

    elif command == "complete":
        if len(args) < 2:
            print("Usage: dispatch.py complete <id> [--result '...']")
            return
        task_id = args[1]
        result = None
        for i, a in enumerate(args[2:], 2):
            if a == "--result" and i + 1 < len(args):
                result = args[i + 1]
        cmd_complete(task_id, result)

    elif command == "log":
        limit = int(args[1]) if len(args) > 1 else 20
        cmd_log(limit)

    elif command == "clean":
        cmd_clean()

    elif command == "summary":
        s = cmd_summary()
        if s:
            print(s)

    else:
        print(f"Unknown command: {command}")
        print("Commands: status, add, update, complete, log, clean, summary")


if __name__ == "__main__":
    main()
