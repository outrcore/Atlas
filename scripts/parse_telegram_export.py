#!/usr/bin/env python3
"""Parse Telegram HTML export and extract conversations by date."""

import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def parse_telegram_html(html_path):
    """Parse Telegram HTML export file."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract messages with timestamps
    # Pattern: title="DD.MM.YYYY HH:MM:SS" followed by message content
    messages_by_date = defaultdict(list)
    
    # Find all message blocks
    message_pattern = re.compile(
        r'<div class="message[^"]*"[^>]*id="message(\d+)".*?'
        r'title="(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2}:\d{2})[^"]*".*?'
        r'<div class="from_name">\s*([^<]+)\s*</div>.*?'
        r'<div class="text">\s*(.*?)\s*</div>',
        re.DOTALL
    )
    
    # Simpler approach - find date markers and text
    date_pattern = re.compile(r'title="(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})')
    from_pattern = re.compile(r'<div class="from_name">\s*([^<]+)\s*</div>')
    text_pattern = re.compile(r'<div class="text">\s*(.*?)\s*</div>', re.DOTALL)
    
    # Split by message divs
    message_blocks = re.split(r'<div class="message[^"]*clearfix"', content)
    
    current_date = None
    current_from = None
    
    for block in message_blocks[1:]:  # Skip first empty
        # Find date
        date_match = date_pattern.search(block)
        if date_match:
            day, month, year, time = date_match.groups()
            current_date = f"{year}-{month}-{day}"
        
        # Find sender
        from_match = from_pattern.search(block)
        if from_match:
            current_from = from_match.group(1).strip()
        
        # Find text
        text_match = text_pattern.search(block)
        if text_match and current_date:
            text = text_match.group(1).strip()
            # Clean HTML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if text and len(text) > 5:
                messages_by_date[current_date].append({
                    'from': current_from or 'Unknown',
                    'text': text[:500]  # Truncate long messages
                })
    
    return messages_by_date

def main():
    if len(sys.argv) < 2:
        print("Usage: parse_telegram_export.py <html_file>")
        sys.exit(1)
    
    html_path = sys.argv[1]
    messages = parse_telegram_html(html_path)
    
    print(f"\n=== Parsed {html_path} ===\n")
    for date in sorted(messages.keys()):
        msgs = messages[date]
        print(f"\n📅 {date}: {len(msgs)} messages")
        
        # Show sample of topics discussed
        matt_msgs = [m['text'] for m in msgs if 'User' in m['from']][:5]
        atlas_msgs = [m['text'] for m in msgs if 'Atlas' in m['from']][:5]
        
        if matt_msgs:
            print(f"  User samples:")
            for m in matt_msgs[:3]:
                print(f"    - {m[:100]}...")
        
    return messages

if __name__ == "__main__":
    main()
