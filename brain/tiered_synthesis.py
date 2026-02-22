#!/usr/bin/env python3
"""
Tiered Memory Synthesis
========================
Multi-level memory synthesis at different time intervals:
- Daily: Fresh consolidation of yesterday
- Weekly: Pattern detection across the week
- Monthly: Project/goal progress tracking

Each level looks for different things and produces different insights.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path


class TieredSynthesis:
    """
    Multi-level memory synthesis system.
    
    Daily (4 AM):
    - What happened yesterday that matters?
    - Fresh facts, decisions, lessons
    - Immediate consolidation
    
    Weekly (Sunday 4 AM):
    - What patterns emerged this week?
    - Recurring themes, evolving projects
    - Cross-day connections
    
    Monthly (1st of month, 4 AM):
    - How did projects progress?
    - Goal tracking
    - Major milestones
    """
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.workspace = Path(workspace)
        self.memory_dir = self.workspace / "memory"
        self.memory_file = self.workspace / "MEMORY.md"
    
    def get_logs_for_period(
        self, 
        days: int,
        end_date: Optional[datetime] = None
    ) -> List[Path]:
        """Get log files for a period."""
        if end_date is None:
            end_date = datetime.now()
        
        logs = []
        for i in range(days):
            date = end_date - timedelta(days=i)
            filename = f"{date.strftime('%Y-%m-%d')}.md"
            path = self.memory_dir / filename
            if path.exists():
                logs.append(path)
        
        return logs
    
    def read_logs(self, logs: List[Path]) -> str:
        """Read and combine log files."""
        content = ""
        for log in logs:
            content += f"\n\n=== {log.stem} ===\n"
            content += log.read_text()
        return content
    
    async def daily_synthesis(self) -> Dict[str, Any]:
        """
        Daily synthesis - what happened yesterday?
        
        Focus:
        - New facts and decisions
        - Lessons learned
        - Completed tasks
        - New information about Matt/projects
        """
        logs = self.get_logs_for_period(1)  # Yesterday only
        
        if not logs:
            return {"status": "no_logs", "insights": []}
        
        content = self.read_logs(logs)
        
        # Extract key patterns for daily
        insights = []
        
        # Look for completions
        if 'complete' in content.lower() or '✅' in content:
            insights.append("Completed tasks found")
        
        # Look for lessons
        if 'lesson' in content.lower() or 'learned' in content.lower():
            insights.append("Lessons learned recorded")
        
        # Look for decisions
        if 'decided' in content.lower() or 'decision' in content.lower():
            insights.append("Decisions made")
        
        return {
            "status": "success",
            "period": "daily",
            "logs_processed": len(logs),
            "insights": insights,
            "content_length": len(content),
        }
    
    async def weekly_synthesis(self) -> Dict[str, Any]:
        """
        Weekly synthesis - what patterns emerged?
        
        Focus:
        - Recurring themes (mentioned 3+ days)
        - Project evolution across the week
        - Repeated tasks or concerns
        - Cross-day connections
        """
        logs = self.get_logs_for_period(7)
        
        if len(logs) < 3:
            return {"status": "insufficient_logs", "insights": []}
        
        # Track mentions across days
        daily_mentions: Dict[str, set] = {}
        
        for log in logs:
            date = log.stem
            content = log.read_text().lower()
            daily_mentions[date] = set()
            
            # Track key topics
            topics = ['brain', 'memory', 'wander', 'voice', 'discord', 
                     'claude', 'api', 'matt', 'project', 'build']
            
            for topic in topics:
                if topic in content:
                    daily_mentions[date].add(topic)
        
        # Find recurring themes (appeared 3+ days)
        all_topics = {}
        for date, topics in daily_mentions.items():
            for topic in topics:
                all_topics[topic] = all_topics.get(topic, 0) + 1
        
        recurring = [t for t, count in all_topics.items() if count >= 3]
        
        return {
            "status": "success",
            "period": "weekly",
            "logs_processed": len(logs),
            "recurring_themes": recurring,
            "days_analyzed": len(daily_mentions),
        }
    
    async def monthly_synthesis(self) -> Dict[str, Any]:
        """
        Monthly synthesis - how did projects progress?
        
        Focus:
        - Project milestones
        - Goal tracking
        - Major achievements
        - Long-term patterns
        """
        logs = self.get_logs_for_period(30)
        
        if len(logs) < 7:
            return {"status": "insufficient_logs", "insights": []}
        
        content = self.read_logs(logs)
        
        # Track project mentions
        projects = {
            'brain': {'mentions': 0, 'completions': 0},
            'wander': {'mentions': 0, 'completions': 0},
            'voice': {'mentions': 0, 'completions': 0},
            'atlas': {'mentions': 0, 'completions': 0},
        }
        
        content_lower = content.lower()
        
        for project in projects:
            projects[project]['mentions'] = content_lower.count(project)
            # Look for completions near project mentions
            if f'{project}' in content_lower and 'complete' in content_lower:
                projects[project]['completions'] += 1
        
        # Find most active projects
        active = sorted(
            projects.items(), 
            key=lambda x: x[1]['mentions'], 
            reverse=True
        )[:3]
        
        return {
            "status": "success",
            "period": "monthly",
            "logs_processed": len(logs),
            "active_projects": [p[0] for p in active],
            "project_stats": projects,
        }
    
    async def run_synthesis(self, level: str = "daily") -> Dict[str, Any]:
        """Run synthesis at specified level."""
        if level == "daily":
            return await self.daily_synthesis()
        elif level == "weekly":
            return await self.weekly_synthesis()
        elif level == "monthly":
            return await self.monthly_synthesis()
        else:
            return {"status": "error", "message": f"Unknown level: {level}"}
    
    def get_synthesis_prompt(self, level: str, content: str) -> str:
        """Get Claude prompt for synthesis at given level."""
        
        prompts = {
            "daily": f"""Analyze yesterday's activity log and extract:
