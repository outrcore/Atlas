# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## Web Research

### Perplexity API (Optional)
If you have a Perplexity API key, you can use it for research:
```bash
python tools/research.py "your question here"
python tools/research.py "detailed topic" --detailed
```

In your `.env` or here, set your key:
```
PERPLEXITY_API_KEY=YOUR_KEY_HERE
```

### In Code
```python
import requests

def perplexity_research(query):
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": "Bearer YOUR_KEY_HERE",
            "Content-Type": "application/json"
        },
        json={"model": "sonar", "messages": [{"role": "user", "content": query}]}
    )
    return response.json()["choices"][0]["message"]["content"]
```

---

## Web Browsing (Playwright)

```bash
python tools/browse.py "https://example.com"
python tools/browse.py "https://example.com" --screenshot /tmp/out.png
python tools/browse.py "https://example.com" --html  # Raw HTML
python tools/browse.py "https://example.com" --wait 5  # Wait for JS
```

---

## Claude Code (Optional)

If you have a Claude subscription and want to use Claude Code:
- **Command:** `claude`
- **Auth:** OAuth token via Claude Max/Pro subscription
- **Projects dir:** Wherever you keep your projects

### Setup
1. Run `claude` interactively
2. Type `/login`
3. Select option 1 (Claude subscription)
4. Open URL in browser, authorize, paste code back

---

## External Servers

Add your server details here:

| Server | IP | SSH Command | Purpose |
|--------|-----|-------------|---------|
| Example | 1.2.3.4 | `ssh user@1.2.3.4` | API server |

---

## Knowledge Library

- **Location:** `knowledge/`
- **Categories:** Dewey Decimal inspired (000-reference, 100-projects, etc.)

### Commands
```bash
# Rebuild vector index (after adding content)
python scripts/index_knowledge.py

# Semantic search
python scripts/search_knowledge.py "your query" [limit] [category]
```

---

## Ports Reference

| Port | Service | Notes |
|------|---------|-------|
| Add your ports here | | |

---

Add whatever helps you do your job. This is your cheat sheet.
