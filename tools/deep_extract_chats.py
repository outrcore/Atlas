#!/usr/bin/env python3
"""
Deep extraction of chat exports into chunked knowledge documents.
Extracts actual conversation content from Claude and ChatGPT exports.
"""
import json, os, re, hashlib
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_PATH = "/workspace/other_ai_chat_exports/claude_data-2026-02-09-02-40-51-batch-0000/conversations.json"
CHATGPT_PATH = "/workspace/other_ai_chat_exports/openAI_a3ece8404b4007efb83449002d3a8659fb0379248845a5e15906bf5f0d69f90b-2026-02-09-02-42-38-76c851fcf82c4fbe8d60db5e9ae2a3a4/conversations.json"
CHUNKS_DIR = Path("/workspace/clawd/knowledge/700-chat-exports/chunks")
JSONL_PATH = Path("/workspace/clawd/knowledge/700-chat-exports/chunks.jsonl")

# Category detection
CATEGORIES = {
    "trading": ["trading", "kalshi", "corn", "futures", "stock", "market", "bet", "onlylocks", "betbots", "spread", "odds", "wager", "commodity", "option"],
    "ai-ml": ["gpt", "llm", "neural", "neat", "model", "train", "embedding", "transformer", "agent", "ai ", "machine learning", "deep learning", "reinforcement"],
    "health": ["peptide", "bpc-157", "tb-500", "dosing", "health", "supplement", "workout", "diet", "testosterone", "semaglutide"],
    "coding": ["python", "javascript", "react", "api", "database", "deploy", "docker", "server", "code", "function", "debug", "error"],
    "personal": ["budget", "finance", "car", "house", "move", "travel", "family", "plan"],
    "projects": ["iwander", "atlas", "openclaw", "betbots", "onlylocks", "voice", "discord"],
}

def categorize(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORIES.items():
        scores[cat] = sum(1 for k in keywords if k in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"

def extract_claude():
    """Extract messages from Claude conversations."""
    data = json.load(open(CLAUDE_PATH))
    conversations = []
    total_msgs = 0
    
    for conv in data:
        title = conv.get("name", "Untitled")
        created = conv.get("created_at", "")
        msgs = conv.get("chat_messages", [])
        total_msgs += len(msgs)
        
        # Build conversation text
        parts = []
        for msg in msgs:
            sender = msg.get("sender", "unknown")
            text = msg.get("text", "")
            if not text or not text.strip():
                # Try content field
                content = msg.get("content", [])
                if isinstance(content, list):
                    text = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                elif isinstance(content, str):
                    text = content
            if text and text.strip():
                role = "USER" if sender == "human" else "ASSISTANT"
                parts.append(f"[{role}]: {text.strip()}")
        
        if parts:
            conversations.append({
                "source": "claude",
                "title": title,
                "date": created[:10] if created else "",
                "text": "\n\n".join(parts),
                "msg_count": len(msgs),
            })
    
    return conversations, total_msgs

def walk_chatgpt_tree(mapping, node_id, messages):
    """Walk ChatGPT tree structure to extract messages in order."""
    node = mapping.get(node_id, {})
    msg = node.get("message")
    if msg:
        role = msg.get("author", {}).get("role", "")
        content = msg.get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text = " ".join(str(p) for p in parts if isinstance(p, str))
        if text.strip() and role in ("user", "assistant"):
            messages.append({"role": role, "text": text.strip()})
    
    for child_id in node.get("children", []):
        walk_chatgpt_tree(mapping, child_id, messages)

def extract_chatgpt():
    """Extract messages from ChatGPT conversations."""
    data = json.load(open(CHATGPT_PATH))
    conversations = []
    total_msgs = 0
    
    for conv in data:
        title = conv.get("title", "Untitled")
        created = conv.get("create_time")
        date_str = ""
        if created:
            try:
                date_str = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d")
            except:
                pass
        
        mapping = conv.get("mapping", {})
        # Find root nodes (no parent)
        roots = [nid for nid, n in mapping.items() if n.get("parent") is None]
        
        messages = []
        for root in roots:
            walk_chatgpt_tree(mapping, root, messages)
        
        total_msgs += len(messages)
        
        parts = []
        for msg in messages:
            role = "USER" if msg["role"] == "user" else "ASSISTANT"
            parts.append(f"[{role}]: {msg['text']}")
        
        if parts:
            conversations.append({
                "source": "chatgpt",
                "title": title,
                "date": date_str,
                "text": "\n\n".join(parts),
                "msg_count": len(messages),
            })
    
    return conversations, total_msgs

def chunk_conversation(conv, max_words=750):
    """Break a conversation into chunks of ~max_words."""
    text = conv["text"]
    words = text.split()
    
    if len(words) <= max_words:
        return [conv]
    
    # Split on message boundaries near the word limit
    messages = text.split("\n\n")
    chunks = []
    current = []
    current_words = 0
    
    for msg in messages:
        msg_words = len(msg.split())
        if current_words + msg_words > max_words and current:
            chunks.append({
                **conv,
                "text": "\n\n".join(current),
                "chunk_idx": len(chunks),
            })
            current = [msg]
            current_words = msg_words
        else:
            current.append(msg)
            current_words += msg_words
    
    if current:
        chunks.append({
            **conv,
            "text": "\n\n".join(current),
            "chunk_idx": len(chunks),
        })
    
    return chunks

def main():
    print("=== Deep Chat Export Extraction ===\n")
    
    print("Extracting Claude conversations...")
    claude_convs, claude_msgs = extract_claude()
    print(f"  {len(claude_convs)} conversations, {claude_msgs} messages")
    
    print("Extracting ChatGPT conversations...")
    gpt_convs, gpt_msgs = extract_chatgpt()
    print(f"  {len(gpt_convs)} conversations, {gpt_msgs} messages")
    
    total_msgs = claude_msgs + gpt_msgs
    print(f"\nTotal messages: {total_msgs}")
    
    # Chunk all conversations
    all_chunks = []
    for conv in claude_convs + gpt_convs:
        chunks = chunk_conversation(conv)
        for chunk in chunks:
            chunk["category"] = categorize(chunk["text"])
            all_chunks.append(chunk)
    
    print(f"Total chunks: {len(all_chunks)}")
    
    # Write JSONL for bulk indexing
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSONL_PATH, "w") as f:
        for chunk in all_chunks:
            f.write(json.dumps({
                "source": chunk["source"],
                "title": chunk["title"],
                "date": chunk["date"],
                "category": chunk["category"],
                "text": chunk["text"],
            }) + "\n")
    print(f"Wrote {JSONL_PATH}")
    
    # Also write individual markdown chunks
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    # Clean old chunks
    for f in CHUNKS_DIR.glob("chunk_*.md"):
        f.unlink()
    
    for i, chunk in enumerate(all_chunks):
        path = CHUNKS_DIR / f"chunk_{i:04d}.md"
        path.write_text(
            f"---\n"
            f"source: {chunk['source']}\n"
            f"title: {chunk['title']}\n"
            f"date: {chunk['date']}\n"
            f"category: {chunk['category']}\n"
            f"---\n\n"
            f"# {chunk['title']}\n\n"
            f"{chunk['text']}\n"
        )
    
    print(f"Wrote {len(all_chunks)} chunk files to {CHUNKS_DIR}")
    
    # Category breakdown
    cats = {}
    for c in all_chunks:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    print("\nCategory breakdown:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

if __name__ == "__main__":
    main()
