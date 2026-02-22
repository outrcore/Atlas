#!/usr/bin/env python3
"""
ATLAS Memory Bridge - Sub-Agent Context Sharing

Provides a bridge for sub-agents to access ATLAS's shared memory:
- Semantic search via Brain v2 (if available)
- Keyword fallback for file-based search
- Finding logger for agents to write back
- Scratchpad integration for shared state

Usage:
    from memory_bridge import MemoryBridge, enrich_prompt, what_do_we_know
    
    bridge = MemoryBridge()
    
    # Get context for a sub-agent
    context = bridge.get_context_for_task(
        task="Research trading algorithms",
        include_recent_days=3,
        max_tokens=2000
    )
    
    # Sub-agent logs findings
    bridge.log_finding(
        task_id="research-123",
        finding="Discovered X is better than Y",
        importance="high"
    )
"""

import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import asyncio

# Paths
WORKSPACE = Path("/workspace/clawd")
MEMORY_DIR = WORKSPACE / "memory"
MEMORY_MD = WORKSPACE / "MEMORY.md"
SCRATCHPAD_DIR = WORKSPACE / "scratchpad"
SCRATCHPAD_CONTEXT = SCRATCHPAD_DIR / "context.json"
FINDINGS_LOG = MEMORY_DIR / "agent_findings.jsonl"
BRAIN_DIR = WORKSPACE / "brain"

# Token estimation (rough: ~4 chars per token)
CHARS_PER_TOKEN = 4


@dataclass
class Finding:
    """A finding logged by a sub-agent."""
    task_id: str
    finding: str
    importance: str  # high, medium, low
    timestamp: str
    agent_session: Optional[str] = None
    tags: Optional[List[str]] = None


@dataclass
class ContextChunk:
    """A chunk of context with metadata."""
    content: str
    source: str  # "memory.md", "daily:2026-02-03", "brain:semantic", etc.
    relevance: float  # 0.0-1.0
    tokens_est: int


