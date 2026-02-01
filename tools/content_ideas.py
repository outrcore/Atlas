#!/usr/bin/env python3
"""
ATLAS Content Idea Generator
Generates content ideas for Matt's YouTube channels and other ventures.

Channels:
- @CampbellSoupMatt - AI/tech content
- @ShortyStorys - Scary story narration

Built by ATLAS during autonomous improvement session.
2026-02-01
"""
import os
import sys
import json
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

# Try to import anthropic for AI-powered ideas
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ContentIdeaGenerator:
    """Generate content ideas for Matt's channels."""
    
    # Trending AI topics (update periodically)
    AI_TRENDING_TOPICS = [
        "Claude Code vs Cursor comparison",
        "Building apps with AI in under 30 minutes",
        "AI agents that code for you",
        "Voice cloning with ElevenLabs",
        "Local LLMs that match GPT-4",
        "AI automation for trading",
        "Building your own Jarvis",
        "Claude Opus 4.5 deep dive",
        "RLM (Recursive Language Models) explained",
        "AI tools that will change 2026",
        "Open source AI tools beating paid ones",
        "Building with Anthropic's MCP",
        "The best AI coding assistants ranked",
        "AI for content creators",
        "Automating YouTube with AI",
    ]
    
    # Horror story themes
    HORROR_THEMES = [
        "Cosmic horror / Lovecraftian",
        "Psychological thriller",
        "Found footage style",
        "Creepypasta classics",
        "Urban legends",
        "Body horror",
        "Supernatural / Paranormal",
        "Apocalyptic",
        "Home invasion",
        "Technology gone wrong",
        "Deep web / Internet horror",
        "Ritual / Cult",
        "Nature horror",
        "Historical horror",
        "Medical / Hospital horror",
    ]
    
    # Content formats
    FORMATS = {
        "tech": [
            "Tutorial - Build X in Y minutes",
            "Comparison - X vs Y",
            "Deep dive - Understanding X",
            "Speed run - X challenge",
            "Review - Is X worth it?",
            "Tier list - Best X ranked",
            "Reaction - Trying X for first time",
            "Tips & tricks - X secrets",
        ],
        "horror": [
            "Single long story (15-30 min)",
            "Story compilation (3-5 stories)",
            "Interactive / Choose your fate",
            "Animated / visualized",
            "Real stories from Reddit",
            "Original creepypasta",
            "True crime inspired",
            "Seasonal (Halloween, etc.)",
        ],
    }
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.workspace = Path(workspace)
        self.ideas_dir = self.workspace / "brain_data" / "content_ideas"
        self.ideas_dir.mkdir(parents=True, exist_ok=True)
        
        if ANTHROPIC_AVAILABLE:
            self.client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
        else:
            self.client = None
    
    def generate_tech_ideas(self, count: int = 5, use_ai: bool = True) -> List[Dict]:
        """Generate ideas for @CampbellSoupMatt."""
        ideas = []
        
        if use_ai and self.client:
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": f"""Generate {count} YouTube video ideas for a tech/AI channel.
                        
The channel is @CampbellSoupMatt. Focus areas:
- Claude Code and AI coding tools
- Building things with AI
- AI automation
- Trading tools (Auction Market Theory)
- Tech tutorials

For each idea, provide:
1. Title (catchy, YouTube optimized)
2. Hook (first 5 seconds)
3. Format (tutorial, comparison, etc.)
4. Estimated effort (low/medium/high)
5. Why it would perform well

Output as JSON array."""
                    }]
                )
                
                # Parse JSON from response
                text = response.content[0].text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                ai_ideas = json.loads(text)
                for idea in ai_ideas[:count]:
                    idea["channel"] = "@CampbellSoupMatt"
                    idea["category"] = "tech"
                    idea["generated_at"] = datetime.now().isoformat()
                    ideas.append(idea)
                    
            except Exception as e:
                print(f"AI generation failed: {e}, using fallback")
        
        # Fallback to template-based generation
        if len(ideas) < count:
            for _ in range(count - len(ideas)):
                topic = random.choice(self.AI_TRENDING_TOPICS)
                format_type = random.choice(self.FORMATS["tech"])
                
                ideas.append({
                    "title": f"{format_type.split(' - ')[0]}: {topic}",
                    "topic": topic,
                    "format": format_type,
                    "channel": "@CampbellSoupMatt",
                    "category": "tech",
                    "generated_at": datetime.now().isoformat(),
                    "effort": random.choice(["low", "medium", "high"]),
                })
        
        return ideas[:count]
    
    def generate_horror_ideas(self, count: int = 5, use_ai: bool = True) -> List[Dict]:
        """Generate ideas for @ShortyStorys."""
        ideas = []
        
        if use_ai and self.client:
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": f"""Generate {count} scary story video ideas for a horror narration YouTube channel.

