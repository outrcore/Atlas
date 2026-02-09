#!/usr/bin/env python3
"""
Chat Export Ingestion Pipeline
Processes Claude and ChatGPT conversation exports into ATLAS knowledge base.
"""

import json
import os
import re
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

# Paths
CLAUDE_DIR = "/workspace/other_ai_chat_exports/claude_data-2026-02-09-02-40-51-batch-0000"
CHATGPT_DIR = "/workspace/other_ai_chat_exports/openAI_a3ece8404b4007efb83449002d3a8659fb0379248845a5e15906bf5f0d69f90b-2026-02-09-02-42-38-76c851fcf82c4fbe8d60db5e9ae2a3a4"
OUTPUT_DIR = "/workspace/clawd/knowledge/700-chat-exports"
OPS_DIR = "/workspace/clawd/ops"

# Category keywords
CATEGORIES = {
    "trading": [
        "trade", "trading", "bot", "backtest", "market", "futures", "options",
        "kalshi", "hyperliquid", "crypto", "bitcoin", "ethereum", "stock",
        "portfolio", "hedge", "arbitrage", "spread", "candle", "ticker",
        "binance", "coinbase", "deribit", "profit", "loss", "pnl", "roi",
        "signal", "indicator", "macd", "rsi", "bollinger", "moving average",
        "leverage", "margin", "liquidat", "forex", "betting", "odds",
        "sportsbook", "wager", "parlay", "onlylocks", "betbots", "sportsbetting",
        "kelly criterion", "expected value", "ev+", "sharp", "bookie",
    ],
    "projects": [
        "build", "deploy", "react", "python", "api", "app", "website",
        "frontend", "backend", "database", "server", "docker", "vercel",
        "supabase", "github", "git", "repo", "repository", "code",
        "function", "class", "component", "feature", "bug", "fix",
        "refactor", "architecture", "design", "implement", "scaffold",
        "nextjs", "typescript", "javascript", "node", "express", "flask",
        "django", "tailwind", "css", "html", "aws", "digitalocean",
        "heroku", "netlify", "cloudflare", "nginx", "pm2",
    ],
    "health": [
        "peptide", "gym", "workout", "supplement", "health", "fitness",
        "exercise", "weight", "diet", "nutrition", "protein", "creatine",
        "testosterone", "trt", "bpc-157", "bpc157", "tb-500", "tb500",
        "semaglutide", "tirzepatide", "ozempic", "mounjaro", "mk-677",
        "ipamorelin", "cjc-1295", "hgh", "growth hormone", "sleep",
        "recovery", "injury", "vitamin", "mineral", "stack", "cycle",
        "bodybuilding", "strength", "cardio", "running", "lifting",
    ],
    "ai_ml": [
        "neural", "gpt", "llm", "agent", "transformer", "embedding",
        "vector", "rag", "fine-tune", "finetune", "training", "inference",
        "openai", "anthropic", "claude", "chatgpt", "mistral", "llama",
        "langchain", "langsmith", "prompt", "token", "context window",
        "machine learning", "deep learning", "nlp", "natural language",
        "diffusion", "stable diffusion", "midjourney", "dall-e",
        "reinforcement", "reward model", "alignment", "swarm", "multi-agent",
        "autonomous", "agentic", "tool use", "function calling",
    ],
    "personal": [
        "travel", "food", "dating", "apartment", "rent", "lease",
        "move", "chicago", "restaurant", "bar", "club", "friend",
        "family", "relationship", "vacation", "flight", "hotel",
        "birthday", "gift", "recipe", "cook", "music", "movie",
        "show", "netflix", "spotify", "concert", "event", "party",
        "car", "insurance", "tax", "finance personal", "budget",
        "savings", "investment personal", "401k", "ira", "mortgage",
    ],
}

# Known project names to look for
PROJECT_PATTERNS = [
    r"onlylocks", r"betbots", r"iwander", r"i-wander", r"atlas",
    r"voice.?stack", r"brain.?daemon", r"clawd", r"openclaw",
    r"swarm", r"jarvis", r"copilot", r"dashboard",
]


