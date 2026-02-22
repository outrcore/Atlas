#!/usr/bin/env python3
"""
ATLAS Memory Promotion System
==============================
Implements a human-like memory consolidation pipeline:

Hierarchy (like human memory):
1. Sensory/Short-term → Raw activity logs (memory/YYYY-MM-DD.md)
2. Consolidation → Brain daemon extraction (during "sleep")
3. Semantic → Vector DB retrieval by association
4. Long-term → MEMORY.md + Dewey library curated knowledge

This module handles PROMOTION: deciding what moves up the chain.

Based on research:
- Recursive Language Models (arxiv.org/abs/2512.24601)
- Hippocampus-inspired dual-stream consolidation
- Hierarchical memory with temporal decay and emotion prioritization
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
import re

# Try to import LanceDB for vector operations
try:
    import lancedb
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False

# Try to import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False


@dataclass
class MemoryCandidate:
    """A piece of information being considered for promotion."""
    content: str
    source_file: str
    source_line: int
    timestamp: datetime
    category: str  # fact, preference, decision, event, lesson, todo
    importance: float  # 0.0 - 1.0
    emotion_weight: float  # 0.0 - 1.0 (emotional memories persist longer)
    recency_weight: float  # 0.0 - 1.0 (newer = higher)
    frequency: int  # How many times this or similar content appears
    related_entities: List[str] = field(default_factory=list)
    
    @property
    def promotion_score(self) -> float:
        """Calculate overall score for promotion decision."""
        # Weighted combination (inspired by human memory consolidation)
        return (
            self.importance * 0.4 +
            self.emotion_weight * 0.25 +
            self.recency_weight * 0.15 +
            min(self.frequency / 5.0, 1.0) * 0.2
        )


@dataclass
class ConsolidationResult:
    """Result of a consolidation run."""
    timestamp: datetime
    files_processed: int
    candidates_found: int
    promoted_to_memory: int
    promoted_to_vector: int
    promoted_to_library: int
    errors: List[str] = field(default_factory=list)


class MemoryPromoter:
    """
    Handles promotion of memories through the hierarchy.
    
    Promotion paths:
    - Daily logs → Vector DB (all important facts for semantic search)
    - Daily logs → MEMORY.md (curated long-term memories)
    - Daily logs → Knowledge Library (structured domain knowledge)
    """
    
    def __init__(
        self,
        workspace_dir: str = "/workspace/clawd",
        promotion_threshold: float = 0.6,
        max_memory_entries: int = 200,  # Keep MEMORY.md manageable
    ):
        self.workspace = Path(workspace_dir)
        self.memory_dir = self.workspace / "memory"
        self.memory_file = self.workspace / "MEMORY.md"
        self.knowledge_dir = self.workspace / "knowledge"
        self.vector_db_path = self.workspace / "data" / "vector_db"
        self.promotion_threshold = promotion_threshold
        self.max_memory_entries = max_memory_entries
        
        # Initialize embedding model if available
        self.embedder = None
        if HAS_EMBEDDINGS:
            try:
                self.embedder = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)
                if hasattr(self.embedder, 'max_seq_length'):
                    self.embedder.max_seq_length = 8192
            except Exception as e:
                print(f"[memory_promotion] Could not load embedder: {e}")
        
        # Initialize vector DB if available
        self.db = None
        if HAS_LANCEDB and self.vector_db_path.exists():
            try:
                self.db = lancedb.connect(str(self.vector_db_path))
            except Exception as e:
                print(f"[memory_promotion] Could not connect to vector DB: {e}")
    
    def _calculate_recency_weight(self, timestamp: datetime) -> float:
        """Calculate recency weight - newer memories score higher."""
        now = datetime.now()
        age_days = (now - timestamp).days
        
        if age_days <= 1:
            return 1.0
        elif age_days <= 7:
            return 0.8
        elif age_days <= 30:
            return 0.5
        elif age_days <= 90:
            return 0.3
        else:
            return 0.1
    
    def _estimate_importance(self, content: str) -> float:
        """Estimate importance based on content signals."""
        importance = 0.3  # Base importance
        
        # High importance signals
        high_signals = [
            "important", "critical", "crucial", "remember", "don't forget",
            "lesson learned", "mistake", "success", "breakthrough",
            "decision:", "goal:", "preference:", "rule:",
            "api key", "password", "token", "secret",
            "matt wants", "matt said", "matt prefers",
        ]
        
        # Medium importance signals
        medium_signals = [
            "completed", "finished", "built", "created", "fixed",
            "learned", "discovered", "realized", "understood",
            "todo", "plan", "next steps", "follow up",
        ]
        
        content_lower = content.lower()
        
        for signal in high_signals:
            if signal in content_lower:
                importance = max(importance, 0.8)
                break
        
        for signal in medium_signals:
            if signal in content_lower:
                importance = max(importance, 0.6)
                break
        
        # Length bonus (longer = more detailed = potentially more important)
        if len(content) > 200:
            importance += 0.1
        
        return min(importance, 1.0)
    
    def _estimate_emotion(self, content: str) -> float:
        """Estimate emotional weight - emotional memories persist longer."""
        emotion = 0.2  # Base emotion
        
        emotion_signals = [
            # Positive
            ("excited", 0.7), ("happy", 0.6), ("proud", 0.7), ("amazing", 0.6),
            ("love", 0.8), ("awesome", 0.5), ("fantastic", 0.6),
            # Negative (also memorable)
            ("frustrated", 0.7), ("angry", 0.7), ("disappointed", 0.6),
            ("worried", 0.5), ("concerned", 0.5), ("failed", 0.6),
            # Intensity markers
            ("!", 0.3), ("very", 0.2), ("extremely", 0.4),
        ]
        
        content_lower = content.lower()
        
        for signal, weight in emotion_signals:
            if signal in content_lower:
                emotion = max(emotion, weight)
        
        return min(emotion, 1.0)
    
    def _categorize_content(self, content: str) -> str:
        """Categorize content for organization."""
        content_lower = content.lower()
        
        if any(x in content_lower for x in ["api key", "token", "password", "secret"]):
            return "credential"
        elif any(x in content_lower for x in ["todo", "need to", "should", "plan to"]):
            return "todo"
        elif any(x in content_lower for x in ["learned", "lesson", "mistake", "realized"]):
            return "lesson"
        elif any(x in content_lower for x in ["decided", "decision", "chose", "will use"]):
            return "decision"
        elif any(x in content_lower for x in ["prefers", "likes", "wants", "preference"]):
            return "preference"
        elif any(x in content_lower for x in ["matt", "user", "human"]):
            return "user_info"
        elif any(x in content_lower for x in ["built", "created", "implemented", "fixed"]):
            return "event"
        else:
            return "fact"
    
    def _extract_entities(self, content: str) -> List[str]:
        """Extract named entities from content."""
        entities = []
        
        # Simple pattern matching for now (could use NER model later)
        # Look for capitalized words that might be names/projects
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
        entities.extend(words[:5])  # Limit to 5 entities
        
        # Look for paths
        paths = re.findall(r'/[\w/.-]+', content)
        entities.extend(paths[:3])
        
        # Look for URLs
        urls = re.findall(r'https?://[\w./%-]+', content)
        entities.extend(urls[:2])
        
        return list(set(entities))
    
    def parse_daily_log(self, file_path: Path) -> List[MemoryCandidate]:
        """Parse a daily log file and extract memory candidates."""
        candidates = []
        
        if not file_path.exists():
            return candidates
        
        try:
            content = file_path.read_text()
            lines = content.split('\n')
            
            # Extract date from filename (YYYY-MM-DD.md)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_path.name)
            if date_match:
                file_date = datetime.strptime(date_match.group(1), '%Y-%m-%d')
            else:
                file_date = datetime.now()
            
            # Process content in chunks (paragraphs or list items)
            current_section = ""
            current_content = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Skip empty lines and headers
                if not line:
                    if current_content:
                        chunk = '\n'.join(current_content)
                        if len(chunk) > 20:  # Minimum content length
                            candidate = MemoryCandidate(
                                content=chunk,
                                source_file=str(file_path),
                                source_line=i - len(current_content),
                                timestamp=file_date,
                                category=self._categorize_content(chunk),
                                importance=self._estimate_importance(chunk),
                                emotion_weight=self._estimate_emotion(chunk),
                                recency_weight=self._calculate_recency_weight(file_date),
                                frequency=1,
                                related_entities=self._extract_entities(chunk),
                            )
                            candidates.append(candidate)
                        current_content = []
                    continue
                
                # Track section headers
                if line.startswith('#'):
                    current_section = line.lstrip('#').strip()
                    continue
                
                # Accumulate content
                current_content.append(line)
            
            # Don't forget the last chunk
            if current_content:
                chunk = '\n'.join(current_content)
                if len(chunk) > 20:
                    candidate = MemoryCandidate(
                        content=chunk,
                        source_file=str(file_path),
                        source_line=len(lines) - len(current_content),
                        timestamp=file_date,
                        category=self._categorize_content(chunk),
                        importance=self._estimate_importance(chunk),
                        emotion_weight=self._estimate_emotion(chunk),
                        recency_weight=self._calculate_recency_weight(file_date),
                        frequency=1,
                        related_entities=self._extract_entities(chunk),
                    )
                    candidates.append(candidate)
        
        except Exception as e:
            print(f"[memory_promotion] Error parsing {file_path}: {e}")
        
        return candidates
    
    def get_recent_logs(self, days: int = 7) -> List[Path]:
        """Get daily log files from the last N days."""
        logs = []
        
        if not self.memory_dir.exists():
            return logs
        
        now = datetime.now()
        
        for i in range(days):
            date = now - timedelta(days=i)
            filename = f"{date.strftime('%Y-%m-%d')}.md"
            file_path = self.memory_dir / filename
            if file_path.exists():
                logs.append(file_path)
        
        return logs
    
    def deduplicate_candidates(
        self, 
        candidates: List[MemoryCandidate]
    ) -> List[MemoryCandidate]:
        """Remove duplicate or very similar candidates."""
        if not candidates:
            return []
        
        unique = []
        seen_content = set()
        
        for candidate in candidates:
            # Simple dedup: normalize and check content hash
            normalized = candidate.content.lower().strip()
            # Use first 100 chars as fingerprint
            fingerprint = normalized[:100]
            
            if fingerprint not in seen_content:
                seen_content.add(fingerprint)
                unique.append(candidate)
            else:
                # Increment frequency of existing similar candidate
                for existing in unique:
                    if existing.content.lower()[:100] == fingerprint:
                        existing.frequency += 1
                        break
        
        return unique
    
    def select_for_promotion(
        self, 
        candidates: List[MemoryCandidate]
    ) -> List[MemoryCandidate]:
        """Select candidates that meet the promotion threshold."""
        promoted = [c for c in candidates if c.promotion_score >= self.promotion_threshold]
        # Sort by score descending
        promoted.sort(key=lambda c: c.promotion_score, reverse=True)
        return promoted
    
    def format_for_memory_md(self, candidates: List[MemoryCandidate]) -> str:
        """Format candidates for appending to MEMORY.md."""
        if not candidates:
            return ""
        
        sections = {
            "credential": [],
            "preference": [],
            "user_info": [],
            "decision": [],
            "lesson": [],
            "event": [],
            "fact": [],
            "todo": [],
        }
        
        for candidate in candidates:
            sections.get(candidate.category, sections["fact"]).append(candidate)
        
        output = []
        output.append(f"\n\n---\n*Auto-consolidated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
        
        section_titles = {
            "credential": "## Credentials",
            "preference": "## Preferences",
            "user_info": "## About Matt",
            "decision": "## Decisions",
            "lesson": "## Lessons Learned",
            "event": "## Events",
            "fact": "## Facts",
            "todo": "## TODOs",
        }
        
        for category, title in section_titles.items():
            if sections[category]:
                output.append(f"\n{title}")
                for candidate in sections[category][:5]:  # Limit per section
                    # Clean up content for MEMORY.md
                    content = candidate.content.strip()
                    if len(content) > 500:
                        content = content[:500] + "..."
                    output.append(f"- {content}")
        
        return '\n'.join(output)
    
    async def add_to_vector_db(self, candidates: List[MemoryCandidate]) -> int:
        """Add candidates to the vector database for semantic search."""
        if not HAS_LANCEDB or not self.db or not self.embedder:
            return 0
        
        added = 0
        
        try:
            # Prepare data for insertion - match existing schema:
            # id, content, category, metadata, created_at, vector
            data = []
            import uuid
            for candidate in candidates:
                embedding = self.embedder.encode(candidate.content).tolist()
                metadata = json.dumps({
                    "source": candidate.source_file,
                    "importance": candidate.importance,
                    "emotion_weight": candidate.emotion_weight,
                    "entities": candidate.related_entities,
                })
                data.append({
                    "id": str(uuid.uuid4()),
                    "content": candidate.content,
                    "category": candidate.category,
                    "metadata": metadata,
                    "created_at": candidate.timestamp.isoformat(),
                    "vector": embedding,
                })
            
            # Get or create table
            table_name = "memories"
            if table_name in self.db.table_names():
                table = self.db.open_table(table_name)
                table.add(data)
            else:
                self.db.create_table(table_name, data)
            
            added = len(data)
        
        except Exception as e:
            print(f"[memory_promotion] Error adding to vector DB: {e}")
        
        return added
    
    def _get_staging_content(self) -> str:
        """Load current STAGING.md content for deduplication."""
        staging_file = self.workspace / "memory" / "STAGING.md"
        if staging_file.exists():
            try:
                return staging_file.read_text().lower()
            except Exception:
                pass
        return ""
    
    def _is_in_staging(self, content: str, staging_content: str) -> bool:
        """Check if content (or similar) already exists in staging."""
        # Normalize and take first 100 chars as fingerprint
        fingerprint = content.lower().strip()[:100]
        return fingerprint in staging_content
    
    async def run_consolidation(self, days: int = 7) -> ConsolidationResult:
        """Run the full consolidation pipeline."""
        result = ConsolidationResult(
            timestamp=datetime.now(),
            files_processed=0,
            candidates_found=0,
            promoted_to_memory=0,
            promoted_to_vector=0,
            promoted_to_library=0,
        )
        
        try:
            # Get recent logs
            log_files = self.get_recent_logs(days)
            result.files_processed = len(log_files)
            
            # Parse all logs
            all_candidates = []
            for log_file in log_files:
                candidates = self.parse_daily_log(log_file)
                all_candidates.extend(candidates)
            
            result.candidates_found = len(all_candidates)
            
            # Deduplicate within candidates
            unique_candidates = self.deduplicate_candidates(all_candidates)
            
            # Select for promotion
            promoted = self.select_for_promotion(unique_candidates)
            
            # Add to vector DB (all promoted candidates)
            result.promoted_to_vector = await self.add_to_vector_db(promoted)
            
            # Write candidates to STAGING.md for manual review
            # MEMORY.md is now manually curated, not auto-appended
            if promoted:
                top_candidates = promoted[:20]  # Limit to top 20
                
                # Load existing STAGING.md content for dedup
                staging_content = self._get_staging_content()
                
                # Filter out duplicates against existing MEMORY.md
                try:
                    from brain.smart_consolidation import SmartConsolidator
                    consolidator = SmartConsolidator(str(self.workspace))
                    non_duplicates = []
                    for candidate in top_candidates:
                        content = candidate.content if hasattr(candidate, 'content') else str(candidate)
                        if not content:
                            continue
                        # Check against MEMORY.md
                        is_dup, _ = consolidator.is_duplicate(content)
                        if is_dup:
                            continue
                        # Check against STAGING.md (THE FIX!)
                        if self._is_in_staging(content, staging_content):
                            continue
                        non_duplicates.append(candidate)
                    
                    filtered_count = len(top_candidates) - len(non_duplicates)
                    if filtered_count > 0:
                        print(f"[memory_promotion] Filtered {filtered_count} duplicates against MEMORY.md + STAGING.md")
                    top_candidates = non_duplicates
                except Exception as e:
                    print(f"[memory_promotion] Dedup check failed, using all candidates: {e}")
                
                if not top_candidates:
                    print("[memory_promotion] All candidates were duplicates, nothing to stage")
                else:
                    memory_content = self.format_for_memory_md(top_candidates)
                    
                    if memory_content:
                        # Write to staging file for review, not MEMORY.md directly
                        staging_file = self.workspace / "memory" / "STAGING.md"
                        staging_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Append to staging with timestamp
                        with open(staging_file, 'a') as f:
                            f.write(f"\n\n## Candidates from {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                            f.write(memory_content)
                        result.promoted_to_memory = len(top_candidates)
                        print(f"[memory_promotion] Wrote {len(top_candidates)} candidates to STAGING.md for review")
            
            print(f"[memory_promotion] Consolidation complete: "
                  f"{result.files_processed} files, "
                  f"{result.candidates_found} candidates, "
                  f"{result.promoted_to_memory} promoted to MEMORY.md, "
                  f"{result.promoted_to_vector} promoted to vector DB")
        
        except Exception as e:
            result.errors.append(str(e))
            print(f"[memory_promotion] Consolidation error: {e}")
        
        return result


async def main():
    """Run memory consolidation."""
    promoter = MemoryPromoter()
    result = await promoter.run_consolidation(days=7)
    print(json.dumps(asdict(result), default=str, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