The channel is @ShortyStorys. It features:
- Horror story narrations
- Creepypasta style content
- r/nosleep inspired stories
- Professional narration with ambient audio

For each idea, provide:
1. Title (catchy, horror-themed)
2. Theme/genre (psychological, supernatural, etc.)
3. Synopsis (2-3 sentences)
4. Tone (creepy, terrifying, unsettling, etc.)
5. Target length (short 5-10min, medium 15-20min, long 25-30min)

Output as JSON array."""
                    }]
                )
                
                text = response.content[0].text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                ai_ideas = json.loads(text)
                for idea in ai_ideas[:count]:
                    idea["channel"] = "@ShortyStorys"
                    idea["category"] = "horror"
                    idea["generated_at"] = datetime.now().isoformat()
                    ideas.append(idea)
                    
            except Exception as e:
                print(f"AI generation failed: {e}, using fallback")
        
        # Fallback
        if len(ideas) < count:
            for _ in range(count - len(ideas)):
                theme = random.choice(self.HORROR_THEMES)
                format_type = random.choice(self.FORMATS["horror"])
                
                ideas.append({
                    "title": f"True {theme} Horror Story",
                    "theme": theme,
                    "format": format_type,
                    "channel": "@ShortyStorys",
                    "category": "horror",
                    "generated_at": datetime.now().isoformat(),
                })
        
        return ideas[:count]
    
    def save_ideas(self, ideas: List[Dict], channel: str = "all") -> str:
        """Save ideas to file."""
        filename = f"ideas_{channel}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.ideas_dir / filename
        filepath.write_text(json.dumps(ideas, indent=2))
        return str(filepath)
    
    def get_recent_ideas(self, channel: str = "all", limit: int = 10) -> List[Dict]:
        """Get recently generated ideas."""
        ideas = []
        
        # Find all idea files
        pattern = f"ideas_{channel}_*.json" if channel != "all" else "ideas_*.json"
        files = sorted(self.ideas_dir.glob(pattern), reverse=True)
        
        for file in files[:5]:  # Check last 5 files
            try:
                file_ideas = json.loads(file.read_text())
                ideas.extend(file_ideas)
            except:
                pass
        
        return ideas[:limit]
    
    def format_ideas(self, ideas: List[Dict]) -> str:
        """Format ideas as readable markdown."""
        lines = ["# Content Ideas", ""]
        
        # Group by channel
        by_channel = {}
        for idea in ideas:
            channel = idea.get("channel", "Unknown")
            if channel not in by_channel:
                by_channel[channel] = []
            by_channel[channel].append(idea)
        
        for channel, channel_ideas in by_channel.items():
            lines.append(f"## {channel}")
            lines.append("")
            
            for i, idea in enumerate(channel_ideas, 1):
                title = idea.get("title", "Untitled")
                lines.append(f"### {i}. {title}")
                
                if idea.get("hook"):
                    lines.append(f"**Hook:** {idea['hook']}")
                if idea.get("synopsis"):
                    lines.append(f"**Synopsis:** {idea['synopsis']}")
                if idea.get("format"):
                    lines.append(f"**Format:** {idea['format']}")
                if idea.get("theme"):
                    lines.append(f"**Theme:** {idea['theme']}")
                if idea.get("effort"):
                    lines.append(f"**Effort:** {idea['effort']}")
                if idea.get("target_length"):
                    lines.append(f"**Length:** {idea['target_length']}")
                
                lines.append("")
        
        return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ATLAS Content Idea Generator")
    parser.add_argument("--channel", choices=["tech", "horror", "all"], default="all")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--no-ai", action="store_true", help="Don't use AI generation")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--save", action="store_true", help="Save to file")
    args = parser.parse_args()
    
    generator = ContentIdeaGenerator()
    ideas = []
    
    if args.channel in ["tech", "all"]:
        ideas.extend(generator.generate_tech_ideas(args.count, use_ai=not args.no_ai))
    
    if args.channel in ["horror", "all"]:
        ideas.extend(generator.generate_horror_ideas(args.count, use_ai=not args.no_ai))
    
    if args.save:
        filepath = generator.save_ideas(ideas, args.channel)
        print(f"Saved to: {filepath}")
    
    if args.json:
        print(json.dumps(ideas, indent=2))
    else:
        print(generator.format_ideas(ideas))


if __name__ == "__main__":
    main()