def parse_claude_conversations(path):
    """Parse Claude export format."""
    with open(os.path.join(path, "conversations.json")) as f:
        raw = json.load(f)
    
    convos = []
    for c in raw:
        messages = []
        for m in c.get("chat_messages", []):
            text = m.get("text", "") or ""
            if not text and m.get("content"):
                # content field sometimes has the text
                content = m["content"]
                if isinstance(content, list):
                    text = " ".join(str(p) for p in content)
                elif isinstance(content, str):
                    text = content
            messages.append({
                "role": "user" if m.get("sender") == "human" else "assistant",
                "text": text,
                "created_at": m.get("created_at", ""),
            })
        
        convos.append({
            "id": c.get("uuid", ""),
            "title": c.get("name", "Untitled"),
            "summary": c.get("summary", ""),
            "source": "claude",
            "created_at": c.get("created_at", ""),
            "updated_at": c.get("updated_at", ""),
            "messages": messages,
            "message_count": len(messages),
        })
    return convos


def walk_chatgpt_tree(mapping, current_node=None):
    """Walk ChatGPT conversation tree to get messages in order.
    
    Strategy: trace from current_node back to root via parent links,
    then reverse to get chronological order. This follows the actual
    conversation path rather than just first-child.
    """
    if not mapping:
        return []
    
    # If we have current_node, walk backwards to root
    if current_node and current_node in mapping:
        path = []
        node_id = current_node
        visited = set()
        while node_id and node_id not in visited:
            visited.add(node_id)
            path.append(node_id)
            node_id = mapping[node_id].get("parent")
        path.reverse()
    else:
        # Fallback: find root, follow last child (most likely main thread)
        root_id = None
        for nid, node in mapping.items():
            if node.get("parent") is None:
                root_id = nid
                break
        if not root_id:
            return []
        path = []
        current = root_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            path.append(current)
            children = mapping.get(current, {}).get("children", [])
            current = children[-1] if children else None  # last child = latest branch
    
    messages = []
    for node_id in path:
        node = mapping.get(node_id, {})
        msg = node.get("message")
        if msg and msg.get("content"):
            role = msg.get("author", {}).get("role", "unknown")
            content = msg["content"]
            parts = content.get("parts", [])
            text_parts = []
            for p in parts:
                if isinstance(p, str):
                    text_parts.append(p)
                elif isinstance(p, dict):
                    text_parts.append("[image]")
            text = "\n".join(text_parts)
            if text.strip() and role in ("user", "assistant"):
                messages.append({
                    "role": role,
                    "text": text,
                    "created_at": datetime.fromtimestamp(
                        msg.get("create_time", 0) or 0, tz=timezone.utc
                    ).isoformat() if msg.get("create_time") else "",
                })
    
    return messages


def parse_chatgpt_conversations(path):
    """Parse ChatGPT export format."""
    with open(os.path.join(path, "conversations.json")) as f:
        raw = json.load(f)
    
    convos = []
    for c in raw:
        messages = walk_chatgpt_tree(c.get("mapping", {}), c.get("current_node"))
        ct = c.get("create_time", 0) or 0
        ut = c.get("update_time", 0) or 0
        
        convos.append({
            "id": c.get("conversation_id", c.get("id", "")),
            "title": c.get("title", "Untitled") or "Untitled",
            "summary": "",
            "source": "chatgpt",
            "created_at": datetime.fromtimestamp(ct, tz=timezone.utc).isoformat() if ct else "",
            "updated_at": datetime.fromtimestamp(ut, tz=timezone.utc).isoformat() if ut else "",
            "messages": messages,
            "message_count": len(messages),
        })
    return convos


def categorize_conversation(convo):
    """Categorize a conversation by keyword matching. Returns list of categories."""
    # Build searchable text from title + first few messages
    text_parts = [convo["title"].lower(), convo.get("summary", "").lower()]
    for m in convo["messages"][:20]:  # First 20 messages
        text_parts.append(m["text"][:2000].lower())
    text = " ".join(text_parts)
    
    scores = {}
    for cat, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text)
        if score >= 2:
            scores[cat] = score
    
    if not scores:
        return ["other"]
    
    # Return top categories (primary + any with >50% of max score)
    max_score = max(scores.values())
    return [cat for cat, s in sorted(scores.items(), key=lambda x: -x[1]) 
            if s >= max_score * 0.5]


