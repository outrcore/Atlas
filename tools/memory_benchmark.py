#!/usr/bin/env python3
"""
Memory System Benchmark
Compares our proactive recall vs QMD for token efficiency and relevance.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

# Test queries that would benefit from memory
TEST_QUERIES = [
    "What's the BetBots API key?",
    "How do I SSH into the BetBots server?",
    "What are Matt's development rules?",
    "Tell me about the iWander project",
    "What's the Perplexity API key?",
    "What did we work on yesterday?",
    "What's the WWHD framework?",
    "How do I deploy to production?",
    "What are the brain daemon modules?",
    "What's Matt's daily routine?",
]

WORKSPACE = "/workspace/clawd"

def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token average)"""
    return len(text) // 4

def search_memory_md(query: str, memory_path: str) -> list[dict]:
    """Simple keyword search in MEMORY.md"""
    results = []
    
    if not os.path.exists(memory_path):
        return results
    
    with open(memory_path, 'r') as f:
        content = f.read()
    
    # Split into sections
    sections = re.split(r'\n##+ ', content)
    
    # Search for query terms
    query_terms = query.lower().split()
    
    for section in sections:
        score = 0
        section_lower = section.lower()
        for term in query_terms:
            if term in section_lower:
                score += 1
        
        if score > 0:
            # Truncate to 200 chars
            preview = section[:200] + "..." if len(section) > 200 else section
            results.append({
                'content': preview,
                'score': score / len(query_terms),
                'source': 'MEMORY.md'
            })
    
    # Sort by score and return top 5
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:5]


def search_daily_logs(workspace: str, days: int = 2) -> list[dict]:
    """Get recent daily log entries"""
    results = []
    memory_dir = Path(workspace) / "memory"
    
    if not memory_dir.exists():
        return results
    
    from datetime import datetime, timedelta
    
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        log_path = memory_dir / f"{date_str}.md"
        
        if log_path.exists():
            content = log_path.read_text()
            # Get first 500 chars
            preview = content[:500] + "..." if len(content) > 500 else content
            results.append({
                'content': preview,
                'score': 0.5,
                'source': f'memory/{date_str}.md'
            })
    
    return results


def benchmark_our_system(query: str) -> dict:
    """Benchmark our proactive recall system"""
    start = time.time()
    
    memory_path = os.path.join(WORKSPACE, "MEMORY.md")
    
    # Run searches
    keyword_results = search_memory_md(query, memory_path)
    temporal_results = search_daily_logs(WORKSPACE)
    
    # Combine (similar to proactive-recall.ts logic)
    all_results = keyword_results[:3] + temporal_results[:2]
    
    # Build context string
    context_parts = ["[Relevant context from memory:]"]
    for r in all_results:
        content = r['content'][:200] + "..." if len(r['content']) > 200 else r['content']
        context_parts.append(f"- {content} ({r['source']})")
    
    context = "\n".join(context_parts)
    
    elapsed = (time.time() - start) * 1000
    
    return {
        'query': query,
        'results_count': len(all_results),
        'context': context,
        'tokens': estimate_tokens(context),
        'time_ms': elapsed,
        'avg_score': sum(r['score'] for r in all_results) / len(all_results) if all_results else 0
    }


def check_qmd_installed() -> bool:
    """Check if QMD is installed"""
    try:
        result = subprocess.run(['which', 'qmd'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False


def run_benchmark():
    """Run full benchmark"""
    print("=" * 60)
    print("MEMORY SYSTEM BENCHMARK")
    print("=" * 60)
    
    # Check QMD
    qmd_installed = check_qmd_installed()
    print(f"\nQMD installed: {qmd_installed}")
    
    print("\n" + "-" * 60)
    print("OUR SYSTEM (Proactive Recall)")
    print("-" * 60)
    
    total_tokens = 0
    total_time = 0
    total_results = 0
    
    for query in TEST_QUERIES:
        result = benchmark_our_system(query)
        total_tokens += result['tokens']
        total_time += result['time_ms']
        total_results += result['results_count']
        
        print(f"\nQuery: {query}")
        print(f"  Results: {result['results_count']}")
        print(f"  Tokens: ~{result['tokens']}")
        print(f"  Time: {result['time_ms']:.1f}ms")
        print(f"  Avg Score: {result['avg_score']:.2f}")
    
    print("\n" + "=" * 60)
    print("SUMMARY - OUR SYSTEM")
    print("=" * 60)
    print(f"Total queries: {len(TEST_QUERIES)}")
    print(f"Average tokens per query: {total_tokens / len(TEST_QUERIES):.0f}")
    print(f"Average time: {total_time / len(TEST_QUERIES):.1f}ms")
    print(f"Average results: {total_results / len(TEST_QUERIES):.1f}")
    
    # Show a sample context
    print("\n" + "-" * 60)
    print("SAMPLE CONTEXT (first query)")
    print("-" * 60)
    sample = benchmark_our_system(TEST_QUERIES[0])
    print(sample['context'][:1000])
    
    if not qmd_installed:
        print("\n" + "=" * 60)
        print("QMD NOT INSTALLED - Install to compare:")
        print("  bun install -g github.com/tobi/qmd")
        print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
