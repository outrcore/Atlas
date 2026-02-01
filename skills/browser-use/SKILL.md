# Browser-Use Skill

Autonomous web browser control for AI agents.

## Installation
Already installed: `browser-use==0.11.5`

## Basic Usage

```python
from browser_use import Agent, Browser
import asyncio

async def browse():
    browser = Browser()
    
    agent = Agent(
        task="Find the latest news about AI",
        browser=browser,
    )
    
    history = await agent.run()
    return history

asyncio.run(browse())
```

## CLI Commands

```bash
browser-use open https://example.com    # Navigate to URL
browser-use state                        # See clickable elements
browser-use click 5                      # Click element by index
browser-use type "Hello"                 # Type text
browser-use screenshot page.png          # Take screenshot
browser-use close                        # Close browser
```

## Use Cases
- Autonomous web research
- Form filling
- Data extraction from websites
- Testing web applications

## Notes
- Requires Chromium: `uvx browser-use install`
- Can use cloud or local browser
- Supports multiple LLM providers