1. Key facts learned (new information)
2. Decisions made
3. Lessons learned
4. Completed tasks
5. Action items for today

Focus on NEW information not already in long-term memory.
Be concise - bullet points only.

<logs>
{content[:8000]}
</logs>""",

            "weekly": f"""Analyze this week's activity logs and identify:
1. Recurring themes (topics that came up multiple days)
2. Project evolution (how did projects progress?)
3. Patterns in Matt's requests or interests
4. Cross-day connections (things mentioned separately that relate)
5. Emerging priorities

Look for the BIG PICTURE, not individual facts.

<logs>
{content[:12000]}
</logs>""",

            "monthly": f"""Analyze this month's activity logs for:
1. Major milestones achieved
2. Project progress (start → current state)
3. Goal tracking (what was accomplished toward stated goals)
4. Lessons that should be permanent knowledge
5. Patterns in how we work together

This is for LONG-TERM memory - only the most important insights.

<logs>
{content[:15000]}
</logs>""",
        }
        
        return prompts.get(level, prompts["daily"])


async def test_tiered_synthesis():
    """Test the tiered synthesis system."""
    synth = TieredSynthesis()
    
    print("Testing tiered synthesis...\n")
    
    for level in ["daily", "weekly", "monthly"]:
        print(f"\n{'='*50}")
        print(f"Level: {level.upper()}")
        print('='*50)
        
        result = await synth.run_synthesis(level)
        
        print(f"Status: {result['status']}")
        print(f"Logs processed: {result.get('logs_processed', 0)}")
        
        if level == "weekly" and result.get('recurring_themes'):
            print(f"Recurring themes: {', '.join(result['recurring_themes'])}")
        
        if level == "monthly" and result.get('active_projects'):
            print(f"Active projects: {', '.join(result['active_projects'])}")


if __name__ == "__main__":
    asyncio.run(test_tiered_synthesis())