def extract_technologies(text):
    """Extract mentioned technologies/tools."""
    tech_patterns = [
        "python", "javascript", "typescript", "react", "nextjs", "next.js",
        "node.js", "nodejs", "express", "flask", "django", "fastapi",
        "docker", "kubernetes", "aws", "gcp", "azure", "vercel", "netlify",
        "supabase", "firebase", "mongodb", "postgres", "redis", "sqlite",
        "tailwind", "css", "html", "graphql", "rest api", "websocket",
        "playwright", "selenium", "puppeteer", "pandas", "numpy",
        "tensorflow", "pytorch", "langchain", "openai api", "anthropic api",
        "discord.js", "telegram", "twilio", "stripe", "plaid",
        "cloudflare", "nginx", "pm2", "systemd", "github actions", "ci/cd",
        "digitalocean", "heroku", "railway", "render",
    ]
    lower = text.lower()
    return list(set(t for t in tech_patterns if t in lower))


def extract_projects_from_text(text):
    """Find project references in text."""
    found = []
    lower = text.lower()
    for pattern in PROJECT_PATTERNS:
        if re.search(pattern, lower):
            found.append(re.search(pattern, lower).group())
    return list(set(found))


def format_date(iso_str):
    """Format ISO date to readable format."""
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except:
        return iso_str[:10] if len(iso_str) >= 10 else iso_str


def generate_category_markdown(category, convos):
    """Generate markdown file for a category."""
    cat_names = {
        "trading": "Trading & Finance",
        "projects": "Projects & Coding",
        "health": "Health & Fitness",
        "ai_ml": "AI & Machine Learning",
        "personal": "Personal",
        "other": "Other / Miscellaneous",
    }
    
    lines = [f"# {cat_names.get(category, category)}\n"]
    lines.append(f"*{len(convos)} conversations from chat exports*\n")
    lines.append("---\n")
    
    # Sort by date
    convos.sort(key=lambda c: c["created_at"] or "0")
    
    for convo in convos:
        date = format_date(convo["created_at"])
        source = convo["source"].upper()
        title = convo["title"]
        mc = convo["message_count"]
        
        lines.append(f"## [{date}] {title}")
        lines.append(f"*Source: {source} | Messages: {mc}*\n")
        
        if convo.get("summary"):
            lines.append(f"> {convo['summary']}\n")
        
        # Extract info from conversation text
        full_text = " ".join(m["text"][:500] for m in convo["messages"][:10])
        techs = extract_technologies(full_text)
        projects = extract_projects_from_text(full_text)
        
        if techs:
            lines.append(f"**Technologies:** {', '.join(techs[:10])}")
        if projects:
            lines.append(f"**Projects:** {', '.join(projects)}")
        lines.append("")
    
    return "\n".join(lines)


def find_onlylocks_references(all_convos):
    """Find all OnlyLocks references across conversations."""
    refs = []
    for c in all_convos:
        full_text = c["title"].lower() + " " + " ".join(m["text"].lower() for m in c["messages"])
        if "onlylocks" in full_text or "only locks" in full_text or "only-locks" in full_text:
            # Extract relevant snippets
            snippets = []
            for m in c["messages"]:
                if any(kw in m["text"].lower() for kw in ["onlylocks", "only locks", "only-locks"]):
                    snippets.append(m["text"][:500])
            refs.append({
                "title": c["title"],
                "source": c["source"],
                "date": format_date(c["created_at"]),
                "message_count": c["message_count"],
                "id": c["id"],
                "snippets": snippets[:5],
            })
    return refs


