#!/usr/bin/env python3
"""
ATLAS Session Start — Quick context loader.

Run at the start of each session to get instant awareness of:
- Active tasks and their status
- Running sub-agents
- Training/backfill progress
- What happened since last session

Usage:
    python ops/session_start.py
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

OPS_DIR = Path(__file__).parent
WORKSPACE = Path("/workspace/clawd")


def get_active_tasks() -> list:
    tasks_file = OPS_DIR / "tasks.json"
    if tasks_file.exists():
        data = json.loads(tasks_file.read_text())
        return data.get("active", [])
    return []


def get_recent_completed(hours: int = 12) -> list:
    tasks_file = OPS_DIR / "tasks.json"
    if tasks_file.exists():
        data = json.loads(tasks_file.read_text())
        completed = data.get("completed", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent = []
        for t in completed:
            try:
                ts = datetime.fromisoformat(t.get("completed_at", ""))
                if ts > cutoff:
                    recent.append(t)
            except:
                pass
        return recent
    return []


def get_screens() -> dict:
    sessions = {}
    try:
        r = subprocess.run(["screen", "-ls"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            for name in ["quasar-train", "quasar-backfill", "quasar-recorder",
                        "brain-daemon", "atlas-desktop-api", "tunnel"]:
                if name in line:
                    sessions[name.split("-")[0] if "-" not in name else line.split(".")[1].split("\t")[0].split(" ")[0]] = True
    except:
        pass
    return sessions


def check_training_log(path: str) -> str:
    """Quick one-liner about training state."""
    import re
    p = Path(path)
    if not p.exists():
        return "not started"

    text = p.read_text()
    epoch_re = re.compile(r"Epoch\s+(\d+)/(\d+).*Val Acc:\s*([\d.]+)")
    last = None
    for line in text.split("\n"):
        m = epoch_re.search(line)
        if m:
            last = (int(m.group(1)), int(m.group(2)), float(m.group(3)))

    if last:
        epoch, max_ep, val_acc = last
        if epoch >= max_ep:
            return f"COMPLETE — {max_ep} epochs, best val_acc: {val_acc:.1%}"
        return f"epoch {epoch}/{max_ep}, val_acc: {val_acc:.1%}"
    return "log exists but no epochs parsed"


def get_recent_memory_entries(hours: int = 12) -> list:
    """Get recent entries from today's memory log."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    entries = []
    for date in [today, yesterday]:
        log = WORKSPACE / "memory" / f"{date}.md"
        if log.exists():
            text = log.read_text()
            # Count sections
            sections = [l for l in text.split("\n") if l.startswith("### ")]
            entries.append(f"{date}: {len(sections)} sections")
    return entries


def main():
    now = datetime.now(timezone.utc)
    print(f"═══ ATLAS SESSION START — {now.strftime('%Y-%m-%d %H:%M UTC')} ═══\n")

    # Active work
    tasks = get_active_tasks()
    if tasks:
        print("🎯 ACTIVE WORK")
        for t in tasks:
            icon = {"queued": "⏳", "dispatched": "🚀", "running": "⚙️", "blocked": "🚫", "review": "👀"}.get(t["status"], "❓")
            priority = " 🔴" if t.get("priority") == "high" else ""
            print(f"  {icon} [{t['id']}] {t['title']}{priority} — {t['status']}")
        print()

    # Recently completed
    recent = get_recent_completed(12)
    if recent:
        print(f"✅ COMPLETED (last 12h): {len(recent)} tasks")
        for t in recent[-3:]:
            result = f" → {t['result'][:60]}" if t.get("result") else ""
            print(f"  [{t['id']}] {t['title']}{result}")
        print()

    # Training
    print("📊 TRAINING STATUS")
    scalp = check_training_log("/tmp/quasar_train_scalp.log")
    momentum = check_training_log("/tmp/quasar_train_momentum.log")
    print(f"  V2-Scalp:    {scalp}")
    print(f"  V2-Momentum: {momentum}")
    print()

    # Backfill
    fills_dir = Path("/workspace/projects/HyperClaude-AMT-Atlas/data/fills_btc")
    if fills_dir.exists():
        n_files = len(list(fills_dir.glob("*")))
        total_mb = sum(f.stat().st_size for f in fills_dir.glob("*")) / 1e6
        print(f"📥 S3 BACKFILL: {n_files} fill files ({total_mb:.0f} MB)")
    print()

    # Memory
    logs = get_recent_memory_entries()
    if logs:
        print("📝 MEMORY LOGS")
        for l in logs:
            print(f"  {l}")
        print()

    print("Ready. Use `python ops/dispatch.py status` for full task details.")


if __name__ == "__main__":
    main()
