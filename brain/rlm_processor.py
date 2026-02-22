#!/usr/bin/env python3
"""
ATLAS Brain v2 - Phase 3: RLM Integration
==========================================
Recursive Language Model-style processing for long context consolidation.

Based on research:
- arxiv.org/abs/2512.24601 - Recursive Language Models
- Context folding for infinite input handling
- Hierarchical summarization

Key insight: Process arbitrarily long logs by recursively chunking,
summarizing, and consolidating. Like a tree where leaves are raw text
and each level up is a summary of summaries.
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ChunkResult:
    """Result of processing a single chunk."""
    chunk_id: int
    content: str
    summary: str
    key_facts: List[str]
    entities: List[str]
    importance: float  # 0.0 - 1.0
    word_count: int


@dataclass
class ConsolidationLevel:
    """A level in the recursive consolidation hierarchy."""
    level: int  # 0 = raw chunks, 1 = first summary, etc.
    chunks: List[ChunkResult]
    consolidated_summary: Optional[str] = None


@dataclass
class RLMResult:
    """Final result of RLM processing."""
    original_length: int
    levels_processed: int
    final_summary: str
    key_facts: List[str]
    entities: List[str]
    top_memories: List[str]
    processing_time: float


class RLMProcessor:
    """
    Recursive Language Model-style processor for long memory logs.
    
    Architecture:
    Level 0: Raw text chunks (e.g., 2000 tokens each)
    Level 1: Summaries of chunks
    Level 2: Summaries of summaries
    ...
    Level N: Final consolidated summary
    
    The recursion depth adapts to input size.
    """
    
    def __init__(
        self,
        chunk_size: int = 3000,  # Characters per chunk
        max_chunks_per_level: int = 5,  # Consolidate when we have this many
        max_depth: int = 4,  # Maximum recursion depth
        summarizer: Optional[Callable] = None,  # Custom summarizer function
    ):
        self.chunk_size = chunk_size
        self.max_chunks_per_level = max_chunks_per_level
        self.max_depth = max_depth
        self.summarizer = summarizer or self._default_summarizer
        
        # Processing stats
        self.stats = {
            "chunks_processed": 0,
            "consolidations": 0,
            "total_input_chars": 0,
        }
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into chunks, trying to break at paragraph boundaries."""
        chunks = []
        
        # First try to split by double newlines (paragraphs)
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # If any chunks are still too large, split by newline
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.chunk_size * 1.5:
                lines = chunk.split('\n')
                current = ""
                for line in lines:
                    if len(current) + len(line) > self.chunk_size:
                        if current:
                            final_chunks.append(current.strip())
                        current = line
                    else:
                        current += "\n" + line if current else line
                if current.strip():
                    final_chunks.append(current.strip())
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    def _default_summarizer(self, text: str, level: int) -> Dict[str, Any]:
        """
        Default summarizer using heuristics (no LLM).
        
        For production, replace with LLM-based summarization.
        """
        lines = text.strip().split('\n')
        
        # Extract key facts (lines that look important)
        key_facts = []
        entities = []
        
        important_keywords = [
            'important', 'critical', 'lesson', 'learned', 'decision',
            'created', 'built', 'fixed', 'completed', 'milestone',
            'goal', 'preference', 'matt', 'api key', 'token',
        ]
        
        for line in lines:
            line_lower = line.lower()
            
            # Check for important keywords
            for keyword in important_keywords:
                if keyword in line_lower:
                    key_facts.append(line.strip()[:200])
                    break
            
            # Extract entities (capitalized words, paths, URLs)
            import re
            words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', line)
            entities.extend(words[:3])
            
            paths = re.findall(r'/[\w/.-]+', line)
            entities.extend(paths[:2])
        
        # Remove duplicates
        key_facts = list(dict.fromkeys(key_facts))[:10]
        entities = list(dict.fromkeys(entities))[:15]
        
        # Create summary (first 500 chars + key facts)
        summary_parts = []
        
        # Add section headers if present
        headers = [l for l in lines if l.startswith('#')]
        if headers:
            summary_parts.extend(headers[:3])
        
        # Add key facts
        summary_parts.extend(key_facts[:5])
        
        summary = '\n'.join(summary_parts) if summary_parts else text[:500]
        
        # Calculate importance
        importance = 0.3
        if any(kw in text.lower() for kw in ['critical', 'important', 'lesson', 'api key']):
            importance = 0.8
        elif any(kw in text.lower() for kw in ['built', 'created', 'completed', 'decision']):
            importance = 0.6
        
        return {
            "summary": summary[:1000],
            "key_facts": key_facts,
            "entities": entities,
            "importance": importance,
        }
    
    async def _process_chunk(self, chunk: str, chunk_id: int, level: int) -> ChunkResult:
        """Process a single chunk."""
        self.stats["chunks_processed"] += 1
        
        result = self.summarizer(chunk, level)
        
        return ChunkResult(
            chunk_id=chunk_id,
            content=chunk,
            summary=result["summary"],
            key_facts=result["key_facts"],
            entities=result["entities"],
            importance=result["importance"],
            word_count=len(chunk.split()),
        )
    
    async def _consolidate_chunks(self, chunks: List[ChunkResult], level: int) -> ChunkResult:
        """Consolidate multiple chunks into one."""
        self.stats["consolidations"] += 1
        
        # Combine summaries
        combined_summary = "\n\n---\n\n".join(c.summary for c in chunks)
        
        # Combine and dedupe key facts
        all_facts = []
        for c in chunks:
            all_facts.extend(c.key_facts)
        key_facts = list(dict.fromkeys(all_facts))[:20]
        
        # Combine and dedupe entities
        all_entities = []
        for c in chunks:
            all_entities.extend(c.entities)
        entities = list(dict.fromkeys(all_entities))[:25]
        
        # Calculate combined importance
        importance = max(c.importance for c in chunks)
        
        # Re-summarize if too long
        if len(combined_summary) > self.chunk_size:
            result = self.summarizer(combined_summary, level + 1)
            combined_summary = result["summary"]
            key_facts = list(dict.fromkeys(key_facts + result["key_facts"]))[:20]
            entities = list(dict.fromkeys(entities + result["entities"]))[:25]
        
        return ChunkResult(
            chunk_id=0,  # Consolidated
            content=combined_summary,
            summary=combined_summary,
            key_facts=key_facts,
            entities=entities,
            importance=importance,
            word_count=sum(c.word_count for c in chunks),
        )
    
    async def process(self, text: str) -> RLMResult:
        """
        Process long text using recursive consolidation.
        
        Returns final summary, key facts, entities, and top memories.
        """
        start_time = datetime.now()
        self.stats["total_input_chars"] = len(text)
        
        # Level 0: Split into chunks
        raw_chunks = self._split_into_chunks(text)
        
        if not raw_chunks:
            return RLMResult(
                original_length=len(text),
                levels_processed=0,
                final_summary="",
                key_facts=[],
                entities=[],
                top_memories=[],
                processing_time=0,
            )
        
        # Process level 0 chunks
        current_level: List[ChunkResult] = []
        for i, chunk in enumerate(raw_chunks):
            result = await self._process_chunk(chunk, i, 0)
            current_level.append(result)
        
        levels_processed = 1
        
        # Recursive consolidation
        while len(current_level) > 1 and levels_processed < self.max_depth:
            next_level: List[ChunkResult] = []
            
            # Group chunks for consolidation
            for i in range(0, len(current_level), self.max_chunks_per_level):
                group = current_level[i:i + self.max_chunks_per_level]
                
                if len(group) == 1:
                    next_level.append(group[0])
                else:
                    consolidated = await self._consolidate_chunks(group, levels_processed)
                    next_level.append(consolidated)
            
            current_level = next_level
            levels_processed += 1
        
        # Final consolidation if needed
        if len(current_level) > 1:
            final = await self._consolidate_chunks(current_level, levels_processed)
        else:
            final = current_level[0]
        
        # Extract top memories (highest importance summaries)
        all_chunks = raw_chunks  # Could track through levels for better selection
        top_memories = [
            c.summary[:200] for c in sorted(
                [await self._process_chunk(chunk, i, 0) for i, chunk in enumerate(raw_chunks[:10])],
                key=lambda x: x.importance,
                reverse=True
            )[:5]
        ]
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        return RLMResult(
            original_length=len(text),
            levels_processed=levels_processed,
            final_summary=final.summary,
            key_facts=final.key_facts,
            entities=final.entities,
            top_memories=top_memories,
            processing_time=elapsed,
        )
    
    async def process_files(self, file_paths: List[Path]) -> RLMResult:
        """Process multiple files as one combined context."""
        combined_text = ""
        
        for path in file_paths:
            if path.exists():
                content = path.read_text()
                combined_text += f"\n\n=== {path.name} ===\n\n{content}"
        
        return await self.process(combined_text)


