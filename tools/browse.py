#!/usr/bin/env python3
"""
Web browsing tool using Playwright.
More reliable than web_fetch, gives full page content.

Usage:
    python browse.py "https://example.com"                    # Get page content
    python browse.py "https://example.com" --screenshot out.png  # Screenshot
    python browse.py "https://example.com" --html             # Raw HTML
    python browse.py "https://example.com" --wait 5           # Wait N seconds for JS
"""

import sys
import argparse
from playwright.sync_api import sync_playwright


def fetch_page(url: str, wait_seconds: float = 2, get_html: bool = False, 
               screenshot_path: str = None, timeout_ms: int = 30000) -> dict:
    """
    Fetch a web page using Playwright.
    Returns text content, optionally HTML or screenshot.
    """
    result = {
        "url": url,
        "success": False,
        "content": None,
        "title": None,
        "error": None
    }
    
    try:
        with sync_playwright() as p:
            # Launch headless chromium
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Navigate
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            
            # Wait for JS if needed
            if wait_seconds > 0:
                page.wait_for_timeout(int(wait_seconds * 1000))
            
            result["title"] = page.title()
            result["final_url"] = page.url
            
            # Screenshot if requested
            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                result["screenshot"] = screenshot_path
            
            # Get content
            if get_html:
                result["content"] = page.content()
            else:
                # Get readable text content
                result["content"] = page.inner_text("body")
            
            result["success"] = True
            browser.close()
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch web pages with Playwright")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--html", action="store_true", help="Get raw HTML instead of text")
    parser.add_argument("--screenshot", metavar="PATH", help="Save screenshot to path")
    parser.add_argument("--wait", type=float, default=2, help="Seconds to wait for JS (default: 2)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds (default: 30)")
    parser.add_argument("--max-chars", type=int, default=50000, help="Max characters to output")
    
    args = parser.parse_args()
    
    print(f"Fetching: {args.url}")
    print("-" * 50)
    
    result = fetch_page(
        args.url,
        wait_seconds=args.wait,
        get_html=args.html,
        screenshot_path=args.screenshot,
        timeout_ms=args.timeout * 1000
    )
    
    if not result["success"]:
        print(f"Error: {result['error']}")
        sys.exit(1)
    
    print(f"Title: {result['title']}")
    if result.get("screenshot"):
        print(f"Screenshot: {result['screenshot']}")
    print(f"Final URL: {result['final_url']}")
    print("-" * 50)
    
    content = result["content"]
    if len(content) > args.max_chars:
        content = content[:args.max_chars] + f"\n\n[... truncated at {args.max_chars} chars ...]"
    
    print(content)


if __name__ == "__main__":
    main()
