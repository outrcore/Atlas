#!/usr/bin/env python3
"""
ShortyStorys Script Generator
Generates scary story scripts for Matt's YouTube channel @ShortyStorys

Built by ATLAS during first autonomous build session.
2026-02-01
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add Anthropic support
try:
    import anthropic
except ImportError:
    print("Installing anthropic...")
    os.system("pip install anthropic -q")
    import anthropic

STORY_STYLES = {
    "nosleep": """Write in the style of r/nosleep - first person, 
    past tense, the narrator has experienced something 
    terrifying and is sharing their story. Make it feel real 
    and grounded. Build tension slowly. The horror should 
    feel like it could happen to anyone.""",
    
    "cosmic": """Write cosmic horror in the style of Lovecraft - 
    the horror comes from the vast, unknowable, and 
    incomprehensible. Humans are insignificant. Use rich, 
    atmospheric prose. The true horror is what we cannot 
    understand.""",
    
    "psychological": """Write psychological horror - the terror 
    comes from within. Unreliable narrator, paranoia, 
    gaslighting, questioning reality. Is the horror real 
    or in their mind? Leave it ambiguous.""",
    
    "creature": """Classic creature feature - something is 
    hunting the protagonists. Build the creature slowly, 
    hints and glimpses before the reveal. Make the 
    creature memorable and terrifying.""",
    
    "urban_legend": """Write in the style of modern urban legends - 
    something strange that could be happening in any town. 
    The horror comes from the familiar becoming sinister."""
}

SYSTEM_PROMPT = """You are a master horror writer creating scripts for a scary story 
narration YouTube channel called ShortyStorys. Your stories should be:

1. CAPTIVATING - Hook the listener in the first 30 seconds
2. ATMOSPHERIC - Rich sensory details that paint vivid scenes
3. PACED WELL - Build tension, provide relief, then escalate
4. NARRATION-READY - Written to be read aloud (avoid complex visual descriptions)
5. 5-15 MINUTES when read aloud (800-2000 words typically)

Include subtle pauses marked with [PAUSE] for dramatic effect.
Include tone suggestions in brackets like [whispered], [building tension], etc.

The story should have:
- A compelling opening hook
- Rising tension throughout
- A memorable, impactful ending (can be ambiguous, horrifying, or twist)
"""

def generate_story(
    theme: str = None,
    style: str = "nosleep",
    length: str = "medium",
    custom_prompt: str = None,
    api_key: str = None
) -> dict:
    """Generate a scary story script."""
    
    client = anthropic.Anthropic(api_key=api_key or os.environ.get('ANTHROPIC_API_KEY'))
    
    length_guide = {
        "short": "around 800 words (5 minutes when read)",
        "medium": "around 1200 words (8-10 minutes when read)",
        "long": "around 2000 words (12-15 minutes when read)"
    }
    
    style_guide = STORY_STYLES.get(style, STORY_STYLES["nosleep"])
    
    prompt = f"""Generate a scary story for narration.

Style: {style_guide}

Length: {length_guide.get(length, length_guide['medium'])}

{f'Theme/Premise: {theme}' if theme else 'Create an original, compelling premise.'}

{f'Additional instructions: {custom_prompt}' if custom_prompt else ''}

Format your response as:
TITLE: [Compelling, intriguing title]

HOOK: [A brief description of the opening hook for thumbnails/descriptions]

STORY:
[The full story script with [PAUSE] and [tone] markers]

END NOTES:
[Brief notes on narration style, music suggestions, key moments to emphasize]
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.content[0].text
    
    # Parse the response
    result = {
        "generated_at": datetime.now().isoformat(),
        "style": style,
        "length": length,
        "theme": theme,
        "raw_content": content,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    }
    
    # Try to extract sections
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('TITLE:'):
            result['title'] = line.replace('TITLE:', '').strip()
        elif line.startswith('HOOK:'):
            result['hook'] = line.replace('HOOK:', '').strip()
    
    return result

def save_story(story: dict, output_dir: str = None):
    """Save the generated story to a file."""
    output_dir = Path(output_dir or '/workspace/clawd/content/scary_stories')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename from title or timestamp
    title = story.get('title', 'untitled').lower()
    safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in title)
    safe_title = safe_title.replace(' ', '_')[:50]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    filename = f"{timestamp}_{safe_title}"
    
    # Save markdown version
    md_path = output_dir / f"{filename}.md"
    with open(md_path, 'w') as f:
        f.write(f"# {story.get('title', 'Untitled Story')}\n\n")
        f.write(f"**Generated:** {story['generated_at']}\n")
        f.write(f"**Style:** {story['style']}\n")
        f.write(f"**Length:** {story['length']}\n\n")
        if story.get('hook'):
            f.write(f"**Hook:** {story['hook']}\n\n")
        f.write("---\n\n")
        f.write(story['raw_content'])
    
    # Save JSON version for metadata
    json_path = output_dir / f"{filename}.json"
    with open(json_path, 'w') as f:
        json.dump(story, f, indent=2)
    
    return md_path, json_path

def main():
    parser = argparse.ArgumentParser(
        description="🎃 ShortyStorys Script Generator - Create scary stories for YouTube"
    )
    parser.add_argument("--theme", "-t", help="Story theme or premise")
    parser.add_argument("--style", "-s", 
                       choices=list(STORY_STYLES.keys()),
                       default="nosleep",
                       help="Story style")
    parser.add_argument("--length", "-l",
                       choices=["short", "medium", "long"],
                       default="medium",
                       help="Story length")
    parser.add_argument("--prompt", "-p", help="Additional custom instructions")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--no-save", action="store_true", help="Don't save to file")
    
    args = parser.parse_args()
    
    print("🎃 ShortyStorys Script Generator")
    print("=" * 50)
    print(f"Style: {args.style}")
    print(f"Length: {args.length}")
    if args.theme:
        print(f"Theme: {args.theme}")
    print("=" * 50)
    print("\n⏳ Generating story...\n")
    
    try:
        story = generate_story(
            theme=args.theme,
            style=args.style,
            length=args.length,
            custom_prompt=args.prompt
        )
        
        print(f"📖 Title: {story.get('title', 'Untitled')}")
        print(f"🎣 Hook: {story.get('hook', 'N/A')}")
        print(f"📊 Tokens used: {story['usage']['input_tokens'] + story['usage']['output_tokens']}")
        
        if not args.no_save:
            md_path, json_path = save_story(story, args.output)
            print(f"\n✅ Saved to: {md_path}")
        
        print("\n" + "=" * 50)
        print("FULL SCRIPT:")
        print("=" * 50)
        print(story['raw_content'])
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()