class MemoryRLM:
    """
    RLM-based memory consolidation for ATLAS Brain.
    
    Processes daily logs recursively and extracts:
    - Consolidated timeline summary
    - Cross-referenced facts
    - Entity relationships
    - Actionable memories to promote
    """
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.workspace = Path(workspace)
        self.memory_dir = self.workspace / "memory"
        self.processor = RLMProcessor(
            chunk_size=3000,
            max_chunks_per_level=4,
            max_depth=3,
        )
    
    def get_logs(self, days: int = 7) -> List[Path]:
        """Get daily log files for the last N days."""
        from datetime import timedelta
        
        logs = []
        now = datetime.now()
        
        for i in range(days):
            date = now - timedelta(days=i)
            filename = f"{date.strftime('%Y-%m-%d')}.md"
            path = self.memory_dir / filename
            if path.exists():
                logs.append(path)
        
        return logs
    
    async def consolidate_week(self) -> Dict[str, Any]:
        """Consolidate the last week's logs using RLM."""
        logs = self.get_logs(7)
        
        if not logs:
            return {"error": "No logs found"}
        
        result = await self.processor.process_files(logs)
        
        return {
            "files_processed": len(logs),
            "original_length": result.original_length,
            "levels_processed": result.levels_processed,
            "final_summary": result.final_summary,
            "key_facts": result.key_facts,
            "entities": result.entities,
            "top_memories": result.top_memories,
            "processing_time": result.processing_time,
            "stats": self.processor.stats,
        }
    
    async def cross_reference(self, days: int = 7) -> Dict[str, Any]:
        """
        Find cross-references between days.
        
        Looks for:
        - Topics mentioned on multiple days
        - Evolving projects
        - Repeated decisions/lessons
        """
        logs = self.get_logs(days)
        
        # Track entities and facts by date
        by_date: Dict[str, Dict] = {}
        
        for log in logs:
            content = log.read_text()
            result = await self.processor._process_chunk(content, 0, 0)
            
            date_str = log.stem  # YYYY-MM-DD
            by_date[date_str] = {
                "entities": set(result.entities),
                "key_facts": result.key_facts,
                "importance": result.importance,
            }
        
        # Find cross-references
        all_entities = {}
        for date, data in by_date.items():
            for entity in data["entities"]:
                if entity not in all_entities:
                    all_entities[entity] = []
                all_entities[entity].append(date)
        
        # Entities that appear on multiple days
        recurring = {
            entity: dates 
            for entity, dates in all_entities.items() 
            if len(dates) > 1
        }
        
        return {
            "days_analyzed": len(logs),
            "recurring_entities": recurring,
            "entity_count": len(all_entities),
            "recurring_count": len(recurring),
        }


