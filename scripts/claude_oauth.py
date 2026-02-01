#!/usr/bin/env python3
"""
Claude Code OAuth Helper
Automates the OAuth flow with screenshots for manual intervention.
"""

import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OAUTH_URL = "https://claude.ai/oauth/authorize?code=true&client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e&response_type=code&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback&scope=user%3Ainference&code_challenge=j7IdqLs4IFBVhoqgEx7nM-iNgCZl8eoi7LA9_d6rzPk&code_challenge_method=S256&state=oNNzyu54un5rj46VAg9FUBSRB2iHXw98xMVCHMWp2r4"

SCREENSHOT_DIR = Path("/workspace/clawd/oauth_screenshots")

async def main():
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        
        print("🌐 Navigating to OAuth URL...")
        await page.goto(OAUTH_URL, wait_until="networkidle")
        
        screenshot_path = SCREENSHOT_DIR / "01_initial.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"📸 Screenshot saved: {screenshot_path}")
        
        # Check current URL and page content
        print(f"📍 Current URL: {page.url}")
        
        # Get page title
        title = await page.title()
        print(f"📄 Page title: {title}")
        
        # Try to find login form elements
        email_input = await page.query_selector('input[type="email"], input[name="email"]')
        if email_input:
            print("✅ Found email input field")
        
        # Keep browser open for manual interaction info
        print("\n🔍 Page analysis complete. Check the screenshot.")
        print(f"Screenshot at: {screenshot_path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
