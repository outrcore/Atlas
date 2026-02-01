#!/usr/bin/env python3
"""
ATLAS Research Assistant - Powered by RLM
Uses Recursive Language Models to handle complex research tasks
with near-infinite context windows.

Built by ATLAS during first autonomous build session.
2026-02-01
"""

import os
import sys
import argparse
from pathlib import Path

# Add RLM to path
sys.path.insert(0, '/workspace/projects/rlm')

from rlm import RLM

def create_research_rlm(verbose: bool = True) -> RLM:
    """Create an RLM instance configured for research tasks."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    return RLM(
        backend="anthropic",
        backend_kwargs={
            "api_key": api_key,
            "model_name": "claude-sonnet-4-20250514",
            "max_tokens": 8192,
        },
        verbose=verbose,
        environment="local",
    )

def analyze_document(rlm: RLM, document_path: str, question: str) -> str:
    """Analyze a long document using RLM's recursive capabilities."""
    doc_path = Path(document_path)
    if not doc_path.exists():
        return f"Error: Document not found: {document_path}"
    
    content = doc_path.read_text()
    
    prompt = f"""You have access to a document stored in the variable `document`.

Document content:
```
{content}
```

Question: {question}

Use recursive decomposition if the document is too long to analyze at once.
Break it into sections, analyze each, then synthesize your findings.
"""
    
    response = rlm.completion(prompt)
    return response.response

def research_topic(rlm: RLM, topic: str, depth: str = "standard") -> str:
    """Research a topic using RLM's recursive self-calling."""
    
    depth_instructions = {
        "quick": "Provide a brief overview in 2-3 paragraphs.",
        "standard": "Provide a comprehensive analysis with key points and implications.",
        "deep": "Conduct exhaustive research. Break the topic into subtopics, analyze each deeply, then synthesize. Consider multiple perspectives, historical context, and future implications."
    }
    
    prompt = f"""Research Topic: {topic}

Instructions: {depth_instructions.get(depth, depth_instructions['standard'])}

You can use recursive sub-calls to break down complex aspects.
Synthesize all findings into a coherent response.
"""
    
    response = rlm.completion(prompt)
    return response.response

def compare_items(rlm: RLM, items: list, criteria: str = None) -> str:
    """Compare multiple items using RLM."""
    items_str = "\n".join(f"- {item}" for item in items)
    
    prompt = f"""Compare the following items:
{items_str}

{f'Focus on these criteria: {criteria}' if criteria else 'Provide a comprehensive comparison.'}

Use recursive analysis for each item if needed, then synthesize into a comparison.
"""
    
    response = rlm.completion(prompt)
    return response.response

def main():
    parser = argparse.ArgumentParser(description="ATLAS Research Assistant - Powered by RLM")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Document analysis
    doc_parser = subparsers.add_parser("analyze", help="Analyze a document")
    doc_parser.add_argument("document", help="Path to document")
    doc_parser.add_argument("question", help="Question about the document")
    
    # Topic research
    research_parser = subparsers.add_parser("research", help="Research a topic")
    research_parser.add_argument("topic", help="Topic to research")
    research_parser.add_argument("--depth", choices=["quick", "standard", "deep"], 
                                  default="standard", help="Research depth")
    
    # Comparison
    compare_parser = subparsers.add_parser("compare", help="Compare items")
    compare_parser.add_argument("items", nargs="+", help="Items to compare")
    compare_parser.add_argument("--criteria", help="Comparison criteria")
    
    # Common args
    for p in [doc_parser, research_parser, compare_parser]:
        p.add_argument("--quiet", "-q", action="store_true", help="Suppress verbose output")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("🔬 ATLAS Research Assistant - Powered by RLM")
    print("=" * 50)
    
    try:
        rlm = create_research_rlm(verbose=not getattr(args, 'quiet', False))
        
        if args.command == "analyze":
            result = analyze_document(rlm, args.document, args.question)
        elif args.command == "research":
            result = research_topic(rlm, args.topic, args.depth)
        elif args.command == "compare":
            result = compare_items(rlm, args.items, getattr(args, 'criteria', None))
        
        print("\n" + "=" * 50)
        print("📊 Results:")
        print("=" * 50)
        print(result)
        
        # Show usage stats
        usage = rlm.lm.get_usage_summary()
        print("\n" + "-" * 50)
        print("📈 Usage Summary:")
        for model, stats in usage.model_usage_summaries.items():
            print(f"  {model}: {stats.total_calls} calls, {stats.total_input_tokens + stats.total_output_tokens} tokens")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()
