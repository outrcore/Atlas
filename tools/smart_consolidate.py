#!/usr/bin/env python3
"""
Smart Memory Consolidation - Phase 2 Tool
==========================================
Uses HybridScorer (LLM + heuristics) for intelligent memory consolidation.

Usage:
    python tools/smart_consolidate.py                    # Default 7 days
    python tools/smart_consolidate.py --days 14          # Last 14 days  
    python tools/smart_consolidate.py --dry-run          # Preview only
    python tools/smart_consolidate.py --verbose          # Show all scoring details
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/workspace/clawd')

from brain.memory_promotion import MemoryPromoter
from brain.llm_scorer import HybridScorer


async def smart_consolidate(
    days: int = 7,
    dry_run: bool = False,
    verbose: bool = False,
    threshold: float = 0.6,
):
    """Run smart consolidation with hybrid scoring."""
    
    workspace = Path("/workspace/clawd")
    memory_dir = workspace / "memory"
    
    print(f"🧠 Smart Memory Consolidation - Phase 2")
    print(f"=" * 50)
    print(f"Days to process: {days}")
    print(f"Threshold: {threshold}")
    print(f"Dry run: {dry_run}")
    print()
    
    # Initialize components
    promoter = MemoryPromoter(promotion_threshold=threshold)
    scorer = HybridScorer(llm_weight=0.7)
    
    # Get recent logs
    log_files = promoter.get_recent_logs(days)
    print(f"📁 Found {len(log_files)} log files")
    
    if not log_files:
        print("No log files found!")
        return
    
    # Parse all logs
    all_candidates = []
    for log_file in log_files:
        candidates = promoter.parse_daily_log(log_file)
        all_candidates.extend(candidates)
        if verbose:
            print(f"  - {log_file.name}: {len(candidates)} candidates")
    
    print(f"\n📊 Total candidates: {len(all_candidates)}")
    
    if not all_candidates:
        print("No candidates found!")
        return
    
    # Deduplicate
    unique_candidates = promoter.deduplicate_candidates(all_candidates)
    print(f"📊 After deduplication: {len(unique_candidates)}")
    
    # Extract content for scoring
    contents = [c.content for c in unique_candidates]
    
    # Run hybrid scoring
    print(f"\n⚡ Running hybrid scoring...")
    results = await scorer.score_with_fallback(contents)
    
    # Combine with original candidates
    scored = []
    for candidate, result in zip(unique_candidates, results):
        scored.append({
            "candidate": candidate,
            "heuristic_score": result["heuristic_score"],
            "final_score": result["final_score"],
            "category": result["category"],
            "should_keep": result["should_keep"],
            "llm_used": result["llm_score"] is not None,
            "llm_summary": result["llm_score"]["summary"] if result["llm_score"] else None,
        })
    
    # Sort by final score
    scored.sort(key=lambda x: x["final_score"], reverse=True)
    
    # Filter to what we're keeping
    to_keep = [s for s in scored if s["should_keep"]]
    to_discard = [s for s in scored if not s["should_keep"]]
    
    print(f"\n✅ Keeping: {len(to_keep)}")
    print(f"❌ Discarding: {len(to_discard)}")
    
    # Show top memories
    print(f"\n🏆 Top memories to promote:")
    print("-" * 50)
    for i, item in enumerate(to_keep[:10]):
        content = item["candidate"].content[:60].replace('\n', ' ')
        llm_tag = "🤖" if item["llm_used"] else "📐"
        print(f"{i+1}. [{item['final_score']:.2f}] {llm_tag} {item['category']}")
        print(f"   {content}...")
        if item["llm_summary"]:
            print(f"   → {item['llm_summary']}")
        print()
    
    if verbose and to_discard:
        print(f"\n🗑️ Discarded memories:")
        print("-" * 50)
        for item in to_discard[:5]:
            content = item["candidate"].content[:60].replace('\n', ' ')
            print(f"[{item['final_score']:.2f}] {content}...")
    
    # Actually promote if not dry run
    if not dry_run and to_keep:
        print(f"\n📝 Promoting {len(to_keep)} memories...")
        
        # Update candidates with new scores and categories
        for item in to_keep:
            item["candidate"].importance = item["final_score"]
            item["candidate"].category = item["category"]
        
        # Format for MEMORY.md
        candidates_to_promote = [item["candidate"] for item in to_keep[:20]]
        memory_content = promoter.format_for_memory_md(candidates_to_promote)
        
        if memory_content:
            memory_file = workspace / "MEMORY.md"
            with open(memory_file, 'a') as f:
                f.write(memory_content)
            print(f"✅ Added {len(candidates_to_promote)} memories to MEMORY.md")
        
        # Add to vector DB
        added = await promoter.add_to_vector_db(candidates_to_promote)
        if added:
            print(f"✅ Added {added} memories to vector DB")
    
    elif dry_run:
        print("\n🔍 Dry run - no changes made")
    
    print("\n✨ Done!")
    
    return {
        "processed": len(all_candidates),
        "unique": len(unique_candidates),
        "keeping": len(to_keep),
        "discarding": len(to_discard),
    }


def main():
    parser = argparse.ArgumentParser(description="Smart memory consolidation with hybrid scoring")
    parser.add_argument("--days", type=int, default=7, help="Days to process (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--threshold", type=float, default=0.6, help="Promotion threshold (default: 0.6)")
    
    args = parser.parse_args()
    
    result = asyncio.run(smart_consolidate(
        days=args.days,
        dry_run=args.dry_run,
        verbose=args.verbose,
        threshold=args.threshold,
    ))
    
    if result:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
