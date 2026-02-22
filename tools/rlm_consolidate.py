#!/usr/bin/env python3
"""
RLM Memory Consolidation - Phase 3 Tool
========================================
Uses Recursive Language Model-style processing for long context consolidation.

Usage:
    python tools/rlm_consolidate.py                    # Consolidate last 7 days
    python tools/rlm_consolidate.py --days 14          # Last 14 days  
    python tools/rlm_consolidate.py --xref             # Cross-reference analysis
    python tools/rlm_consolidate.py --output summary.md # Save to file
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, '/workspace/clawd')

from brain.rlm_processor import MemoryRLM


async def main():
    parser = argparse.ArgumentParser(description="RLM-based memory consolidation")
    parser.add_argument("--days", type=int, default=7, help="Days to process (default: 7)")
    parser.add_argument("--xref", action="store_true", help="Run cross-reference analysis")
    parser.add_argument("--output", "-o", type=str, help="Output file for summary")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    rlm = MemoryRLM()
    
    print(f"🔄 RLM Memory Consolidation - Phase 3")
    print(f"=" * 50)
    
    if args.xref:
        print(f"\n🔗 Cross-reference analysis ({args.days} days)...\n")
        result = await rlm.cross_reference(args.days)
        
        if args.json:
            # Convert sets to lists for JSON
            result['recurring_entities'] = {
                k: list(v) for k, v in result['recurring_entities'].items()
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"📊 Days analyzed: {result['days_analyzed']}")
            print(f"📊 Total entities: {result['entity_count']}")
            print(f"📊 Recurring entities: {result['recurring_count']}")
            
            if result['recurring_entities']:
                print(f"\n🔄 Entities appearing on multiple days:")
                for entity, dates in sorted(
                    result['recurring_entities'].items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )[:15]:
                    print(f"  - {entity}: {', '.join(sorted(dates))}")
    else:
        # Consolidation mode
        rlm.processor.chunk_size = 3000
        
        # Adjust for longer periods
        if args.days > 7:
            rlm.processor.max_chunks_per_level = 6
        
        print(f"\n📅 Consolidating last {args.days} days...\n")
        
        # Get logs manually to set days
        logs = rlm.get_logs(args.days)
        result = await rlm.processor.process_files(logs)
        
        if args.json:
            output = {
                "files_processed": len(logs),
                "original_length": result.original_length,
                "levels_processed": result.levels_processed,
                "processing_time": result.processing_time,
                "final_summary": result.final_summary,
                "key_facts": result.key_facts,
                "entities": result.entities,
                "top_memories": result.top_memories,
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"📊 Results:")
            print(f"  Files processed: {len(logs)}")
            print(f"  Original length: {result.original_length:,} chars")
            print(f"  Levels processed: {result.levels_processed}")
            print(f"  Processing time: {result.processing_time:.2f}s")
            
            print(f"\n📝 Summary:")
            print("-" * 50)
            print(result.final_summary[:2000])
            if len(result.final_summary) > 2000:
                print(f"\n... ({len(result.final_summary) - 2000} more chars)")
            
            print(f"\n🔑 Key Facts ({len(result.key_facts)}):")
            for fact in result.key_facts[:10]:
                print(f"  - {fact[:100]}...")
            
            print(f"\n👤 Entities ({len(result.entities)}):")
            print(f"  {', '.join(result.entities[:20])}")
            
            if result.top_memories:
                print(f"\n🏆 Top Memories:")
                for i, mem in enumerate(result.top_memories[:5], 1):
                    print(f"  {i}. {mem[:100]}...")
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            
            content = f"""# RLM Memory Consolidation
*Generated: {__import__('datetime').datetime.now().isoformat()}*
*Days: {args.days} | Files: {len(logs)} | Chars: {result.original_length:,}*

## Summary

{result.final_summary}

## Key Facts

{chr(10).join('- ' + f for f in result.key_facts)}

## Entities

{', '.join(result.entities)}

## Top Memories

{chr(10).join(f'{i}. {m}' for i, m in enumerate(result.top_memories, 1))}
"""
            output_path.write_text(content)
            print(f"\n✅ Saved to {output_path}")
    
    print("\n✨ Done!")


if __name__ == "__main__":
    asyncio.run(main())
