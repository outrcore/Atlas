#!/usr/bin/env python3
"""
Research tool using Perplexity API.
Usage: python research.py "your question here"

This is more reliable than web_search (which needs Brave API key)
and web_fetch (which can crash).
"""

import sys
import json
import requests
import os

# Load from .env or use directly
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "YOUR_PERPLEXITY_API_KEY")

def research(query: str, detailed: bool = False) -> dict:
    """
    Query Perplexity for research.
    Returns answer with citations.
    """
    url = "https://api.perplexity.ai/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Use sonar for online search, sonar-pro for more detailed
    model = "sonar-pro" if detailed else "sonar"
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful research assistant. Provide accurate, well-sourced information. Be concise but thorough."
            },
            {
                "role": "user", 
                "content": query
            }
        ],
        "search_recency_filter": "month",  # Focus on recent info
        "return_citations": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        result = {
            "answer": data["choices"][0]["message"]["content"],
            "citations": data.get("citations", []),
            "model": data["model"],
            "usage": data.get("usage", {})
        }
        
        return result
        
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    except (KeyError, IndexError) as e:
        return {"error": f"Unexpected response format: {e}"}


def main():
    if len(sys.argv) < 2:
        print("Usage: python research.py 'your question here' [--detailed]")
        print("\nExamples:")
        print("  python research.py 'What is CrewAI framework?'")
        print("  python research.py 'Latest multi-agent AI papers 2025' --detailed")
        sys.exit(1)
    
    query = sys.argv[1]
    detailed = "--detailed" in sys.argv
    
    print(f"Researching: {query}")
    print(f"Model: {'sonar-pro' if detailed else 'sonar'}")
    print("-" * 50)
    
    result = research(query, detailed)
    
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    
    print("\n📝 ANSWER:\n")
    print(result["answer"])
    
    if result["citations"]:
        print("\n📚 CITATIONS:")
        for i, cite in enumerate(result["citations"], 1):
            print(f"  [{i}] {cite}")
    
    print(f"\n💰 Cost: ${result['usage'].get('total_cost', 'N/A')}")


if __name__ == "__main__":
    main()