def find_trading_strategies(all_convos):
    """Find trading strategy discussions."""
    strategy_kws = ["strategy", "backtest", "algorithm", "signal", "indicator", "edge", "alpha", "systematic"]
    results = []
    for c in all_convos:
        text = c["title"].lower() + " " + " ".join(m["text"][:500].lower() for m in c["messages"][:10])
        hits = [kw for kw in strategy_kws if kw in text]
        if len(hits) >= 2 or ("strategy" in text and any(kw in text for kw in ["trade", "trading", "market", "bet"])):
            results.append({
                "title": c["title"],
                "source": c["source"],
                "date": format_date(c["created_at"]),
                "keywords": hits,
            })
    return results


def find_project_ideas(all_convos):
    """Find project ideas and plans."""
    idea_kws = ["idea", "plan", "build", "create", "project", "startup", "launch", "mvp", "prototype"]
    results = []
    for c in all_convos:
        text = c["title"].lower() + " " + " ".join(m["text"][:300].lower() for m in c["messages"][:5])
        hits = [kw for kw in idea_kws if kw in text]
        if len(hits) >= 2:
            results.append({
                "title": c["title"],
                "source": c["source"],
                "date": format_date(c["created_at"]),
            })
    return results


def build_project_inventory(all_convos):
    """Build discovered projects inventory."""
    projects = defaultdict(lambda: {
        "name": "",
        "sources": set(),
        "first_mentioned": "9999",
        "last_mentioned": "0000",
        "conversation_ids": [],
        "descriptions": [],
    })
    
    # Extended project detection
    project_names = {
        "onlylocks": "OnlyLocks - Sports betting/picks platform",
        "only locks": "OnlyLocks - Sports betting/picks platform",
        "betbots": "BetBots - Automated betting bots",
        "bet bots": "BetBots - Automated betting bots",
        "betbot": "BetBots - Automated betting bots",
        "iwander": "iWander - AI-powered travel/walking guide app",
        "i-wander": "iWander - AI-powered travel/walking guide app",
        "i wander": "iWander - AI-powered travel/walking guide app",
        "wander app": "iWander - AI-powered travel/walking guide app",
        "atlas": "ATLAS - AI assistant system",
        "clawd": "Clawd - ATLAS workspace/config",
        "openclaw": "OpenClaw - AI agent platform",
        "open claw": "OpenClaw - AI agent platform",
        "voice stack": "Voice Stack - TTS/STT services",
        "voice api": "Voice Stack - TTS/STT services",
        "elevenlabs": "Voice Stack - TTS/STT services",
        "brain daemon": "Brain Daemon - Memory consolidation",
        "brain v2": "Brain Daemon - Memory consolidation",
        "memory daemon": "Brain Daemon - Memory consolidation",
        "swarm": "AI Swarm - Multi-agent system",
        "multi-agent": "AI Swarm - Multi-agent system",
        "jarvis": "Jarvis - AI assistant",
        "dashboard": "Dashboard project",
        "copilot": "Copilot project",
    }
    
    for c in all_convos:
        full_text = c["title"].lower() + " " + " ".join(m["text"][:500].lower() for m in c["messages"][:15])
        date = format_date(c["created_at"])
        
        for pattern, desc in project_names.items():
            if pattern in full_text:
                name = desc.split(" - ")[0]
                p = projects[name.lower()]
                p["name"] = name
                p["sources"].add(c["source"])
                p["first_mentioned"] = min(p["first_mentioned"], date)
                p["last_mentioned"] = max(p["last_mentioned"], date)
                p["conversation_ids"].append(c["id"])
                if not p["descriptions"]:
                    p["descriptions"].append(desc)
    
    # Convert to serializable
    result = []
    for key, p in projects.items():
        result.append({
            "name": p["name"],
            "sources": list(p["sources"]),
            "first_mentioned": p["first_mentioned"],
            "last_mentioned": p["last_mentioned"],
            "conversation_count": len(p["conversation_ids"]),
            "conversation_ids": p["conversation_ids"][:20],
            "description": p["descriptions"][0] if p["descriptions"] else "",
        })
    
    result.sort(key=lambda x: x["conversation_count"], reverse=True)
    return result


