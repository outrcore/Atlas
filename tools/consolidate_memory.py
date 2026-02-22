#!/usr/bin/env python3
"""
Manual Memory Consolidation Tool

Runs the memory promotion pipeline on demand.
Use this to manually consolidate memories outside of the brain daemon cycle.

Usage:
    python tools/consolidate_memory.py              # Default 7 days
    python tools/consolidate_memory.py --days 14    # Last 14 days
    python tools/consolidate_memory.py --dry-run    # Show what would be promoted
"""

import sys
import asyncio
import argparse
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.memory_promotion import MemoryPromoter


async def main():
    parser = argparse.ArgumentParser(description="Consolidate ATLAS memories")
    parser.add_argument("--days", type=int, default=7, help="Days of logs to process")
    parser.add_argument("--dry-run", action="store_true", help="Show candidates without promoting")
    parser.add_argument("--threshold", type=float, default=0.6, help="Promotion threshold (0-1)")
    args = parser.parse_args()
    
    promoter = MemoryPromoter(
        promotion_threshold=args.threshold,
    )
    
    if args.dry_run:
        print(f"🧠 Dry run - analyzing last {args.days} days of logs...\n")
        
        logs = promoter.get_recent_logs(args.days)
        print(f"Found {len(logs)} log files:")
        for log in logs:
            print(f"  - {log.name}")
        
        all_candidates = []
        for log in logs:
            candidates = promoter.parse_daily_log(log)
            all_candidates.extend(candidates)
        
        print(f"\nExtracted {len(all_candidates)} raw candidates")
        
        unique = promoter.deduplicate_candidates(all_candidates)
        print(f"After deduplication: {len(unique)} candidates")
        
        promoted = promoter.select_for_promotion(unique)
        print(f"Would promote: {len(promoted)} candidates (threshold {args.threshold})\n")
        
        print("Top 10 candidates:")
        for i, c in enumerate(promoted[:10], 1):
            print(f"\n{i}. [{c.category}] score={c.promotion_score:.3f}")
            print(f"   importance={c.importance:.2f} emotion={c.emotion_weight:.2f} "
                  f"recency={c.recency_weight:.2f} freq={c.frequency}")
            content = c.content[:100].replace('\n', ' ')
            print(f"   {content}...")
            
    else:
        print(f"🧠 Running memory consolidation for last {args.days} days...\n")
        result = await promoter.run_consolidation(days=args.days)
        
        print(f"\n{'='*50}")
        print(f"📊 Consolidation Results")
        print(f"{'='*50}")
        print(f"Files processed:      {result.files_processed}")
        print(f"Candidates found:     {result.candidates_found}")
        print(f"Promoted to MEMORY:   {result.promoted_to_memory}")
        print(f"Promoted to Vector:   {result.promoted_to_vector}")
        
        if result.errors:
            print(f"\n⚠️ Errors:")
            for err in result.errors:
                print(f"  - {err}")


if __name__ == "__main__":
    asyncio.run(main())
