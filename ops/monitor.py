#!/usr/bin/env python3
"""
ATLAS Session Monitor

Checks on running sub-agents and background processes.
Designed to be called from heartbeats or cron jobs.

Usage:
    python ops/monitor.py              # Check all active tasks
    python ops/monitor.py --screens    # Also check screen sessions
    python ops/monitor.py --json       # Output as JSON (for API/dashboard)
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

OPS_DIR = Path(__file__).parent
TASKS_FILE = OPS_DIR / "tasks.json"


def get_screen_sessions() -> dict:
    """Get running screen sessions and their status."""
    sessions = {}
    try:
        r = subprocess.run(["screen", "-ls"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            line = line.strip()
            if "." in line and ("Detached" in line or "Attached" in line):
                # Parse: "831540.quasar-train-scalp (02/18/26 04:31:39) (Detached)"
                parts = line.split(".")
                if len(parts) >= 2:
                    name_part = parts[1].split("\t")[0].split(" ")[0]
                    status = "attached" if "Attached" in line else "detached"
                    sessions[name_part] = {
                        "name": name_part,
                        "status": status,
                        "raw": line,
                    }
    except Exception as e:
        pass
    return sessions


def check_training_progress(log_path: str) -> dict:
    """Parse a training log for current progress."""
    p = Path(log_path)
    if not p.exists():
        return {"exists": False}

    text = p.read_text()
    lines = text.strip().split("\n")

    result = {"exists": True, "epoch": 0, "max_epoch": 30}

    # Parse epoch lines
    epoch_re = re.compile(
        r"Epoch\s+(\d+)/(\d+)\s*│\s*Loss:\s*([\d.]+)\s*│\s*Acc:\s*([\d.]+)\s*│\s*"
        r"Val Loss:\s*([\d.]+)\s*│\s*Val Acc:\s*([\d.]+)"
    )
    for line in lines:
        m = epoch_re.search(line)
        if m:
            result["epoch"] = int(m.group(1))
            result["max_epoch"] = int(m.group(2))
            result["train_loss"] = float(m.group(3))
            result["val_acc"] = float(m.group(6))

    # Check if complete
    result["complete"] = result["epoch"] >= result["max_epoch"]

    # File age
    import time
    result["age_seconds"] = int(time.time() - p.stat().st_mtime)
    result["stale"] = result["age_seconds"] > 300

    return result


def check_backfill_progress() -> dict:
    """Check S3 backfill data status."""
    fills_dir = Path("/workspace/projects/HyperClaude-AMT-Atlas/data/fills_btc")
    l2_dir = Path("/workspace/projects/HyperClaude-AMT-Atlas/data/l2book")

    result = {
        "fills_files": 0,
        "fills_size_mb": 0,
        "l2_files": 0,
        "l2_size_mb": 0,
    }

    if fills_dir.exists():
        files = list(fills_dir.glob("*"))
        result["fills_files"] = len(files)
        result["fills_size_mb"] = round(sum(f.stat().st_size for f in files) / 1e6, 1)

    if l2_dir.exists():
        files = list(l2_dir.glob("*"))
        result["l2_files"] = len(files)
        result["l2_size_mb"] = round(sum(f.stat().st_size for f in files) / 1e6, 1)

    return result


def run_monitor(show_screens: bool = False, as_json: bool = False):
    """Run full monitoring check."""
    screens = get_screen_sessions()
    scalp = check_training_progress("/tmp/quasar_train_scalp.log")
    momentum = check_training_progress("/tmp/quasar_train_momentum.log")
    backfill = check_backfill_progress()

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "screens": screens,
        "training": {
            "scalp": scalp,
            "momentum": momentum,
        },
        "backfill": backfill,
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return report

    # Pretty print
    print(f"═══ ATLAS MONITOR — {datetime.now(timezone.utc).strftime('%H:%M UTC')} ═══\n")

    # Training
    print("📊 TRAINING")
    if scalp["exists"]:
        status = "✅ COMPLETE" if scalp["complete"] else f"⚙️ Epoch {scalp['epoch']}/{scalp['max_epoch']}"
        stale = " ⚠️ STALE" if scalp.get("stale") and not scalp["complete"] else ""
        val_acc = f" (val_acc: {scalp['val_acc']:.1%})" if scalp.get("val_acc") else ""
        print(f"  V2-Scalp:    {status}{val_acc}{stale}")
    else:
        print(f"  V2-Scalp:    ❌ No log file")

    if momentum["exists"]:
        status = "✅ COMPLETE" if momentum["complete"] else f"⚙️ Epoch {momentum['epoch']}/{momentum['max_epoch']}"
        stale = " ⚠️ STALE" if momentum.get("stale") and not momentum["complete"] else ""
        val_acc = f" (val_acc: {momentum['val_acc']:.1%})" if momentum.get("val_acc") else ""
        print(f"  V2-Momentum: {status}{val_acc}{stale}")
    else:
        print(f"  V2-Momentum: ⏳ Not started")
    print()

    # Backfill
    print("📥 S3 BACKFILL")
    print(f"  Fills: {backfill['fills_files']} files ({backfill['fills_size_mb']} MB)")
    print(f"  L2:    {backfill['l2_files']} files ({backfill['l2_size_mb']} MB)")
    bf_screen = "quasar-backfill" in screens
    print(f"  Screen: {'🟢 running' if bf_screen else '🔴 stopped'}")
    print()

    # Screens
    if show_screens:
        print("🖥️  SCREEN SESSIONS")
        for name, info in sorted(screens.items()):
            icon = "🟢" if info["status"] == "detached" else "🔵"
            print(f"  {icon} {name} ({info['status']})")
        print()

    return report


if __name__ == "__main__":
    show_screens = "--screens" in sys.argv
    as_json = "--json" in sys.argv
    run_monitor(show_screens, as_json)
