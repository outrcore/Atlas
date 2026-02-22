#!/usr/bin/env python3
"""
Sync QUASAR training task states in ops/tasks.json.

Fixes drift between actual runtime and tracked status:
- Marks T003 (V2-Scalp) complete when scalp training finished
- Marks T004 (V2-Momentum) running/complete based on logs + screens

Usage:
  python ops/sync_training_tasks.py
  python ops/sync_training_tasks.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TASKS_FILE = Path("/workspace/clawd/ops/tasks.json")
SCALP_LOG = Path("/tmp/quasar_train_scalp.log")
MOMENTUM_LOG = Path("/tmp/quasar_train_momentum.log")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_training_log(path: Path):
    if not path.exists():
        return {
            "exists": False,
            "complete": False,
            "epoch": 0,
            "max_epoch": 30,
            "val_acc": None,
        }

    text = path.read_text(errors="ignore")
    lines = text.splitlines()

    last_epoch = 0
    max_epoch = 30
    val_acc = None

    epoch_re = re.compile(r"Epoch\s+(\d+)/(\d+).*Val Acc:\s*([\d.]+)")
    for line in lines:
        m = epoch_re.search(line)
        if m:
            last_epoch = int(m.group(1))
            max_epoch = int(m.group(2))
            val_acc = float(m.group(3))

    complete = ("All training complete" in text) or (last_epoch >= max_epoch and max_epoch > 0)

    return {
        "exists": True,
        "complete": complete,
        "epoch": last_epoch,
        "max_epoch": max_epoch,
        "val_acc": val_acc,
    }


def screen_running(name: str) -> bool:
    try:
        out = subprocess.check_output(["screen", "-ls"], text=True, stderr=subprocess.STDOUT)
        return name in out
    except Exception:
        return False


def append_note(task: dict, text: str):
    notes = task.setdefault("notes", [])
    # avoid duplicate back-to-back notes
    if notes and notes[-1].get("text") == text:
        return
    notes.append({"time": now_iso(), "text": text})


def pop_task(active: list, task_id: str):
    for i, t in enumerate(active):
        if t.get("id") == task_id:
            return active.pop(i)
    return None


def find_task(tasks: list, task_id: str):
    for t in tasks:
        if t.get("id") == task_id:
            return t
    return None


def sync_tasks(data: dict):
    changes = []

    active = data.setdefault("active", [])
    completed = data.setdefault("completed", [])

    scalp = parse_training_log(SCALP_LOG)
    momentum = parse_training_log(MOMENTUM_LOG)
    momentum_screen = screen_running("quasar-train-momentum")

    # --- T003: Scalp ---
    t003_active = find_task(active, "T003")
    t003_completed = find_task(completed, "T003")

    if scalp["exists"] and scalp["complete"]:
        if t003_active:
            t003 = pop_task(active, "T003")
            t003["status"] = "complete"
            t003["updated"] = now_iso()
            if not t003.get("completed_at"):
                t003["completed_at"] = now_iso()
            if not t003.get("result"):
                v = f", val acc {scalp['val_acc']:.1%}" if scalp["val_acc"] is not None else ""
                t003["result"] = f"Scalp training finished ({scalp['epoch']}/{scalp['max_epoch']}){v}."
            append_note(t003, f"Auto-sync: scalp complete ({scalp['epoch']}/{scalp['max_epoch']})")
            completed.append(t003)
            changes.append("T003 moved active -> completed")
        elif t003_completed:
            # keep updated note if needed
            note = f"Auto-sync: scalp complete ({scalp['epoch']}/{scalp['max_epoch']})"
            before = len(t003_completed.get("notes", []))
            append_note(t003_completed, note)
            if len(t003_completed.get("notes", [])) != before:
                t003_completed["updated"] = now_iso()
                changes.append("T003 completion note updated")

    # --- T004: Momentum ---
    t004_active = find_task(active, "T004")
    t004_completed = find_task(completed, "T004")

    if t004_active:
        if momentum["exists"] and momentum["complete"]:
            t004 = pop_task(active, "T004")
            t004["status"] = "complete"
            t004["updated"] = now_iso()
            t004["completed_at"] = now_iso()
            v = f", val acc {momentum['val_acc']:.1%}" if momentum["val_acc"] is not None else ""
            t004["result"] = f"Momentum training finished ({momentum['epoch']}/{momentum['max_epoch']}){v}."
            append_note(t004, f"Auto-sync: momentum complete ({momentum['epoch']}/{momentum['max_epoch']})")
            completed.append(t004)
            changes.append("T004 moved active -> completed")
        elif momentum_screen or (momentum["exists"] and momentum["epoch"] > 0):
            prev = t004_active.get("status")
            t004_active["status"] = "running"
            t004_active["updated"] = now_iso()
            epoch_part = f"epoch {momentum['epoch']}/{momentum['max_epoch']}" if momentum["exists"] else "screen running"
            val_part = f", val acc {momentum['val_acc']:.1%}" if momentum.get("val_acc") is not None else ""
            append_note(t004_active, f"Auto-sync: momentum active ({epoch_part}{val_part})")
            if prev != "running":
                changes.append("T004 status -> running")
            else:
                changes.append("T004 progress note updated")

    # If T004 already completed, nothing to do.

    return data, changes, {"scalp": scalp, "momentum": momentum, "momentum_screen": momentum_screen}


def main():
    parser = argparse.ArgumentParser(description="Sync QUASAR training task state")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    if not TASKS_FILE.exists():
        raise SystemExit(f"tasks file missing: {TASKS_FILE}")

    data = json.loads(TASKS_FILE.read_text())
    new_data, changes, state = sync_tasks(data)

    print("Training state:")
    scalp_state = (
        "complete"
        if state["scalp"]["complete"]
        else f"{state['scalp']['epoch']}/{state['scalp']['max_epoch']}"
    )
    momentum_state = (
        "complete"
        if state["momentum"]["complete"]
        else f"{state['momentum']['epoch']}/{state['momentum']['max_epoch']}"
    )
    print(f"  scalp: {scalp_state}")
    print(f"  momentum: {momentum_state} (screen={'on' if state['momentum_screen'] else 'off'})")

    if changes:
        print("Changes:")
        for c in changes:
            print(f"  - {c}")
    else:
        print("Changes: none")

    if not args.dry_run:
        TASKS_FILE.write_text(json.dumps(new_data, indent=2))
        print(f"Saved: {TASKS_FILE}")


if __name__ == "__main__":
    main()
