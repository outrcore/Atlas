#!/usr/bin/env python3
"""
Automated OAuth flow for Claude Code using Playwright.
Takes screenshots at each step for user verification.
"""

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

SCREENSHOT_DIR = Path("/workspace/clawd/oauth_screenshots")
CREDS_FILE = Path("/root/.claude/credentials.json")

async def run_oauth():
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    
    # First, start claude setup-token to get a fresh URL
    print("🔑 Starting OAuth flow...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        
        # We need to generate a fresh OAuth URL
        # For now, use a test URL to see the login page
        oauth_url = sys.argv[1] if len(sys.argv) > 1 else None
        
        if not oauth_url:
            print("Usage: oauth_automated.py <oauth_url>")
            print("Get the URL from 'claude setup-token'")
            await browser.close()
            return
        
        print(f"📡 Navigating to OAuth URL...")
        
        try:
            await page.goto(oauth_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"Navigation error: {e}")
        
        await asyncio.sleep(2)
        
        # Screenshot
        ss1 = SCREENSHOT_DIR / "step1_initial.png"
        await page.screenshot(path=str(ss1))
        print(f"📸 Screenshot: {ss1}")
        
        # Check URL
        current_url = page.url
        print(f"📍 Current URL: {current_url}")
        
        # Check if we're on the callback page already
        if "oauth/code/callback" in current_url:
            parsed = urlparse(current_url)
            params = parse_qs(parsed.query)
            if 'code' in params:
                code = params['code'][0]
                print(f"✅ Got authorization code: {code}")
                await browser.close()
                return code
        
        # Get page content summary
        title = await page.title()
        print(f"📄 Page title: {title}")
        
        # Look for login form or authorize button
        content = await page.content()
        
        if "Sign in" in content or "Log in" in content or "email" in content.lower():
            print("🔐 Login page detected")
            
            # Try to find and screenshot the form
            ss2 = SCREENSHOT_DIR / "step2_login.png"
            await page.screenshot(path=str(ss2))
            print(f"📸 Screenshot: {ss2}")
            
        elif "Authorize" in content or "Allow" in content:
            print("✅ Authorization page detected")
            
            # Try to click authorize
            try:
                auth_btn = await page.query_selector('button:has-text("Authorize"), button:has-text("Allow")')
                if auth_btn:
                    print("🖱️ Clicking authorize button...")
                    await auth_btn.click()
                    await asyncio.sleep(3)
                    
                    # Check if redirected
                    new_url = page.url
                    if "oauth/code/callback" in new_url:
                        parsed = urlparse(new_url)
                        params = parse_qs(parsed.query)
                        if 'code' in params:
                            code = params['code'][0]
                            print(f"✅ Got authorization code: {code}")
                            await browser.close()
                            return code
            except Exception as e:
                print(f"Error clicking authorize: {e}")
        
        # Final screenshot
        ss_final = SCREENSHOT_DIR / "step_final.png"
        await page.screenshot(path=str(ss_final))
        print(f"📸 Final screenshot: {ss_final}")
        
        await browser.close()
        return None

if __name__ == "__main__":
    code = asyncio.run(run_oauth())
    if code:
        print(f"\n🎉 SUCCESS! Code: {code}")
    else:
        print("\n❌ Could not complete OAuth automatically")
        print("Check screenshots in /workspace/clawd/oauth_screenshots/")
