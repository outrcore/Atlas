#!/usr/bin/env python3
"""
Backfill Graph - Populate the entity graph from existing memory files.

Run this once to seed the graph with historical data, then let auto-extraction
maintain it going forward.

Usage:
    python backfill_graph.py                    # Process all daily logs
    python backfill_graph.py --days 7           # Last 7 days only
    python backfill_graph.py --file memory/2026-02-06.md  # Specific file
"""

import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.graph import EntityGraph
from brain.graph_extractor import GraphExtractor


async def process_file(extractor: GraphExtractor, filepath: Path) -> dict:
    """Process a single file and return stats."""
    print(f"  Processing: {filepath.name}")
    
    content = filepath.read_text()
    
    # Skip very short files
    if len(content) < 100:
        print(f"    Skipping (too short)")
        return {'nodes': 0, 'edges': 0, 'skipped': True}
    
    try:
        result = await extractor.extract_and_link(
            text=content,
            source=str(filepath)
        )
        
        print(f"    → {len(result.nodes)} nodes, {len(result.edges)} edges")
        return {
            'nodes': len(result.nodes),
            'edges': len(result.edges),
            'facts': len(result.facts),
            'decisions': len(result.decisions),
            'skipped': False
        }
    except Exception as e:
        print(f"    Error: {e}")
        return {'nodes': 0, 'edges': 0, 'error': str(e)}


async def backfill(days: int = None, specific_file: str = None):
    """Run the backfill process."""
    extractor = GraphExtractor()
    memory_dir = Path("/workspace/clawd/memory")
    
    # Get initial stats
    initial_stats = extractor.graph.get_stats()
    print(f"Initial graph: {initial_stats['nodes']} nodes, {initial_stats['edges']} edges")
    print()
    
    files_to_process = []
    
    if specific_file:
        files_to_process = [Path(specific_file)]
    elif days:
        # Get files from last N days
        cutoff = datetime.now() - timedelta(days=days)
        for f in sorted(memory_dir.glob("*.md")):
            # Try to parse date from filename
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                if file_date >= cutoff:
                    files_to_process.append(f)
            except ValueError:
                # Not a date-named file, skip
                pass
    else:
        # All daily log files
        files_to_process = sorted(memory_dir.glob("2026-*.md"))
    
    print(f"Processing {len(files_to_process)} files...")
    print()
    
    total_nodes = 0
    total_edges = 0
    total_facts = 0
    total_decisions = 0
    
    for filepath in files_to_process:
        stats = await process_file(extractor, filepath)
        total_nodes += stats.get('nodes', 0)
        total_edges += stats.get('edges', 0)
        total_facts += stats.get('facts', 0)
        total_decisions += stats.get('decisions', 0)
    
    # Final stats
    final_stats = extractor.graph.get_stats()
    
    print()
    print("=" * 50)
    print("BACKFILL COMPLETE")
    print("=" * 50)
    print(f"Files processed: {len(files_to_process)}")
    print(f"Nodes added: {total_nodes}")
    print(f"Edges added: {total_edges}")
    print(f"Facts extracted: {total_facts}")
    print(f"Decisions captured: {total_decisions}")
    print()
    print(f"Final graph: {final_stats['nodes']} nodes, {final_stats['edges']} edges")
    print(f"Node types: {final_stats['node_types']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill entity graph from memory files")
    parser.add_argument("--days", type=int, help="Only process last N days")
    parser.add_argument("--file", type=str, help="Process specific file")
    args = parser.parse_args()
    
    asyncio.run(backfill(days=args.days, specific_file=args.file))
