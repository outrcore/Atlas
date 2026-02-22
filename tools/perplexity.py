#!/usr/bin/env python3
"""
Perplexity AI Research Tool for ATLAS
=====================================
Deep research with web citations via Perplexity API.

Usage:
    python perplexity.py "your research question"
    python perplexity.py "question" --model sonar-pro
    python perplexity.py "question" --focus web|academic|news
    
Models:
    sonar          - Fast, cheap ($0.005/req) - default
    sonar-pro      - Better reasoning ($0.01/req)
    sonar-reasoning - Chain of thought, best for complex questions
"""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# API Configuration
API_KEY = os.environ.get('PERPLEXITY_API_KEY', 'YOUR_PERPLEXITY_API_KEY')
API_URL = "https://api.perplexity.ai/chat/completions"

def research(
    query: str,
    model: str = "sonar",
    system_prompt: str = None,
    focus: str = None,
    return_citations: bool = True,
    return_images: bool = False,
    max_tokens: int = 1024,
) -> dict:
    """
    Query Perplexity API for research with web citations.
    
    Args:
        query: The research question
        model: sonar, sonar-pro, or sonar-reasoning
        system_prompt: Optional system instructions
        focus: Optional search focus (web, academic, news, youtube, reddit)
        return_citations: Include source citations
        return_images: Include related images
        max_tokens: Max response length
        
    Returns:
        dict with 'answer', 'citations', 'usage', 'model'
    """
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": query})
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "return_citations": return_citations,
        "return_images": return_images,
    }
    
    # Add search domain focus if specified
    if focus:
        payload["search_domain_filter"] = [focus]
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    
    req = Request(API_URL, data=json.dumps(payload).encode(), headers=headers, method='POST')
    
    try:
        with urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode())
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return {"error": f"HTTP {e.code}: {error_body}"}
    except URLError as e:
        return {"error": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}
    
    # Extract results
    result = {
        "answer": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
        "citations": data.get("citations", []),
        "images": data.get("images", []),
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }
    
    return result


def format_output(result: dict, verbose: bool = False) -> str:
    """Format research result for display."""
    
    if "error" in result:
        return f"❌ Error: {result['error']}"
    
    output = []
    output.append(result["answer"])
    
    if result.get("citations"):
        output.append("\n📚 Sources:")
        for i, url in enumerate(result["citations"][:10], 1):
            output.append(f"  [{i}] {url}")
    
    if verbose and result.get("usage"):
        usage = result["usage"]
        cost = usage.get("cost", {}).get("total_cost", 0)
        output.append(f"\n💰 Cost: ${cost:.4f} | Tokens: {usage.get('total_tokens', 'N/A')}")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Perplexity AI Research Tool")
    parser.add_argument("query", help="Research question")
    parser.add_argument("--model", "-m", default="sonar", 
                       choices=["sonar", "sonar-pro", "sonar-reasoning"],
                       help="Model to use")
    parser.add_argument("--focus", "-f", 
                       choices=["web", "academic", "news", "youtube", "reddit"],
                       help="Search focus domain")
    parser.add_argument("--system", "-s", help="System prompt")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show usage/cost")
    parser.add_argument("--max-tokens", "-t", type=int, default=1024, help="Max response tokens")
    
    args = parser.parse_args()
    
    result = research(
        query=args.query,
        model=args.model,
        system_prompt=args.system,
        focus=args.focus,
        max_tokens=args.max_tokens,
    )
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_output(result, verbose=args.verbose))


if __name__ == "__main__":
    main()
