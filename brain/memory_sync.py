#!/usr/bin/env python3
"""
Memory Sync - Syncs brain insights to MEMORY.md and daily notes.

This module handles the bidirectional sync between:
- Brain's structured memory (LanceDB)
- MEMORY.md (long-term curated knowledge)
- Daily notes (memory/YYYY-MM-DD.md)
"""
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any


class MemorySync:
    """
    Syncs brain knowledge to human-readable memory files.
    """
    
    def __init__(
        self,
        workspace: str = "/workspace/clawd",
    ):
        self.workspace = Path(workspace)
        self.memory_file = self.workspace / "MEMORY.md"
        self.daily_dir = self.workspace / "memory"
        
    def get_today_file(self) -> Path:
        """Get today's daily memory file path."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.daily_dir / f"{today}.md"
        
    def append_to_daily(
        self,
        content: str,
        section: Optional[str] = None,
    ):
        """
        Append content to today's daily memory file.
        
        Args:
            content: Content to append
            section: Optional section header (e.g., "## Auto-Extracted")
        """
        daily_file = self.get_today_file()
        
        # Ensure directory exists
        daily_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(daily_file, "a") as f:
            if section:
                f.write(f"\n\n{section}\n")
            f.write(content + "\n")
            
    def append_facts_to_memory(
        self,
        facts: List[str],
        source: str = "auto-extracted",
    ):
        """
        Append new facts to MEMORY.md under the appropriate section.
        
        Args:
            facts: List of facts to add
            source: Source of the facts
        """
        if not facts:
            return
            
        # Read current memory file
        if self.memory_file.exists():
            content = self.memory_file.read_text()
        else:
            content = "# MEMORY.md - Long-Term Memory\n\n"
            
        # Find or create "## Auto-Extracted Facts" section
        section_header = "## Auto-Extracted Facts"
        
        if section_header not in content:
            content += f"\n\n{section_header}\n\n"
            
        # Format new facts
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_facts = f"\n### Added {timestamp} ({source})\n"
        for fact in facts:
            new_facts += f"- {fact}\n"
            
        # Insert after section header
        insert_pos = content.find(section_header) + len(section_header)
        # Find end of line
        insert_pos = content.find("\n", insert_pos) + 1
        
        content = content[:insert_pos] + new_facts + content[insert_pos:]
        
        # Write back
        self.memory_file.write_text(content)
        
    def append_preferences_to_memory(
        self,
        preferences: List[str],
    ):
        """
        Append new preferences to the Preferences section of MEMORY.md.
        
        Args:
            preferences: List of preferences to add
        """
        if not preferences:
            return
            
        if self.memory_file.exists():
            content = self.memory_file.read_text()
        else:
            content = "# MEMORY.md - Long-Term Memory\n\n"
            
        # Find "## Preferences & Patterns" section
        section_header = "## Preferences & Patterns"
        
        if section_header not in content:
            # Create section before "## Lessons Learned" if it exists
            if "## Lessons Learned" in content:
                pos = content.find("## Lessons Learned")
                content = content[:pos] + f"{section_header}\n\n" + content[pos:]
            else:
                content += f"\n\n{section_header}\n\n"
                
        # Format new preferences
        timestamp = datetime.now().strftime("%Y-%m-%d")
        new_prefs = f"\n### Learned {timestamp}\n"
        for pref in preferences:
            new_prefs += f"- {pref}\n"
            
        # Insert after section header
        insert_pos = content.find(section_header) + len(section_header)
        insert_pos = content.find("\n", insert_pos) + 1
        
        content = content[:insert_pos] + new_prefs + content[insert_pos:]
        
        self.memory_file.write_text(content)
        
    def log_action_items(self, items: List[str]):
        """
        Log action items to today's daily memory.
        
        Args:
            items: List of action items
        """
        if not items:
            return
            
        content = "### Action Items (auto-extracted)\n"
        for item in items:
            content += f"- [ ] {item}\n"
            
        self.append_to_daily(content)
        
    def log_session_summary(
        self,
        summary: str,
        topics: List[str],
        decisions: List[str],
    ):
        """
        Log a session summary to daily memory.
        
        Args:
            summary: One-line summary
            topics: Topics discussed
            decisions: Decisions made
        """
        content = f"### Session Summary\n"
        content += f"_{summary}_\n\n"
        
        if topics:
            content += f"**Topics:** {', '.join(topics)}\n"
            
        if decisions:
            content += f"\n**Decisions:**\n"
            for d in decisions:
                content += f"- {d}\n"
                
        self.append_to_daily(content)
        
    def get_recent_learnings(self, days: int = 7) -> Dict[str, List[str]]:
        """
        Get recently extracted learnings from daily files.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dict with facts, preferences, action_items
        """
        from datetime import timedelta
        
        learnings = {
            "facts": [],
            "preferences": [],
            "action_items": [],
        }
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            file_path = self.daily_dir / f"{date.strftime('%Y-%m-%d')}.md"
            
            if file_path.exists():
                content = file_path.read_text()
                
                # Extract action items (uncompleted)
                for match in re.finditer(r"^- \[ \] (.+)$", content, re.MULTILINE):
                    learnings["action_items"].append(match.group(1))
                    
        return learnings


def sync_brain_to_memory(brain, memory_sync: Optional[MemorySync] = None):
    """
    Sync brain insights to memory files.
    
    Call this periodically to keep MEMORY.md and daily notes updated.
    """
    if memory_sync is None:
        memory_sync = MemorySync()
        
    # This would be called after brain.run_maintenance()
    # For now, it's a placeholder for the integration
    pass
