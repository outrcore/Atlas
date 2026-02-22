#!/usr/bin/env python3
"""
Recover Chat History - Process exported Telegram conversations
and extract important information into the brain/memory system.

Usage:
    python recover_chat_history.py <chat_export_file>
    
The file should be a text export of Telegram conversations.
This script will:
1. Parse the conversations
2. Extract important facts, decisions, and context
3. Update MEMORY.md and daily memory files
4. Index into the vector database
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime
import anthropic

# Paths
WORKSPACE = Path("/workspace/clawd")
MEMORY_DIR = WORKSPACE / "memory"
MEMORY_FILE = WORKSPACE / "MEMORY.md"
BRAIN_DATA = WORKSPACE / "brain_data"
ACTIVITY_DIR = BRAIN_DATA / "activity"

# Initialize Anthropic
client = anthropic.Anthropic()

def parse_telegram_export(file_path: str) -> list:
    """Parse a Telegram text export into messages."""
    messages = []
    current_msg = None
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Try to parse various formats
    lines = content.split('\n')
    
    for line in lines:
        # Common Telegram export format: [timestamp] Name: message
        # Or: Name, [date time]:\nmessage
        
        if line.strip():
            messages.append(line.strip())
    
    return messages

def extract_insights_with_claude(conversation_text: str) -> dict:
    """Use Claude to extract important information from conversation."""
    
    prompt = f"""Analyze this conversation history between the user and ATLAS (his AI assistant).
Extract the most important information that ATLAS should remember.

<conversation>
{conversation_text[:50000]}  
</conversation>

Return a JSON object with:
{{
    "facts": ["list of important facts learned"],
    "decisions": ["key decisions made"],
    "preferences": ["user preferences discovered"],
    "projects": ["projects discussed with status"],
    "technical_details": ["technical implementations, configs, etc"],
    "action_items": ["any pending tasks or TODOs"],
    "context_summary": "A 2-3 paragraph summary of what was discussed"
}}

Focus on:
- Wander app development details
- Memory/brain system configuration
- Any mockups or design decisions (Options A-E, etc.)
- Infrastructure setup (GitHub Actions, DigitalOcean, Supabase)
- Important user preferences or requests

Be thorough - this is recovering lost context."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse JSON from response
    text = response.content[0].text
    
    # Try to extract JSON
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json.loads(json_match.group())
    
    return {"error": "Could not parse response", "raw": text}

def update_memory_file(insights: dict):
    """Update MEMORY.md with recovered insights."""
    
    recovery_section = f"""

---

## Recovered Context ({datetime.now().strftime('%Y-%m-%d %H:%M')})

### Summary
{insights.get('context_summary', 'No summary available')}

### Key Facts
{chr(10).join('- ' + f for f in insights.get('facts', []))}

### Decisions Made
{chr(10).join('- ' + d for d in insights.get('decisions', []))}

### Technical Details
{chr(10).join('- ' + t for t in insights.get('technical_details', []))}

### Projects Discussed
{chr(10).join('- ' + p for p in insights.get('projects', []))}

### Action Items
{chr(10).join('- [ ] ' + a for a in insights.get('action_items', []))}

---
"""
    
    # Append to MEMORY.md
    with open(MEMORY_FILE, 'a') as f:
        f.write(recovery_section)
    
    print(f"✅ Updated MEMORY.md")

def save_to_daily_log(date_str: str, content: str):
    """Save conversation to daily memory file."""
    daily_file = MEMORY_DIR / f"{date_str}.md"
    
    with open(daily_file, 'a') as f:
        f.write(f"\n\n## Recovered Conversation\n\n{content}\n")
    
    print(f"✅ Updated {daily_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python recover_chat_history.py <chat_export_file>")
        print("\nThis will process the exported chat and extract important context.")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    print(f"📖 Reading {file_path}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"📊 Loaded {len(content)} characters")
    print("🧠 Analyzing with Claude...")
    
    insights = extract_insights_with_claude(content)
    
    if "error" in insights:
        print(f"⚠️ Warning: {insights['error']}")
        print(insights.get('raw', '')[:500])
    else:
        print("✅ Extracted insights:")
        print(f"   - {len(insights.get('facts', []))} facts")
        print(f"   - {len(insights.get('decisions', []))} decisions")
        print(f"   - {len(insights.get('technical_details', []))} technical details")
        print(f"   - {len(insights.get('action_items', []))} action items")
        
        # Update memory
        update_memory_file(insights)
        
        # Save raw insights
        insights_file = BRAIN_DATA / "recovered_insights.json"
        with open(insights_file, 'w') as f:
            json.dump(insights, f, indent=2)
        print(f"✅ Saved raw insights to {insights_file}")
    
    print("\n✅ Recovery complete!")
    print("Run 'python -m brain.daemon --mode once' to process into vector DB")

if __name__ == "__main__":
    main()