async def test_rlm():
    """Test the RLM processor."""
    print("🔄 Testing RLM Processor...\n")
    
    rlm = MemoryRLM()
    
    # Test weekly consolidation
    print("📅 Consolidating last week's logs...")
    result = await rlm.consolidate_week()
    
    print(f"\n📊 Results:")
    print(f"  Files: {result.get('files_processed', 0)}")
    print(f"  Original length: {result.get('original_length', 0):,} chars")
    print(f"  Levels processed: {result.get('levels_processed', 0)}")
    print(f"  Processing time: {result.get('processing_time', 0):.2f}s")
    
    print(f"\n🔑 Key Facts ({len(result.get('key_facts', []))}):")
    for fact in result.get('key_facts', [])[:5]:
        print(f"  - {fact[:80]}...")
    
    print(f"\n👤 Entities ({len(result.get('entities', []))}):")
    print(f"  {', '.join(result.get('entities', [])[:10])}")
    
    # Test cross-referencing
    print("\n\n🔗 Cross-referencing...")
    xref = await rlm.cross_reference(7)
    
    print(f"\n📊 Cross-reference Results:")
    print(f"  Days analyzed: {xref['days_analyzed']}")
    print(f"  Total entities: {xref['entity_count']}")
    print(f"  Recurring entities: {xref['recurring_count']}")
    
    if xref['recurring_entities']:
        print("\n🔄 Recurring across days:")
        for entity, dates in list(xref['recurring_entities'].items())[:5]:
            print(f"  - {entity}: {', '.join(dates)}")


if __name__ == "__main__":
    asyncio.run(test_rlm())