class MemoryBridge:
    """
    Bridge for sub-agents to access ATLAS's shared memory.
    
    Supports:
    - Semantic search via Brain v2 (if available)
    - Keyword-based file search as fallback
    - Scratchpad read/write for shared state
    - Finding logger for agent outputs
    """
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.workspace = Path(workspace)
        self.memory_dir = self.workspace / "memory"
        self.memory_md = self.workspace / "MEMORY.md"
        self.scratchpad_dir = self.workspace / "scratchpad"
        self.scratchpad_context = self.scratchpad_dir / "context.json"
        self.findings_log = self.memory_dir / "agent_findings.jsonl"
        
        # Try to load Brain v2
        self._brain = None
        self._brain_initialized = False
        self._load_brain()
        
    def _load_brain(self):
        """Attempt to load Brain v2 for semantic search."""
        # Skip brain loading for now - use file-based search
        # Brain v2 requires async initialization which can hang
        # Enable this when running in an async context with proper timeout
        self._brain = None
        self._brain_available = False
        
        # To enable Brain v2:
        # try:
        #     import sys
        #     brain_path = str(BRAIN_DIR.parent)
        #     if brain_path not in sys.path:
        #         sys.path.insert(0, brain_path)
        #     from brain import Brain
        #     self._brain = Brain(workspace=str(self.workspace))
        #     self._brain_available = True
        # except:
        #     pass
    
    async def _ensure_brain_init(self):
        """Ensure Brain is initialized (lazy async init)."""
        if self._brain and not self._brain_initialized:
            try:
                await self._brain.initialize()
                self._brain_initialized = True
            except Exception as e:
                self._brain = None
                self._brain_initialized = False
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation."""
        return len(text) // CHARS_PER_TOKEN
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit token budget."""
        max_chars = max_tokens * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n...[truncated]"
    
    # =========================================================================
    # Core Context Retrieval
    # =========================================================================
    
    def get_context_for_task(
        self,
        task: str,
        include_recent_days: int = 3,
        include_long_term: bool = True,
        max_tokens: int = 2000,
        topics: Optional[List[str]] = None
    ) -> str:
        """
        Get relevant context for a sub-agent's task.
        
        Args:
            task: Description of the task
            include_recent_days: How many days of daily logs to search
            include_long_term: Whether to include MEMORY.md
            max_tokens: Maximum tokens for returned context
            topics: Optional specific topics to search for
        
        Returns:
            Formatted context string to inject into agent prompt
        """
        # Try async brain search first, fall back to sync keyword search
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - can't run nested
                return self._get_context_sync(
                    task, include_recent_days, include_long_term, max_tokens, topics
                )
            else:
                return loop.run_until_complete(
                    self._get_context_async(
                        task, include_recent_days, include_long_term, max_tokens, topics
                    )
                )
        except RuntimeError:
            # No event loop
            return asyncio.run(
                self._get_context_async(
                    task, include_recent_days, include_long_term, max_tokens, topics
                )
            )
    
    async def _get_context_async(
        self,
        task: str,
        include_recent_days: int,
        include_long_term: bool,
        max_tokens: int,
        topics: Optional[List[str]]
    ) -> str:
        """Async version - tries Brain semantic search first."""
        chunks: List[ContextChunk] = []
        
        # Build search terms
        search_terms = self._extract_keywords(task)
        if topics:
            search_terms.extend(topics)
        
        # Try Brain v2 semantic search
        await self._ensure_brain_init()
        if self._brain and self._brain_initialized:
            try:
                results = await self._brain.find_related(
                    query=task,
                    limit=5
                )
                for result in results:
                    content = result.get("content", result.get("text", ""))
                    score = result.get("score", result.get("relevance", 0.5))
                    chunks.append(ContextChunk(
                        content=content,
                        source="brain:semantic",
                        relevance=score,
                        tokens_est=self._estimate_tokens(content)
                    ))
            except Exception as e:
                pass  # Fall through to keyword search
        
        # Search recent daily logs
        daily_chunks = self._search_daily_logs(search_terms, include_recent_days)
        chunks.extend(daily_chunks)
        
        # Include long-term memory
        if include_long_term:
            memory_chunk = self._get_memory_md_context(search_terms)
            if memory_chunk:
                chunks.append(memory_chunk)
        
        # Sort by relevance and fit to token budget
        return self._compile_context(chunks, max_tokens, task)
    
    def _get_context_sync(
        self,
        task: str,
        include_recent_days: int,
        include_long_term: bool,
        max_tokens: int,
        topics: Optional[List[str]]
    ) -> str:
        """Sync fallback - keyword search only."""
        chunks: List[ContextChunk] = []
        
        search_terms = self._extract_keywords(task)
        if topics:
            search_terms.extend(topics)
        
        # Search daily logs
        daily_chunks = self._search_daily_logs(search_terms, include_recent_days)
        chunks.extend(daily_chunks)
        
        # Long-term memory
        if include_long_term:
            memory_chunk = self._get_memory_md_context(search_terms)
            if memory_chunk:
                chunks.append(memory_chunk)
        
        return self._compile_context(chunks, max_tokens, task)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Remove common words
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
            'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'not', 'only', 'same', 'so', 'than', 'too',
            'very', 'just', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'under', 'again', 'further',
            'then', 'once', 'here', 'there', 'any', 'find', 'research', 'search'
        }
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [w for w in words if w not in stopwords]
        
        # Dedupe while preserving order
        seen = set()
        unique = []
        for w in keywords:
            if w not in seen:
                seen.add(w)
                unique.append(w)
        
        return unique[:15]  # Limit to top 15
    
    def _search_daily_logs(
        self, 
        keywords: List[str], 
        days: int
    ) -> List[ContextChunk]:
        """Search recent daily log files for relevant content."""
        chunks = []
        today = datetime.now()
        
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            # Try multiple year formats (the memory files use 2026)
            for year_prefix in ["2026", "2025", "2024", date.strftime("%Y")]:
                log_path = self.memory_dir / f"{year_prefix}-{date_str[5:]}.md"
                if log_path.exists():
                    matches = self._search_file(log_path, keywords)
                    for match, score in matches:
                        chunks.append(ContextChunk(
                            content=match,
                            source=f"daily:{log_path.stem}",
                            relevance=score,
                            tokens_est=self._estimate_tokens(match)
                        ))
                    break
        
        return chunks
    
    def _search_file(
        self, 
        path: Path, 
        keywords: List[str]
    ) -> List[Tuple[str, float]]:
        """Search a file for keyword matches. Returns (content, score) tuples."""
        try:
            content = path.read_text()
        except:
            return []
        
        # Split into sections (by headers or double newlines)
        sections = re.split(r'\n(?=#+\s)|(?:\n\n)+', content)
        
        matches = []
        for section in sections:
            if len(section.strip()) < 20:
                continue
            
            # Calculate relevance score
            section_lower = section.lower()
            matches_found = sum(1 for kw in keywords if kw in section_lower)
            if matches_found > 0:
                score = min(1.0, matches_found / max(len(keywords), 1) * 2)
                matches.append((section.strip(), score))
        
        # Sort by score, return top matches
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:3]
    
    def _get_memory_md_context(
        self, 
        keywords: List[str]
    ) -> Optional[ContextChunk]:
        """Get relevant sections from MEMORY.md."""
        if not self.memory_md.exists():
            return None
        
        try:
            content = self.memory_md.read_text()
        except:
            return None
        
        # Split into sections
        sections = re.split(r'\n(?=##\s)', content)
        
        # Find matching sections
        relevant = []
        for section in sections:
            section_lower = section.lower()
            matches = sum(1 for kw in keywords if kw in section_lower)
            if matches > 0:
                score = min(1.0, matches / max(len(keywords), 1) * 2)
                relevant.append((section.strip(), score))
        
        if not relevant:
            # Include key sections anyway (credentials, rules)
            for section in sections:
                if any(h in section for h in ["## Credentials", "## Matt's Rules", "## Technical"]):
                    relevant.append((section.strip(), 0.3))
        
        if relevant:
            relevant.sort(key=lambda x: x[1], reverse=True)
            combined = "\n\n".join([r[0] for r in relevant[:3]])
            avg_score = sum(r[1] for r in relevant[:3]) / len(relevant[:3])
            return ContextChunk(
                content=combined,
                source="memory.md",
                relevance=avg_score,
                tokens_est=self._estimate_tokens(combined)
            )
        
        return None
    
    def _compile_context(
        self, 
        chunks: List[ContextChunk], 
        max_tokens: int,
        task: str
    ) -> str:
        """Compile chunks into final context string within token budget."""
        if not chunks:
            return ""
        
        # Sort by relevance
        chunks.sort(key=lambda c: c.relevance, reverse=True)
        
        # Fit to budget
        selected = []
        total_tokens = 0
        header_tokens = 50  # Reserve for header
        
        for chunk in chunks:
            if total_tokens + chunk.tokens_est + header_tokens > max_tokens:
                # Try truncating this chunk
                remaining = max_tokens - total_tokens - header_tokens
                if remaining > 100:  # Worth including if >100 tokens
                    truncated = self._truncate_to_tokens(chunk.content, remaining)
                    selected.append((chunk.source, truncated))
                break
            selected.append((chunk.source, chunk.content))
            total_tokens += chunk.tokens_est
        
        if not selected:
            return ""
        
        # Format output
        lines = ["## Relevant Context from ATLAS Memory\n"]
        
        # Group by source type
        brain_items = [(s, c) for s, c in selected if s.startswith("brain:")]
        memory_items = [(s, c) for s, c in selected if s == "memory.md"]
        daily_items = [(s, c) for s, c in selected if s.startswith("daily:")]
        
        if memory_items:
            lines.append("### From Long-Term Memory (MEMORY.md)")
            for _, content in memory_items:
                lines.append(content)
            lines.append("")
        
        if brain_items:
            lines.append("### From Semantic Search (Brain v2)")
            for _, content in brain_items:
                lines.append(f"- {content[:500]}...")
            lines.append("")
        
        if daily_items:
            lines.append("### From Recent Daily Logs")
            for source, content in daily_items:
                date = source.replace("daily:", "")
                lines.append(f"**{date}:**")
                lines.append(content[:800])
            lines.append("")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Finding Logger
    # =========================================================================
    
    def log_finding(
        self,
        task_id: str,
        finding: str,
        importance: str = "medium",
        tags: Optional[List[str]] = None,
        agent_session: Optional[str] = None
    ):
        """
        Log a finding from a sub-agent.
        
        Args:
            task_id: Identifier for the task that produced this finding
            finding: The actual finding/insight/result
            importance: "high", "medium", or "low"
            tags: Optional tags for categorization
            agent_session: Optional session ID of the agent
        """
        if importance not in ("high", "medium", "low"):
            importance = "medium"
        
        entry = Finding(
            task_id=task_id,
            finding=finding,
            importance=importance,
            timestamp=datetime.now().isoformat(),
            agent_session=agent_session,
            tags=tags or []
        )
        
        # Ensure directory exists
        self.findings_log.parent.mkdir(parents=True, exist_ok=True)
        
        # Append to JSONL
        with open(self.findings_log, 'a') as f:
            f.write(json.dumps(asdict(entry)) + "\n")
    
    def get_recent_findings(
        self, 
        limit: int = 20,
        importance: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> List[Finding]:
        """Get recent findings, optionally filtered."""
        if not self.findings_log.exists():
            return []
        
        findings = []
        try:
            with open(self.findings_log, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        finding = Finding(**data)
                        
                        # Apply filters
                        if importance and finding.importance != importance:
                            continue
                        if task_id and finding.task_id != task_id:
                            continue
                        
                        findings.append(finding)
                    except:
                        pass
        except:
            pass
        
        # Return most recent
        findings.reverse()
        return findings[:limit]
    
    # =========================================================================
    # Scratchpad Integration
    # =========================================================================
    
    def read_scratchpad(self) -> Dict[str, Any]:
        """Read the shared scratchpad context."""
        if not self.scratchpad_context.exists():
            return {"_version": 1, "_updated": None}
        
        try:
            with open(self.scratchpad_context, 'r') as f:
                return json.load(f)
        except:
            return {"_version": 1, "_updated": None}
    
    def write_scratchpad(
        self, 
        data: Dict[str, Any],
        expected_version: Optional[int] = None
    ) -> bool:
        """
        Write to scratchpad with optional version check.
        
        Args:
            data: Data to write (will be merged with existing)
            expected_version: If provided, only write if current version matches
        
        Returns:
            True if write succeeded, False if version mismatch
        """
        self.scratchpad_dir.mkdir(parents=True, exist_ok=True)
        
        current = self.read_scratchpad()
        current_version = current.get("_version", 1)
        
        # Version check
        if expected_version is not None and current_version != expected_version:
            return False
        
        # Merge data
        current.update(data)
        current["_version"] = current_version + 1
        current["_updated"] = datetime.now().isoformat()
        
        try:
            with open(self.scratchpad_context, 'w') as f:
                json.dump(current, f, indent=2)
            return True
        except:
            return False
    
    def update_scratchpad_key(
        self, 
        key: str, 
        value: Any
    ) -> bool:
        """Safely update a single key in the scratchpad."""
        return self.write_scratchpad({key: value})
    
    # =========================================================================
    # Knowledge Search
    # =========================================================================
    
    def search_knowledge(
        self, 
        query: str, 
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge library.
        
        Args:
            query: Search query
            category: Optional category filter (e.g., "100-projects", "300-personal")
            limit: Max results
        
        Returns:
            List of matching documents with content snippets
        """
        knowledge_dir = self.workspace / "knowledge"
        if not knowledge_dir.exists():
            return []
        
        keywords = self._extract_keywords(query)
        results = []
        
        # Walk knowledge directory
        search_dirs = [knowledge_dir]
        if category:
            cat_path = knowledge_dir / category
            if cat_path.exists():
                search_dirs = [cat_path]
        
        for search_dir in search_dirs:
            for md_file in search_dir.rglob("*.md"):
                try:
                    content = md_file.read_text()
                    content_lower = content.lower()
                    
                    # Score by keyword matches
                    score = sum(1 for kw in keywords if kw in content_lower)
                    if score > 0:
                        # Extract relevant snippet
                        snippet = self._extract_snippet(content, keywords)
                        results.append({
                            "path": str(md_file.relative_to(knowledge_dir)),
                            "title": md_file.stem,
                            "score": score,
                            "snippet": snippet
                        })
                except:
                    pass
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def _extract_snippet(self, content: str, keywords: List[str], max_len: int = 300) -> str:
        """Extract a relevant snippet containing keywords."""
        content_lower = content.lower()
        
        # Find first keyword occurrence
        best_pos = len(content)
        for kw in keywords:
            pos = content_lower.find(kw)
            if 0 <= pos < best_pos:
                best_pos = pos
        
        if best_pos == len(content):
            return content[:max_len] + "..."
        
        # Extract around the keyword
        start = max(0, best_pos - 50)
        end = min(len(content), best_pos + max_len)
        
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet


# =============================================================================
# Quick Helpers (Module-level functions)
# =============================================================================

_default_bridge: Optional[MemoryBridge] = None

def _get_bridge() -> MemoryBridge:
    """Get or create default bridge instance."""
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = MemoryBridge()
    return _default_bridge


def enrich_prompt(task: str, prompt: str, max_context_tokens: int = 1500) -> str:
    """
    Add relevant memory context to an agent's prompt.
    
    Args:
        task: Task description (for context retrieval)
        prompt: Original prompt
        max_context_tokens: Max tokens for injected context
    
    Returns:
        Enriched prompt with context prepended
    
    Example:
        enriched = enrich_prompt(
            task="Research trading strategies",
            prompt="Find the best momentum indicators..."
        )
    """
    bridge = _get_bridge()
    context = bridge.get_context_for_task(
        task=task,
        include_recent_days=3,
        include_long_term=True,
        max_tokens=max_context_tokens
    )
    
    if context:
        return f"{context}\n---\n\n{prompt}"
    return prompt


def what_do_we_know(topic: str, detailed: bool = False) -> str:
    """
    Search memory for information about a topic.
    
    Args:
        topic: Topic to search for
        detailed: If True, include more context
    
    Returns:
        Summary of what's known about the topic
    
    Example:
        info = what_do_we_know("iWander project")
    """
    bridge = _get_bridge()
    
    max_tokens = 3000 if detailed else 1000
    context = bridge.get_context_for_task(
        task=f"What do we know about: {topic}",
        include_recent_days=7 if detailed else 3,
        include_long_term=True,
        max_tokens=max_tokens,
        topics=[topic]
    )
    
    # Also search knowledge base
    knowledge = bridge.search_knowledge(topic, limit=3)
    
    if knowledge:
        kb_section = "\n### From Knowledge Library\n"
        for item in knowledge:
            kb_section += f"- **{item['path']}**: {item['snippet'][:200]}...\n"
        context = context + kb_section if context else kb_section
    
    if not context:
        return f"No information found about: {topic}"
    
    return context


def log_agent_finding(
    task_id: str,
    finding: str,
    importance: str = "medium",
    tags: Optional[List[str]] = None
):
    """
    Log a finding from a sub-agent.
    
    Convenience wrapper for MemoryBridge.log_finding().
    
    Example:
        log_agent_finding(
            task_id="research-trading-001",
            finding="RSI divergence is most effective in ranging markets",
            importance="high",
            tags=["trading", "technical-analysis"]
        )
    """
    bridge = _get_bridge()
    bridge.log_finding(
        task_id=task_id,
        finding=finding,
        importance=importance,
        tags=tags
    )


def get_scratchpad_value(key: str, default: Any = None) -> Any:
    """Get a value from the shared scratchpad."""
    bridge = _get_bridge()
    data = bridge.read_scratchpad()
    return data.get(key, default)


def set_scratchpad_value(key: str, value: Any) -> bool:
    """Set a value in the shared scratchpad."""
    bridge = _get_bridge()
    return bridge.update_scratchpad_key(key, value)


# =============================================================================
# Orchestrator Integration
# =============================================================================

def create_enriched_task(
    label: str,
    task: str,
    timeout: int = 300,
    context_tokens: int = 1500
) -> Dict[str, Any]:
    """
    Create an orchestrator task definition with memory context.
    
    Use this with orchestrate.py:
        from memory_bridge import create_enriched_task
        from orchestrate import Orchestrator
        
        task = create_enriched_task(
            label="research-momentum",
            task="Research momentum trading strategies"
        )
        
        orch = Orchestrator()
        results = orch.run_parallel([task])
    
    Args:
        label: Task label
        task: Task description
        timeout: Timeout in seconds
        context_tokens: Max tokens for context
    
    Returns:
        Task definition dict for Orchestrator
    """
    bridge = _get_bridge()
    context = bridge.get_context_for_task(
        task=task,
        include_recent_days=3,
        include_long_term=True,
        max_tokens=context_tokens
    )
    
    return {
        "label": label,
        "task": task,
        "timeout": timeout,
        "context": context
    }


def spawn_with_context(
    label: str,
    task: str,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Spawn an agent with automatic context injection.
    
    Returns the result dict from the orchestrator.
    
    Example:
        result = spawn_with_context(
            label="analyze-market",
            task="Analyze current crypto market conditions"
        )
    """
    try:
        from orchestrate import Orchestrator
    except ImportError:
        return {
            "status": "error",
            "error": "orchestrate module not available"
        }
    
    task_def = create_enriched_task(label, task, timeout)
    orch = Orchestrator()
    results = orch.run_parallel([task_def])
    return results.get(label, {"status": "error", "error": "Task not found in results"})


# =============================================================================
# CLI Interface
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ATLAS Memory Bridge")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search memory")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--days", type=int, default=3, help="Days of logs to search")
    search_parser.add_argument("--tokens", type=int, default=2000, help="Max tokens")
    
    # Know command
    know_parser = subparsers.add_parser("know", help="What do we know about...")
    know_parser.add_argument("topic", help="Topic to search")
    know_parser.add_argument("--detailed", action="store_true", help="More detail")
    
    # Log command
    log_parser = subparsers.add_parser("log", help="Log a finding")
    log_parser.add_argument("task_id", help="Task ID")
    log_parser.add_argument("finding", help="The finding")
    log_parser.add_argument("--importance", default="medium", choices=["high", "medium", "low"])
    
    # Findings command
    findings_parser = subparsers.add_parser("findings", help="Show recent findings")
    findings_parser.add_argument("--limit", type=int, default=10)
    findings_parser.add_argument("--importance", choices=["high", "medium", "low"])
    
    # Scratchpad command
    scratch_parser = subparsers.add_parser("scratch", help="Scratchpad operations")
    scratch_parser.add_argument("action", choices=["get", "set", "show"])
    scratch_parser.add_argument("key", nargs="?", help="Key to get/set")
    scratch_parser.add_argument("value", nargs="?", help="Value to set")
    
    args = parser.parse_args()
    bridge = MemoryBridge()
    
    if args.command == "search":
        context = bridge.get_context_for_task(
            task=args.query,
            include_recent_days=args.days,
            max_tokens=args.tokens
        )
        print(context or "No relevant context found.")
    
    elif args.command == "know":
        result = what_do_we_know(args.topic, detailed=args.detailed)
        print(result)
    
    elif args.command == "log":
        bridge.log_finding(
            task_id=args.task_id,
            finding=args.finding,
            importance=args.importance
        )
        print(f"✓ Logged finding for task: {args.task_id}")
    
    elif args.command == "findings":
        findings = bridge.get_recent_findings(
            limit=args.limit,
            importance=args.importance
        )
        if not findings:
            print("No findings yet.")
        else:
            for f in findings:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(f.importance, "⚪")
                print(f"{icon} [{f.task_id}] {f.finding[:80]}...")
    
    elif args.command == "scratch":
        if args.action == "show":
            data = bridge.read_scratchpad()
            print(json.dumps(data, indent=2))
        elif args.action == "get" and args.key:
            value = get_scratchpad_value(args.key)
            print(f"{args.key} = {json.dumps(value)}")
        elif args.action == "set" and args.key and args.value:
            try:
                value = json.loads(args.value)
            except:
                value = args.value
            set_scratchpad_value(args.key, value)
            print(f"✓ Set {args.key}")
    
    else:
        parser.print_help()
