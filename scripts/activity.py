#!/usr/bin/env python3
"""
Quick activity updater - updates .activity.json for live context sharing
Usage: python activity.py "What I'm doing now"
"""

import sys
import json
from pathlib import Path
from datetime import datetime

ACTIVITY_FILE = Path(__file__).parent.parent / '.activity.json'

def set_activity(activity: str, channel: str = "telegram"):
    """Update the activity file."""
    data = {
        "current": activity,
        "channel": channel,
        "updated": datetime.now().isoformat()
    }
    ACTIVITY_FILE.write_text(json.dumps(data, indent=2))
    print(f"✅ Activity updated: {activity}")

def get_activity():
    """Get current activity."""
    if ACTIVITY_FILE.exists():
        data = json.loads(ACTIVITY_FILE.read_text())
        print(f"Current: {data.get('current')}")
        print(f"Channel: {data.get('channel')}")
        print(f"Updated: {data.get('updated')}")
    else:
        print("No activity file")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        set_activity(" ".join(sys.argv[1:]))
    else:
        get_activity()
