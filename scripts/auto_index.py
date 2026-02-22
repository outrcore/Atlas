#!/usr/bin/env python3
"""
Auto-indexer that only re-indexes when files have changed.
Tracks last index time and compares against file mtimes.
"""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/workspace/clawd")
STATE_FILE = WORKSPACE / ".index_state.json"
WATCH_DIRS = ["knowledge", "memory", "research"]

def get_latest_mtime() -> float:
    """Get the most recent modification time across watched directories."""
    latest = 0
    for dir_name in WATCH_DIRS:
        dir_path = WORKSPACE / dir_name
        if not dir_path.exists():
            continue
        for f in dir_path.rglob("*.md"):
            mtime = f.stat().st_mtime
            if mtime > latest:
                latest = mtime
    return latest

def load_state() -> dict:
    """Load last index state."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_index": 0, "chunk_count": 0}

def save_state(state: dict):
    """Save index state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))

def main():
    state = load_state()
    latest_mtime = get_latest_mtime()
    
    if latest_mtime <= state["last_index"]:
        print(f"✓ Knowledge index up to date ({state['chunk_count']} chunks)")
        return
    
    # Files changed, re-index
    print("📚 Files changed, re-indexing...")
    try:
        result = subprocess.run(
            ["python", "scripts/index_knowledge.py"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=120
        )
    except subprocess.TimeoutExpired:
        print("⏱️ Index skipped (timed out after 120s); will retry on next cycle")
        return

    if result.returncode == 0:
        # Parse chunk count from output
        for line in result.stdout.split("\n"):
            if "total chunks" in line:
                try:
                    count = int(line.split()[1])
                    state["chunk_count"] = count
                except:
                    pass
        
        state["last_index"] = datetime.now().timestamp()
        save_state(state)
        print(f"✅ Re-indexed {state.get('chunk_count', '?')} chunks")
    else:
        print(f"❌ Index failed: {result.stderr}")

if __name__ == "__main__":
    main()