def main():
    print("=" * 60)
    print("Chat Export Ingestion Pipeline")
    print("=" * 60)
    
    # Parse Claude
    print("\n[1/7] Parsing Claude conversations...")
    claude_convos = parse_claude_conversations(CLAUDE_DIR)
    print(f"  → {len(claude_convos)} conversations, {sum(c['message_count'] for c in claude_convos)} messages")
    
    # Parse Claude extras
    memories_path = os.path.join(CLAUDE_DIR, "memories.json")
    projects_path = os.path.join(CLAUDE_DIR, "projects.json")
    claude_memories = []
    claude_projects = []
    if os.path.exists(memories_path):
        with open(memories_path) as f:
            claude_memories = json.load(f)
        print(f"  → {len(claude_memories)} memories")
    if os.path.exists(projects_path):
        with open(projects_path) as f:
            claude_projects = json.load(f)
        print(f"  → {len(claude_projects)} projects")
    
    # Parse ChatGPT
    print("\n[2/7] Parsing ChatGPT conversations...")
    chatgpt_convos = parse_chatgpt_conversations(CHATGPT_DIR)
    print(f"  → {len(chatgpt_convos)} conversations, {sum(c['message_count'] for c in chatgpt_convos)} messages")
    
    all_convos = claude_convos + chatgpt_convos
    total_messages = sum(c["message_count"] for c in all_convos)
    print(f"\n  Total: {len(all_convos)} conversations, {total_messages} messages")
    
    # Categorize
    print("\n[3/7] Categorizing conversations...")
    categorized = defaultdict(list)
    for c in all_convos:
        cats = categorize_conversation(c)
        for cat in cats:
            categorized[cat].append(c)
    
    for cat, convos in sorted(categorized.items()):
        print(f"  → {cat}: {len(convos)} conversations")
    
    # Generate category files
    print("\n[4/7] Generating category markdown files...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    cat_filenames = {
        "trading": "trading.md",
        "projects": "projects.md",
        "health": "health.md",
        "ai_ml": "ai-ml.md",
        "personal": "personal.md",
        "other": "other.md",
    }
    
    for cat, filename in cat_filenames.items():
        if cat in categorized:
            md = generate_category_markdown(cat, categorized[cat])
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w") as f:
                f.write(md)
            print(f"  → {filepath} ({len(categorized[cat])} convos)")
    
    # Specific extractions
    print("\n[5/7] Running specific extractions...")
    
    onlylocks = find_onlylocks_references(all_convos)
    print(f"  → OnlyLocks references: {len(onlylocks)} conversations")
    
    trading_strategies = find_trading_strategies(all_convos)
    print(f"  → Trading strategy discussions: {len(trading_strategies)}")
    
    project_ideas = find_project_ideas(all_convos)
    print(f"  → Project ideas/plans: {len(project_ideas)}")
    
    # Write special extractions file
    special_md = ["# Special Extractions\n"]
    
    special_md.append("## OnlyLocks References\n")
    if onlylocks:
        for ref in onlylocks:
            special_md.append(f"### [{ref['date']}] {ref['title']} ({ref['source'].upper()})")
            special_md.append(f"*{ref['message_count']} messages*\n")
            for snip in ref["snippets"][:3]:
                special_md.append(f"> {snip[:300]}...\n")
    else:
        special_md.append("*No OnlyLocks references found.*\n")
    
    special_md.append("## Trading Strategy Discussions\n")
    for ts in trading_strategies:
        special_md.append(f"- [{ts['date']}] **{ts['title']}** ({ts['source'].upper()}) — keywords: {', '.join(ts['keywords'])}")
    
    special_md.append("\n## Project Ideas & Plans\n")
    for pi in project_ideas:
        special_md.append(f"- [{pi['date']}] **{pi['title']}** ({pi['source'].upper()})")
    
    with open(os.path.join(OUTPUT_DIR, "special-extractions.md"), "w") as f:
        f.write("\n".join(special_md))
    print(f"  → {OUTPUT_DIR}/special-extractions.md")
    
    # Project inventory
    print("\n[6/7] Building project inventory...")
    inventory = build_project_inventory(all_convos)
    os.makedirs(OPS_DIR, exist_ok=True)
    with open(os.path.join(OPS_DIR, "discovered_projects.json"), "w") as f:
        json.dump(inventory, f, indent=2)
    print(f"  → {len(inventory)} projects discovered → {OPS_DIR}/discovered_projects.json")
    for p in inventory:
        print(f"    • {p['name']} ({p['conversation_count']} convos, {p['first_mentioned']} → {p['last_mentioned']})")
    
    # Claude memories & projects files
    if claude_memories:
        mem_md = ["# Claude Memories\n", f"*{len(claude_memories)} memories extracted*\n"]
        for mem in claude_memories:
            if isinstance(mem, dict):
                mem_md.append(f"- {mem.get('content', mem.get('text', str(mem)))}")
            else:
                mem_md.append(f"- {mem}")
        with open(os.path.join(OUTPUT_DIR, "claude-memories.md"), "w") as f:
            f.write("\n".join(mem_md))
        print(f"  → Claude memories saved")
    
    if claude_projects:
        proj_md = ["# Claude Projects\n", f"*{len(claude_projects)} projects*\n"]
        for proj in claude_projects:
            if isinstance(proj, dict):
                name = proj.get("name", proj.get("title", "Unnamed"))
                desc = proj.get("description", "")
                proj_md.append(f"## {name}\n{desc}\n")
            else:
                proj_md.append(f"- {proj}")
        with open(os.path.join(OUTPUT_DIR, "claude-projects.md"), "w") as f:
            f.write("\n".join(proj_md))
        print(f"  → Claude projects saved")
    
    # Generate INDEX.md
    print("\n[7/7] Generating INDEX.md...")
    
    dates = [c["created_at"] for c in all_convos if c["created_at"]]
    dates.sort()
    earliest = format_date(dates[0]) if dates else "Unknown"
    latest = format_date(dates[-1]) if dates else "Unknown"
    
    index = [
        "# Chat Export Knowledge Base — INDEX\n",
        f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n",
        "## Overview\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Conversations | {len(all_convos)} |",
        f"| Total Messages | {total_messages} |",
        f"| Claude Conversations | {len(claude_convos)} |",
        f"| ChatGPT Conversations | {len(chatgpt_convos)} |",
        f"| Date Range | {earliest} → {latest} |",
        f"| Claude Memories | {len(claude_memories)} |",
        f"| Claude Projects | {len(claude_projects)} |",
        "",
        "## Category Breakdown\n",
        "| Category | Conversations | File |",
        "|----------|--------------|------|",
    ]
    
    for cat, filename in cat_filenames.items():
        count = len(categorized.get(cat, []))
        if count:
            index.append(f"| {cat.replace('_', '/').title()} | {count} | [{filename}]({filename}) |")
    
    index.append("")
    index.append("## Special Files\n")
    index.append("- [special-extractions.md](special-extractions.md) — OnlyLocks, trading strategies, project ideas")
    if claude_memories:
        index.append("- [claude-memories.md](claude-memories.md) — Extracted Claude memories")
    if claude_projects:
        index.append("- [claude-projects.md](claude-projects.md) — Claude project definitions")
    
    index.append("\n## Notable Projects Discovered\n")
    for p in inventory[:15]:
        index.append(f"- **{p['name']}** — {p['description']} ({p['conversation_count']} convos, {p['first_mentioned']} → {p['last_mentioned']})")
    
    index.append(f"\n## OnlyLocks References\n")
    if onlylocks:
        index.append(f"Found **{len(onlylocks)}** conversations mentioning OnlyLocks:\n")
        for ref in onlylocks:
            index.append(f"- [{ref['date']}] {ref['title']} ({ref['source'].upper()}, {ref['message_count']} msgs)")
    else:
        index.append("*No OnlyLocks references found in conversation exports.*")
    
    with open(os.path.join(OUTPUT_DIR, "INDEX.md"), "w") as f:
        f.write("\n".join(index))
    
    print(f"\n{'=' * 60}")
    print("Pipeline complete!")
    print(f"  Output: {OUTPUT_DIR}/")
    print(f"  Projects: {OPS_DIR}/discovered_projects.json")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
