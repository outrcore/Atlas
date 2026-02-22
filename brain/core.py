"""
Brain Core - The main orchestrator for ATLAS's memory and intelligence system.
"""
import os
import re
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from .activity import ActivityLogger
from .extractor import MemoryExtractor
from .linker import SemanticLinker
from .predictor import IntentPredictor
from .suggester import ProactiveSuggester
from .utils import ensure_api_key


class Brain:
    """
    ATLAS Brain - Proactive Memory & Intelligence System
    
    Orchestrates all brain components to provide:
    - Automatic activity logging
    - Insight extraction from conversations
    - Semantic memory linking
    - Intent prediction
    - Proactive suggestions
    """
    
    def __init__(
        self,
        workspace: str = "/workspace/clawd",
        anthropic_api_key: Optional[str] = None,
    ):
        self.workspace = Path(workspace)
        
        # Ensure API key is available
        ensure_api_key()
        self.api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        # Paths
        self.brain_dir = self.workspace / "brain_data"
        self.knowledge_dir = self.workspace / "knowledge"
        self.memory_dir = self.workspace / "memory"
        self.vector_db_path = self.workspace / "data" / "vector_db"
        
        # Ensure directories exist
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.activity_logger = ActivityLogger(self.brain_dir / "activity")
        self.extractor = MemoryExtractor(api_key=self.api_key)
        self.linker = SemanticLinker(self.vector_db_path)
        self.predictor = IntentPredictor(api_key=self.api_key)
        self.suggester = ProactiveSuggester(
            knowledge_dir=self.knowledge_dir,
            memory_dir=self.memory_dir,
            linker=self.linker,
        )
        
        # State
        self._initialized = False
        self._last_maintenance = None
        
    async def initialize(self):
        """Initialize all brain components."""
        if self._initialized:
            return
            
        print("🧠 Initializing ATLAS Brain...")
        
        # Initialize linker (loads/creates vector DB)
        await self.linker.initialize()
        
        # Load recent activity context
        self.activity_logger.load_recent(days=7)
        
        self._initialized = True
        print("🧠 Brain initialized!")
        
    def log_activity(
        self,
        activity_type: str,
        content: str,
        metadata: Optional[Dict] = None,
    ):
        """
        Log an activity (conversation, action, event).
        
        Args:
            activity_type: Type of activity (conversation, action, observation, etc.)
            content: The content/text of the activity
            metadata: Optional additional metadata
        """
        self.activity_logger.log(
            activity_type=activity_type,
            content=content,
            metadata=metadata or {},
        )
        
    async def extract_insights(
        self,
        conversation: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract insights, facts, and preferences from a conversation.
        
        Args:
            conversation: The conversation text to analyze
            context: Optional additional context
            
        Returns:
            Dict with extracted facts, preferences, action_items, etc.
        """
        return await self.extractor.extract(conversation, context)
        
    async def link_memory(
        self,
        content: str,
        category: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add content to semantic memory and link to related memories.
        
        Args:
            content: The content to store
            category: Dewey Decimal category (e.g., "300-personal")
            metadata: Optional metadata
            
        Returns:
            Memory ID
        """
        return await self.linker.add_and_link(content, category, metadata)
        
    async def find_related(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """
        Find memories related to a query.
        
        Args:
            query: Search query
            limit: Max results
            category: Optional category filter
            
        Returns:
            List of related memories with scores
        """
        return await self.linker.search(query, limit, category)
        
    async def predict_intent(
        self,
        recent_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Predict what the user might need based on recent activity.
        
        Args:
            recent_hours: How many hours of activity to consider
            
        Returns:
            Dict with predictions, confidence, and reasoning
        """
        # Get recent activities
        activities = self.activity_logger.get_recent(hours=recent_hours)
        
        # Get recent memories
        recent_memories = await self.suggester.get_recent_context()
        
        return await self.predictor.predict(
            activities=activities,
            context=recent_memories,
        )
        
    async def get_proactive_suggestions(
        self,
        current_context: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get proactive suggestions based on context and patterns.
        
        Args:
            current_context: Current conversation/task context
            
        Returns:
            List of suggestions with relevance scores
        """
        return await self.suggester.suggest(current_context)
        
    async def run_maintenance(self):
        """
        Run periodic maintenance tasks:
        - Extract insights from recent unprocessed conversations
        - Update memory links
        - Cluster related memories
        - Clean up old activity logs
        """
        print("🧠 Running brain maintenance...")
        
        # Get unprocessed activities
        unprocessed = self.activity_logger.get_unprocessed()
        
        for activity in unprocessed:
            if activity["type"] == "conversation":
                # Extract insights
                insights = await self.extract_insights(activity["content"])
                
                # Store extracted facts
                if insights.get("facts"):
                    for fact in insights["facts"]:
                        await self.link_memory(
                            content=fact,
                            category="000-reference",
                            metadata={"source": "extracted", "activity_id": activity["id"]},
                        )
                        
                # Store preferences
                if insights.get("preferences"):
                    for pref in insights["preferences"]:
                        await self.link_memory(
                            content=pref,
                            category="300-personal",
                            metadata={"source": "extracted", "type": "preference"},
                        )
                        
                # Mark as processed
                self.activity_logger.mark_processed(activity["id"])
                
        # Update memory clusters
        await self.linker.update_clusters()
        
        # Clean old logs (keep 30 days)
        self.activity_logger.cleanup(days=30)
        
        # Run memory promotion (consolidate daily logs)
        try:
            from .memory_promotion import MemoryPromoter
            promoter = MemoryPromoter(workspace_dir=str(self.workspace))
            result = await promoter.run_consolidation(days=7)
            if result.promoted_to_memory > 0 or result.promoted_to_vector > 0:
                print(f"🧠 Memory promotion: {result.promoted_to_memory} to MEMORY.md, "
                      f"{result.promoted_to_vector} to vector DB")
        except Exception as e:
            print(f"⚠️ Memory promotion error: {e}")
        
        # Run tiered synthesis (daily/weekly summaries) - check if due
        try:
            await self._run_tiered_synthesis_if_due()
        except Exception as e:
            print(f"⚠️ Tiered synthesis error: {e}")
        
        # Run reflection - once per day at most
        try:
            await self._run_reflection_if_due()
        except Exception as e:
            print(f"⚠️ Reflection error: {e}")
        
        # Check task plans for stalled tasks
        try:
            await self._check_task_plans()
        except Exception as e:
            print(f"⚠️ Task planner error: {e}")
        
        # Run graph entity extraction from daily logs
        try:
            await self._run_graph_extraction()
        except Exception as e:
            print(f"⚠️ Graph extraction error: {e}")
        
        # Auto-clean STAGING.md if needed (weekly)
        try:
            await self._clean_staging_if_due()
        except Exception as e:
            print(f"⚠️ Staging cleanup error: {e}")
        
        self._last_maintenance = datetime.now()
        print("🧠 Maintenance complete!")
    
    async def _run_tiered_synthesis_if_due(self):
        """Run tiered synthesis if enough time has passed."""
        from .tiered_synthesis import TieredSynthesis
        
        state_file = self.brain_dir / "synthesis_state.json"
        state = {}
        
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except:
                pass
        
        now = datetime.now()
        
        # Daily synthesis - run if last was > 20 hours ago
        last_daily = state.get("last_daily")
        if not last_daily or (now - datetime.fromisoformat(last_daily)).total_seconds() > 20 * 3600:
            synthesizer = TieredSynthesis(str(self.workspace))
            result = await synthesizer.run_synthesis(level="daily")
            if result.get("_success"):
                state["last_daily"] = now.isoformat()
                print("🧠 Daily synthesis complete")
        
        # Weekly synthesis - run if last was > 6 days ago
        last_weekly = state.get("last_weekly")
        if not last_weekly or (now - datetime.fromisoformat(last_weekly)).total_seconds() > 6 * 24 * 3600:
            synthesizer = TieredSynthesis(str(self.workspace))
            result = await synthesizer.run_synthesis(level="weekly")
            if result.get("_success"):
                state["last_weekly"] = now.isoformat()
                print("🧠 Weekly synthesis complete")
        
        # Save state
        state_file.write_text(json.dumps(state))
    
    async def _run_reflection_if_due(self):
        """Run self-reflection if enough time has passed."""
        from .reflection import SelfReflector
        
        state_file = self.brain_dir / "reflection_state.json"
        state = {}
        
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except:
                pass
        
        now = datetime.now()
        
        # Reflect once per day at most
        last_reflection = state.get("last_reflection")
        if not last_reflection or (now - datetime.fromisoformat(last_reflection)).total_seconds() > 20 * 3600:
            reflector = SelfReflector(workspace=str(self.workspace))
            
            # Reflect on recent behavior patterns
            reflection = await reflector.reflect_on_behavior(
                behavior="General ATLAS behavior patterns during maintenance",
                context="Daily maintenance reflection",
            )
            
            if reflection:
                state["last_reflection"] = now.isoformat()
                print(f"🧠 Reflection complete: {reflection.reflection[:100] if reflection.reflection else 'No insight'}...")
        
        state_file.write_text(json.dumps(state))
    
    async def _check_task_plans(self):
        """Check for stalled or pending task plans."""
        from .task_planner import TaskPlanner, TaskStatus
        
        planner = TaskPlanner(workspace=str(self.workspace))
        
        # Get in-progress plans
        active_plans = planner.list_plans(status=TaskStatus.IN_PROGRESS)
        pending_plans = planner.list_plans(status=TaskStatus.PENDING)
        
        # Log any stalled plans (in progress for > 24 hours)
        now = datetime.now()
        for plan in active_plans:
            if plan.started_at:
                started = datetime.fromisoformat(plan.started_at) if isinstance(plan.started_at, str) else plan.started_at
                hours_active = (now - started).total_seconds() / 3600
                if hours_active > 24:
                    print(f"⚠️ Task plan '{plan.goal[:50]}' has been in progress for {hours_active:.0f} hours")
        
        if pending_plans:
            print(f"📋 {len(pending_plans)} pending task plans")
        
    # ─────────────────────────────────────────────────────────────
    # Graph Entity Extraction from Daily Logs
    # ─────────────────────────────────────────────────────────────
    
    def _load_extraction_state(self) -> Dict[str, Any]:
        """Load the extraction state tracking file."""
        state_file = self.brain_dir / "extraction_state.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {"processed_files": {}, "last_staging_clean": None}
    
    def _save_extraction_state(self, state: Dict[str, Any]):
        """Save the extraction state tracking file."""
        state_file = self.brain_dir / "extraction_state.json"
        state_file.write_text(json.dumps(state, indent=2))
    
    async def _run_graph_extraction(self):
        """Extract entities from daily memory logs and add to graph DB."""
        from .sonnet_extractor import SonnetExtractor as CheapExtractor  # Sonnet for quality
        from .graph import EntityGraph
        
        state = self._load_extraction_state()
        processed = state.get("processed_files", {})
        
        # Find daily log files from the last 14 days
        cutoff = datetime.now() - timedelta(days=14)
        daily_files = []
        for f in sorted(self.memory_dir.glob("????-??-??.md")):
            # Parse date from filename
            match = re.match(r"(\d{4}-\d{2}-\d{2})\.md$", f.name)
            if not match:
                continue
            file_date = datetime.strptime(match.group(1), "%Y-%m-%d")
            if file_date < cutoff:
                continue
            # Skip if already processed with same file size (content unchanged)
            file_key = f.name
            file_size = f.stat().st_size
            if file_key in processed and processed[file_key].get("size") == file_size:
                continue
            daily_files.append(f)
        
        if not daily_files:
            return
        
        # Process max 3 files per run to keep maintenance fast (~3 min max)
        # Prioritize most recent files first
        daily_files = sorted(daily_files, key=lambda f: f.name, reverse=True)[:3]
        
        extractor = CheapExtractor()
        graph = EntityGraph()
        
        total_new_nodes = 0
        total_new_edges = 0
        files_processed = 0
        
        for daily_file in daily_files:
            try:
                content = daily_file.read_text(encoding="utf-8")
                source_file = daily_file.name
                
                # Chunk large files: extract from multiple sections
                chunks = self._chunk_text(content, max_chunk=3500)
                
                all_entities = {
                    "people": set(),
                    "projects": set(),
                    "tools": set(),
                    "decisions": [],
                    "facts": [],
                }
                
                for chunk in chunks:
                    result = await extractor.extract(chunk)
                    if not result.get("_success"):
                        continue
                    
                    # Merge entities - handle both dict and list formats
                    entities = result.get("key_entities", {})
                    # Sometimes extractor returns flat format, sometimes nested
                    people = result.get("people", entities.get("people", []))
                    projects = result.get("projects", entities.get("projects", []))
                    tools = result.get("tools", entities.get("tools", []))
                    decisions = result.get("decisions", entities.get("decisions", []))
                    facts = result.get("facts", [])
                    
                    if isinstance(people, list):
                        all_entities["people"].update(str(p) for p in people if p)
                    if isinstance(projects, list):
                        all_entities["projects"].update(str(p) for p in projects if p)
                    if isinstance(tools, list):
                        all_entities["tools"].update(str(t) for t in tools if t)
                    if isinstance(decisions, list):
                        all_entities["decisions"].extend(
                            str(d) for d in decisions if d and str(d) not in all_entities["decisions"]
                        )
                    if isinstance(facts, list):
                        all_entities["facts"].extend(
                            str(f) for f in facts if f and str(f) not in all_entities["facts"]
                        )
                    
                    # Small delay between chunks to be nice to the API
                    await asyncio.sleep(0.5)
                
                # Now insert entities into graph
                new_nodes, new_edges = self._insert_entities_to_graph(
                    graph, all_entities, source_file
                )
                total_new_nodes += new_nodes
                total_new_edges += new_edges
                files_processed += 1
                
                # Track as processed and save state incrementally
                processed[daily_file.name] = {
                    "size": daily_file.stat().st_size,
                    "processed_at": datetime.now().isoformat(),
                    "nodes_added": new_nodes,
                    "edges_added": new_edges,
                }
                state["processed_files"] = processed
                self._save_extraction_state(state)
                
            except Exception as e:
                print(f"⚠️ Error extracting from {daily_file.name}: {e}")
                continue
        
        if files_processed > 0:
            print(f"🧠 Graph extraction: {total_new_nodes} new nodes, "
                  f"{total_new_edges} new edges from {files_processed} files")
        
        # Re-index knowledge if we extracted anything new
        if total_new_nodes > 0:
            try:
                import subprocess
                subprocess.run(
                    ["python3", "/workspace/clawd/scripts/auto_index.py"],
                    capture_output=True, timeout=60
                )
                print(f"🔍 Knowledge re-indexed after graph extraction")
            except Exception as e:
                print(f"⚠️ Knowledge re-index error: {e}")
    
    def _chunk_text(self, text: str, max_chunk: int = 3500) -> List[str]:
        """Split text into representative chunks for extraction.
        
        Strategy: take beginning, middle, and end to capture diverse entities
        without making too many API calls (each takes ~10-20s).
        """
        if len(text) <= max_chunk:
            return [text]
        
        # For medium files (< 20KB), just first and last sections
        if len(text) < 20000:
            return [text[:max_chunk], text[-max_chunk:]]
        
        # For large files, take beginning, middle, and end (3 chunks max)
        mid = len(text) // 2
        return [
            text[:max_chunk],
            text[mid:mid + max_chunk],
            text[-max_chunk:],
        ]
    
    def _insert_entities_to_graph(
        self,
        graph,
        entities: Dict[str, Any],
        source_file: str,
    ) -> tuple:
        """Insert extracted entities into the graph DB. Returns (new_nodes, new_edges)."""
        new_nodes = 0
        new_edges = 0
        
        # Track node IDs by category for targeted edge creation
        people_ids = []
        project_ids = []
        tool_ids = []
        decision_ids = []
        
        # Type mapping: extractor category → graph node type
        category_map = {
            "people": ("person", people_ids),
            "projects": ("project", project_ids),
            "tools": ("tool", tool_ids),
        }
        
        # Insert people, projects, tools as nodes
        for category, (node_type, id_list) in category_map.items():
            items = entities.get(category, set())
            if isinstance(items, set):
                items = list(items)
            for name in items:
                if not name or len(str(name).strip()) < 2:
                    continue
                name = str(name).strip()
                existing = graph.find_node(node_type, name)
                metadata = {"source_files": [source_file]}
                if existing:
                    existing_sources = existing.metadata.get("source_files", [])
                    if source_file not in existing_sources:
                        existing_sources.append(source_file)
                        metadata = {"source_files": existing_sources[-10:]}
                    node_id = graph.add_node(node_type, name, metadata=metadata)
                    id_list.append(node_id)
                else:
                    node_id = graph.add_node(node_type, name, metadata=metadata)
                    id_list.append(node_id)
                    new_nodes += 1
        
        # Insert decisions as nodes
        for decision in entities.get("decisions", []):
            if not decision or len(str(decision).strip()) < 5:
                continue
            decision = str(decision).strip()[:200]
            existing = graph.find_node("decision", decision)
            metadata = {"source_file": source_file}
            if not existing:
                node_id = graph.add_node("decision", decision, metadata=metadata, importance=0.7)
                decision_ids.append(node_id)
                new_nodes += 1
            else:
                decision_ids.append(existing.id)
        
        # Add a date node for the source file
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})\.md$", source_file)
        date_node_id = None
        if date_match:
            date_str = date_match.group(1)
            existing_date = graph.find_node("date", date_str)
            if not existing_date:
                date_node_id = graph.add_node("date", date_str, metadata={"type": "daily_log"})
                new_nodes += 1
            else:
                date_node_id = existing_date.id
        
        # Create targeted edges (not full cross-product):
        # 1. All entities → date node (mentioned_in)
        all_ids = people_ids + project_ids + tool_ids + decision_ids
        if date_node_id:
            for node_id in all_ids:
                if node_id != date_node_id:
                    was_new = self._add_edge_if_new(
                        graph, node_id, date_node_id, "mentioned_in",
                        evidence=source_file
                    )
                    if was_new:
                        new_edges += 1
        
        # 2. People → projects (works_on)
        for person_id in people_ids:
            for project_id in project_ids:
                was_new = self._add_edge_if_new(
                    graph, person_id, project_id, "works_on",
                    evidence=source_file
                )
                if was_new:
                    new_edges += 1
        
        # 3. People → decisions (decided)
        for person_id in people_ids:
            for decision_id in decision_ids:
                was_new = self._add_edge_if_new(
                    graph, person_id, decision_id, "decided",
                    evidence=source_file
                )
                if was_new:
                    new_edges += 1
        
        # 4. Projects → tools (depends_on)
        for project_id in project_ids:
            for tool_id in tool_ids:
                was_new = self._add_edge_if_new(
                    graph, project_id, tool_id, "depends_on",
                    evidence=source_file
                )
                if was_new:
                    new_edges += 1
        
        return new_nodes, new_edges
    
    def _add_edge_if_new(self, graph, source_id: str, target_id: str,
                         relation: str, evidence: str = None) -> bool:
        """Add an edge, return True if it was genuinely new (not just strengthened)."""
        import sqlite3
        try:
            with sqlite3.connect(graph.db_path) as conn:
                existing = conn.execute(
                    "SELECT id FROM edges WHERE source_id = ? AND target_id = ? AND relation = ?",
                    (source_id, target_id, relation)
                ).fetchone()
            graph.add_edge(source_id, target_id, relation, evidence=evidence)
            return existing is None
        except Exception:
            return False
    
    # ─────────────────────────────────────────────────────────────
    # STAGING.md Auto-Cleanup
    # ─────────────────────────────────────────────────────────────
    
    async def _clean_staging_if_due(self):
        """Auto-archive STAGING.md if it's grown too large. Runs weekly."""
        state = self._load_extraction_state()
        last_clean = state.get("last_staging_clean")
        
        now = datetime.now()
        
        # Only run weekly
        if last_clean:
            last_clean_dt = datetime.fromisoformat(last_clean)
            if (now - last_clean_dt).total_seconds() < 7 * 24 * 3600:
                return
        
        staging_path = self.memory_dir / "STAGING.md"
        if not staging_path.exists():
            return
        
        content = staging_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        
        # Find where candidates start (after "## Pending Review" section)
        pending_idx = None
        gaps_start = None
        gaps_end = None
        
        for i, line in enumerate(lines):
            if line.strip().startswith("## Pending Review"):
                pending_idx = i
            if line.strip().startswith("### Personal Knowledge Gaps"):
                gaps_start = i
            # Find end of gaps section (next ## header or ---)
            if gaps_start is not None and gaps_end is None and i > gaps_start:
                if line.strip().startswith("## ") or (line.strip() == "---" and i > gaps_start + 1):
                    gaps_end = i
        
        if pending_idx is None:
            return
        
        # Count candidate lines (after pending review header, excluding known sections)
        candidate_lines = []
        in_candidates = False
        for i, line in enumerate(lines):
            if i <= pending_idx:
                continue
            if gaps_start and gaps_start <= i <= (gaps_end or gaps_start + 10):
                continue
            if line.strip().startswith("## Candidates") or line.strip().startswith("### "):
                in_candidates = True
            if in_candidates or (i > (gaps_end or pending_idx + 5)):
                candidate_lines.append((i, line))
        
        # Only archive if more than 100 candidate lines
        if len(candidate_lines) < 100:
            return
        
        # Build archive content
        archive_content = f"# STAGING.md Archive - {now.strftime('%Y-%m-%d')}\n\n"
        archive_content += f"*Archived {len(candidate_lines)} lines from STAGING.md*\n\n"
        archive_content += "\n".join(line for _, line in candidate_lines)
        
        # Save archive
        archive_dir = self.memory_dir / "staging_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_file = archive_dir / f"{now.strftime('%Y-%m-%d')}.md"
        archive_file.write_text(archive_content, encoding="utf-8")
        
        # Rebuild STAGING.md: keep header + gaps section, clear candidates
        preserved_lines = []
        for i, line in enumerate(lines):
            if i <= pending_idx:
                preserved_lines.append(line)
                continue
            if gaps_start and gaps_start <= i <= (gaps_end or gaps_start + 10):
                preserved_lines.append(line)
                continue
        
        # Add clean footer
        preserved_lines.append("")
        preserved_lines.append(f"*Last auto-cleaned: {now.strftime('%Y-%m-%d')}*")
        preserved_lines.append(f"*Archived {len(candidate_lines)} candidate lines to staging_archive/{now.strftime('%Y-%m-%d')}.md*")
        preserved_lines.append("")
        
        staging_path.write_text("\n".join(preserved_lines), encoding="utf-8")
        
        # Update state
        state["last_staging_clean"] = now.isoformat()
        self._save_extraction_state(state)
        
        print(f"🧹 STAGING.md cleaned: archived {len(candidate_lines)} lines")
    
    async def think(self, query: str) -> Dict[str, Any]:
        """
        High-level thinking: combines search, prediction, and suggestions.
        
        Use this for complex queries that need the full brain.
        
        Args:
            query: What to think about
            
        Returns:
            Dict with relevant_memories, predictions, suggestions, synthesis
        """
        # Find related memories
        related = await self.find_related(query, limit=10)
        
        # Get predictions
        predictions = await self.predict_intent()
        
        # Get suggestions
        suggestions = await self.get_proactive_suggestions(query)
        
        # Synthesize (could use Claude to combine these)
        return {
            "query": query,
            "relevant_memories": related,
            "predictions": predictions,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat(),
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get brain status and statistics."""
        return {
            "initialized": self._initialized,
            "last_maintenance": self._last_maintenance.isoformat() if self._last_maintenance else None,
            "activity_count": self.activity_logger.count(),
            "memory_count": self.linker.count() if self._initialized else 0,
            "paths": {
                "brain_data": str(self.brain_dir),
                "knowledge": str(self.knowledge_dir),
                "memory": str(self.memory_dir),
                "vector_db": str(self.vector_db_path),
            }
        }
