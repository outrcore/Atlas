#!/usr/bin/env python3
"""
Agent Council Memory Review - Phase 4 Tool
============================================
Uses multi-agent debate to curate memories.

Usage:
    python tools/council_review.py                     # Review last 7 days
    python tools/council_review.py --days 14           # Review last 14 days
    python tools/council_review.py --dry-run           # Preview only
    python tools/council_review.py --verbose           # Show all votes
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/workspace/clawd')

from brain.memory_promotion import MemoryPromoter
from brain.agent_council import AgentCouncil, CouncilDecision


async def council_review(
    days: int = 7,
    dry_run: bool = False,
    verbose: bool = False,
):
    """Run agent council review on recent memories."""
    
    print(f"🏛️ Agent Council Memory Review - Phase 4")
    print(f"=" * 60)
    print(f"Days to review: {days}")
    print(f"Dry run: {dry_run}")
    print()
    
    # Get memory candidates
    promoter = MemoryPromoter()
    log_files = promoter.get_recent_logs(days)
    
    print(f"📁 Found {len(log_files)} log files")
    
    # Parse logs
    all_candidates = []
    for log_file in log_files:
        candidates = promoter.parse_daily_log(log_file)
        all_candidates.extend(candidates)
    
    # Deduplicate
    unique = promoter.deduplicate_candidates(all_candidates)
    
    print(f"📊 Total candidates: {len(all_candidates)}")
    print(f"📊 After deduplication: {len(unique)}")
    
    if not unique:
        print("No candidates to review!")
        return
    
    # Initialize council
    council = AgentCouncil()
    
    print(f"\n🏛️ Council convening with {len(council.agents)} agents...")
    print(f"   Archivist 📚 | Minimalist 🗑️ | Analyst 🔍 | Guardian 🛡️")
    print()
    
    # Deliberate on each candidate
    decisions: list[CouncilDecision] = []
    
    for i, candidate in enumerate(unique):
        if i > 0 and i % 20 == 0:
            print(f"   Progress: {i}/{len(unique)} memories reviewed...")
        
        decision = await council.deliberate(candidate.content)
        decisions.append(decision)
    
    # Tally results
    keep = [d for d in decisions if d.should_keep]
    discard = [d for d in decisions if not d.should_keep]
    
    print(f"\n📊 Council Decisions:")
    print(f"   ✅ Keep: {len(keep)} ({len(keep)/len(decisions)*100:.1f}%)")
    print(f"   ❌ Discard: {len(discard)} ({len(discard)/len(decisions)*100:.1f}%)")
    
    # Category breakdown
    categories = {}
    for d in keep:
        cat = d.category
        categories[cat] = categories.get(cat, 0) + 1
    
    print(f"\n📂 Categories (kept memories):")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {count}")
    
    # Show top decisions
    keep_sorted = sorted(keep, key=lambda d: d.confidence, reverse=True)
    
    print(f"\n🏆 Top memories to keep (by confidence):")
    print("-" * 60)
    for i, d in enumerate(keep_sorted[:10], 1):
        content = d.memory_content[:50].replace('\n', ' ')
        votes = sum(1 for v in d.vote_breakdown.values() if v)
        print(f"{i}. [{d.confidence:.0%}] {d.category}")
        print(f"   {content}...")
        print(f"   Votes: {votes}/4 agents agree")
        if verbose:
            for agent, vote in d.vote_breakdown.items():
                emoji = "✅" if vote else "❌"
                print(f"     {emoji} {agent}")
        print()
    
    if verbose and discard:
        print(f"\n🗑️ Discarded memories (top 5):")
        print("-" * 60)
        for d in discard[:5]:
            content = d.memory_content[:50].replace('\n', ' ')
            print(f"   [{d.confidence:.0%}] {content}...")
    
    # Actually promote if not dry run
    if not dry_run and keep:
        print(f"\n📝 Promoting {len(keep)} memories to MEMORY.md...")
        
        # Format for MEMORY.md
        workspace = Path("/workspace/clawd")
        memory_file = workspace / "MEMORY.md"
        
        content_parts = [
            f"\n\n---\n*Council review: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"{len(keep)} kept, {len(discard)} discarded*\n"
        ]
        
        # Group by category
        by_category = {}
        for d in keep:
            if d.category not in by_category:
                by_category[d.category] = []
            by_category[d.category].append(d)
        
        for cat, items in by_category.items():
            content_parts.append(f"\n### {cat.title()}")
            for item in items[:5]:  # Limit per category
                content = item.memory_content[:200].strip()
                content_parts.append(f"- {content}")
        
        # Append to MEMORY.md
        with open(memory_file, 'a') as f:
            f.write('\n'.join(content_parts))
        
        print(f"✅ Added to MEMORY.md")
    
    elif dry_run:
        print(f"\n🔍 Dry run - no changes made")
    
    print(f"\n✨ Council review complete!")
    
    return {
        "total": len(unique),
        "keep": len(keep),
        "discard": len(discard),
        "categories": categories,
    }


def main():
    parser = argparse.ArgumentParser(description="Agent council memory review")
    parser.add_argument("--days", type=int, default=7, help="Days to review")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all votes")
    
    args = parser.parse_args()
    
    result = asyncio.run(council_review(
        days=args.days,
        dry_run=args.dry_run,
        verbose=args.verbose,
    ))
    
    if result:
        print(f"\n{json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
