#!/usr/bin/env python3
"""
Extract insights from recent session history.

This is what runs during heartbeats to learn from conversations.

Usage:
    python scripts/brain_extract_session.py
    python scripts/brain_extract_session.py --hours 24
"""
import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure API key is available
from brain.utils import ensure_api_key
ensure_api_key()


def get_recent_session_messages(session_dir: Path, hours: int = 24) -> str:
    """Read recent messages from session files."""
    messages = []
    
    # Find session files
    for session_file in session_dir.glob("*.jsonl"):
        try:
            with open(session_file) as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("type") == "message":
                            msg = entry.get("message", {})
                            role = msg.get("role", "unknown")
                            content = msg.get("content", [])
                            
                            # Extract text content
                            text = ""
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    text += c.get("text", "")
                                elif isinstance(c, str):
                                    text += c
                                    
                            if text and role in ["user", "assistant"]:
                                # Check timestamp
                                ts = entry.get("timestamp", "")
                                messages.append({
                                    "role": role,
                                    "content": text[:500],  # Truncate
                                    "timestamp": ts,
                                })
        except Exception as e:
            print(f"Error reading {session_file}: {e}")
            
    # Sort by timestamp and take recent
    messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Format for extraction
    lines = []
    for m in messages[:50]:  # Last 50 messages
        role = "User" if m["role"] == "user" else "ATLAS"
        lines.append(f"[{role}] {m['content']}")
        
    return "\n\n".join(reversed(lines))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true", help="Don't save, just show")
    args = parser.parse_args()
    
    from brain import Brain
    
    print("🧠 Brain Session Extraction")
    print("=" * 40)
    
    # Find session directory
    session_dir = Path("/root/.openclaw/agents/main/sessions")
    if not session_dir.exists():
        print(f"❌ Session dir not found: {session_dir}")
        return
        
    # Get recent messages
    print(f"\n📖 Reading recent messages...")
    conversation = get_recent_session_messages(session_dir, args.hours)
    
    if not conversation:
        print("No recent messages found")
        return
        
    print(f"Found {len(conversation.split(chr(10)))} message lines")
    
    # Initialize brain
    brain = Brain()
    await brain.initialize()
    
    # Extract insights
    print(f"\n🔍 Extracting insights using Claude...")
    insights = await brain.extract_insights(conversation)
    
    if not insights.get("_success"):
        print(f"❌ Extraction failed: {insights.get('_error')}")
        return
        
    # Show results
    print(f"\n✅ Extraction successful!")
    print(f"\n📋 Summary: {insights.get('summary', 'N/A')}")
    
    if insights.get("facts"):
        print(f"\n📚 Facts learned ({len(insights['facts'])}):")
        for fact in insights["facts"]:
            print(f"  - {fact}")
            
    if insights.get("preferences"):
        print(f"\n⭐ Preferences ({len(insights['preferences'])}):")
        for pref in insights["preferences"]:
            print(f"  - {pref}")
            
    if insights.get("decisions"):
        print(f"\n✓ Decisions ({len(insights['decisions'])}):")
        for dec in insights["decisions"]:
            print(f"  - {dec}")
            
    if insights.get("action_items"):
        print(f"\n📝 Action Items ({len(insights['action_items'])}):")
        for item in insights["action_items"]:
            print(f"  - {item}")
            
    if insights.get("topics"):
        print(f"\n🏷️ Topics: {', '.join(insights['topics'])}")
        
    # Save to brain (unless dry run)
    if not args.dry_run:
        print(f"\n💾 Saving to brain...")
        
        for fact in insights.get("facts", []):
            await brain.link_memory(fact, "000-reference", {"type": "fact", "source": "session"})
            
        for pref in insights.get("preferences", []):
            await brain.link_memory(pref, "300-personal", {"type": "preference", "source": "session"})
            
        # Log the extraction
        brain.log_activity(
            "extraction",
            f"Extracted {len(insights.get('facts', []))} facts, {len(insights.get('preferences', []))} preferences",
            {"insights": insights}
        )
        
        print(f"✅ Saved to brain!")
    else:
        print(f"\n(Dry run - not saved)")


if __name__ == "__main__":
    asyncio.run(main())
