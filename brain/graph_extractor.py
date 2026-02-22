"""
Graph Extractor - UMA Phase 2

Extracts entities and relationships from text and populates the entity graph.
Wraps the existing MemoryExtractor and adds graph integration.

Created: 2026-02-06
"""

import json
import re
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

try:
    from .graph import EntityGraph, Node, Edge
    from .sonnet_extractor import SonnetExtractor
    from .contradiction import ContradictionDetector
except ImportError:
    from graph import EntityGraph, Node, Edge
    from sonnet_extractor import SonnetExtractor
    from contradiction import ContradictionDetector


@dataclass
class ExtractionResult:
    """Result of entity extraction."""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    facts: List[str]
    decisions: List[str]
    source: str
    timestamp: datetime


class GraphExtractor:
    """
    Extract entities and relationships from text, populate the graph.
    """
    
    def __init__(self, graph: Optional[EntityGraph] = None):
        self.graph = graph or EntityGraph()
        self.extractor = SonnetExtractor()
        self.contradiction_detector = ContradictionDetector(self.graph)
        
    async def extract_and_link(
        self,
        text: str,
        source: str,
        context: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract entities from text and add them to the graph.
        
        Args:
            text: The text to analyze
            source: Source file/location (e.g., "memory/2026-02-06.md")
            context: Optional additional context
            
        Returns:
            ExtractionResult with nodes and edges created
        """
        # Use existing extractor for basic extraction
        extraction = await self.extractor.extract(text, context)
        
        nodes_created = []
        edges_created = []
        
        # Extract entities from the result (handle both formats)
        entities = extraction.get('key_entities', extraction)
        people = entities.get('people', extraction.get('people', []))
        projects = entities.get('projects', extraction.get('projects', []))
        tools = entities.get('tools', extraction.get('tools', extraction.get('technologies', [])))
        
        facts = extraction.get('facts', [])
        decisions = extraction.get('decisions', [])
        
        # Create person nodes
        for person in people:
            if person and len(person) > 1:  # Skip single chars
                node_id = self.graph.add_node(
                    type='person',
                    name=self._normalize_name(person),
                    metadata={'source': source, 'extracted_at': datetime.now().isoformat()},
                    importance=0.6
                )
                nodes_created.append({'id': node_id, 'type': 'person', 'name': person})
        
        # Create project nodes
        for project in projects:
            if project and len(project) > 1:
                node_id = self.graph.add_node(
                    type='project',
                    name=self._normalize_name(project),
                    metadata={'source': source},
                    importance=0.7
                )
                nodes_created.append({'id': node_id, 'type': 'project', 'name': project})
        
        # Create tool nodes
        for tool in tools:
            if tool and len(tool) > 1:
                node_id = self.graph.add_node(
                    type='tool',
                    name=self._normalize_name(tool),
                    metadata={'source': source},
                    importance=0.5
                )
                nodes_created.append({'id': node_id, 'type': 'tool', 'name': tool})
        
        # Create decision nodes from decisions list
        for decision in decisions:
            if decision and len(decision) > 5:
                decision_name = decision[:100]  # Truncate long decisions
                node_id = self.graph.add_node(
                    type='decision',
                    name=decision_name,
                    metadata={'full_text': decision, 'source': source},
                    importance=0.7
                )
                nodes_created.append({'id': node_id, 'type': 'decision', 'name': decision_name})
        
        # Extract date from source if it's a daily log
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', source)
        if date_match:
            date_str = date_match.group(1)
            date_node_id = self.graph.add_node(
                type='date',
                name=date_str,
                metadata={},
                importance=0.3
            )
            
            # Link all nodes from this source to the date
            for node in nodes_created:
                if node['type'] != 'date':
                    self.graph.add_edge(
                        node['id'],
                        date_node_id,
                        'mentioned_on',
                        evidence=source
                    )
        
        # Infer relationships between entities
        edges_created.extend(self._infer_relationships(nodes_created, text, source))
        
        # Check for contradictions with existing facts
        entity_names = [n['name'] for n in nodes_created if n['type'] in ('project', 'person', 'tool', 'concept')]
        decision_dicts = [n for n in nodes_created if n['type'] == 'decision']
        
        contradictions = []
        if decision_dicts and entity_names:
            try:
                contradictions = self.contradiction_detector.check_decisions(
                    decisions=decision_dicts,
                    entity_names=entity_names,
                    source=source,
                )
                if contradictions:
                    print(f"[contradiction] Found {len(contradictions)} contradictions:")
                    for c in contradictions:
                        print(f"  [{c.conflict_type}] {c.entity}: '{c.old_fact[:60]}' → '{c.new_fact[:60]}' (sim={c.similarity:.2f})")
            except Exception as e:
                print(f"[contradiction] Error during check: {e}")
        
        return ExtractionResult(
            nodes=nodes_created,
            edges=edges_created,
            facts=facts,
            decisions=decisions,
            source=source,
            timestamp=datetime.now()
        )
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity names for consistency."""
        # Strip whitespace and common prefixes
        name = name.strip()
        
        # Handle common aliases
        aliases = {
            'matt': 'Matt',
            'matt (@mythicalsoup)': 'Matt',
            'matt campbell': 'Matt',
            'mythicalsoup': 'MythicalSoup',
            'mattcampbell': 'mattcampbell',
            'outrcore': 'outrcore',
            'atlas': 'ATLAS',
            'iwander': 'iWander',
            'iwander.app': 'iWander',
            'wander': 'iWander',
            'betbots': 'BetBots',
            'promptwizz': 'PromptWizz',
            'uma': 'Unified Memory Architecture',
            'claude': 'Claude',
            'supabase': 'Supabase',
            'lancedb': 'LanceDB',
        }
        
        lower = name.lower()
        if lower in aliases:
            return aliases[lower]
        
        return name
    
    def _infer_relationships(
        self,
        nodes: List[Dict],
        text: str,
        source: str
    ) -> List[Dict]:
        """Infer relationships between extracted entities based on text patterns."""
        edges = []
        text_lower = text.lower()
        
        # Find Matt and ATLAS nodes if present
        matt_node = None
        atlas_node = None
        
        for node in nodes:
            if node['name'] == 'Matt':
                matt_node = node
            elif node['name'] == 'ATLAS':
                atlas_node = node
        
        # Look for relationship patterns
        patterns = [
            (r'(\w+)\s+created\s+(\w+)', 'created'),
            (r'(\w+)\s+built\s+(\w+)', 'created'),
            (r'(\w+)\s+works?\s+on\s+(\w+)', 'works_on'),
            (r'(\w+)\s+decided\s+(.+?)(?:\.|$)', 'decided'),
            (r'(\w+)\s+uses?\s+(\w+)', 'uses'),
            (r'(\w+)\s+depends?\s+on\s+(\w+)', 'depends_on'),
        ]
        
        # Project nodes get linked to Matt as creator if mentioned together
        for node in nodes:
            if node['type'] == 'project' and matt_node:
                # Check if this looks like Matt's project
                if any(kw in text_lower for kw in ['my project', 'i built', 'i created', "matt's"]):
                    edge_id = self.graph.add_edge(
                        matt_node['id'],
                        node['id'],
                        'created',
                        evidence=source
                    )
                    edges.append({
                        'id': edge_id,
                        'source': matt_node['name'],
                        'target': node['name'],
                        'relation': 'created'
                    })
            
            # ATLAS works on projects mentioned in work context
            if node['type'] == 'project' and atlas_node:
                if any(kw in text_lower for kw in ['working on', 'building', 'implementing', 'fixing']):
                    edge_id = self.graph.add_edge(
                        atlas_node['id'],
                        node['id'],
                        'works_on',
                        evidence=source
                    )
                    edges.append({
                        'id': edge_id,
                        'source': atlas_node['name'],
                        'target': node['name'],
                        'relation': 'works_on'
                    })
            
            # Decisions get linked to who made them
            if node['type'] == 'decision':
                # Check context for who decided
                if matt_node and any(kw in text_lower for kw in ['matt decided', 'i decided', 'let\'s', 'we should', 'matt wants', 'matt asked']):
                    edge_id = self.graph.add_edge(
                        matt_node['id'],
                        node['id'],
                        'decided',
                        evidence=source
                    )
                    edges.append({
                        'id': edge_id,
                        'source': matt_node['name'],
                        'target': node['name'],
                        'relation': 'decided'
                    })
                
                # ATLAS implements/builds decisions - link implementation work
                if atlas_node and any(kw in text_lower for kw in [
                    'implemented', 'built', 'created', 'fixed', 'added', 'wired',
                    'updated', 'deployed', 'configured', 'installed', 'wrote',
                    'atlas', 'sub-agent', 'spawned'
                ]):
                    edge_id = self.graph.add_edge(
                        atlas_node['id'],
                        node['id'],
                        'implemented',
                        evidence=source
                    )
                    edges.append({
                        'id': edge_id,
                        'source': atlas_node['name'],
                        'target': node['name'],
                        'relation': 'implemented'
                    })
            
            # ATLAS works on tools it uses/configures
            if node['type'] == 'tool' and atlas_node:
                if any(kw in text_lower for kw in ['configured', 'installed', 'using', 'running', 'set up']):
                    edge_id = self.graph.add_edge(
                        atlas_node['id'],
                        node['id'],
                        'uses',
                        evidence=source
                    )
                    edges.append({
                        'id': edge_id,
                        'source': atlas_node['name'],
                        'target': node['name'],
                        'relation': 'uses'
                    })
        
        # Link tools to projects they're mentioned with
        tool_nodes = [n for n in nodes if n['type'] == 'tool']
        project_nodes = [n for n in nodes if n['type'] == 'project']
        
        for tool in tool_nodes:
            for project in project_nodes:
                # If both mentioned close together, likely related
                tool_pos = text_lower.find(tool['name'].lower())
                proj_pos = text_lower.find(project['name'].lower())
                
                if tool_pos >= 0 and proj_pos >= 0 and abs(tool_pos - proj_pos) < 200:
                    edge_id = self.graph.add_edge(
                        project['id'],
                        tool['id'],
                        'uses',
                        evidence=source
                    )
                    edges.append({
                        'id': edge_id,
                        'source': project['name'],
                        'target': tool['name'],
                        'relation': 'uses'
                    })
        
        return edges
    
    def extract_from_daily_log(self, log_path: str) -> ExtractionResult:
        """
        Process a daily log file and extract all entities.
        
        Args:
            log_path: Path to the daily log markdown file
            
        Returns:
            Combined ExtractionResult for the entire file
        """
        import asyncio
        from pathlib import Path
        
        path = Path(log_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")
        
        content = path.read_text()
        
        # Split into sections and process each
        sections = re.split(r'\n## ', content)
        
        all_nodes = []
        all_edges = []
        all_facts = []
        all_decisions = []
        
        for section in sections:
            if len(section.strip()) < 50:  # Skip tiny sections
                continue
            
            # Run extraction
            result = asyncio.run(self.extract_and_link(
                text=section,
                source=str(path)
            ))
            
            all_nodes.extend(result.nodes)
            all_edges.extend(result.edges)
            all_facts.extend(result.facts)
            all_decisions.extend(result.decisions)
        
        return ExtractionResult(
            nodes=all_nodes,
            edges=all_edges,
            facts=all_facts,
            decisions=all_decisions,
            source=str(path),
            timestamp=datetime.now()
        )


# ─────────────────────────────────────────────────────────────────
# Hook into auto-extraction
# ─────────────────────────────────────────────────────────────────

_graph_extractor = None

def get_graph_extractor() -> GraphExtractor:
    """Get or create the global graph extractor instance."""
    global _graph_extractor
    if _graph_extractor is None:
        _graph_extractor = GraphExtractor()
    return _graph_extractor


async def extract_to_graph(text: str, source: str) -> ExtractionResult:
    """
    Convenience function for auto-extraction hooks.
    
    Call this from the brain daemon or auto-extraction to populate the graph.
    """
    extractor = get_graph_extractor()
    return await extractor.extract_and_link(text, source)


# ─────────────────────────────────────────────────────────────────
# CLI for testing
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import asyncio
    
    if len(sys.argv) < 2:
        print("Usage: python graph_extractor.py <text or file path>")
        print("\nExamples:")
        print("  python graph_extractor.py 'Matt built iWander using Supabase'")
        print("  python graph_extractor.py memory/2026-02-06.md")
        sys.exit(1)
    
    arg = sys.argv[1]
    extractor = GraphExtractor()
    
    if arg.endswith('.md') and '/' in arg:
        # It's a file path
        print(f"Processing file: {arg}")
        result = extractor.extract_from_daily_log(arg)
    else:
        # It's text
        print(f"Processing text: {arg[:50]}...")
        result = asyncio.run(extractor.extract_and_link(arg, "cli_test"))
    
    print(f"\n=== Extraction Results ===")
    print(f"Nodes created: {len(result.nodes)}")
    for node in result.nodes:
        print(f"  [{node['type']}] {node['name']}")
    
    print(f"\nEdges created: {len(result.edges)}")
    for edge in result.edges:
        print(f"  {edge['source']} → ({edge['relation']}) → {edge['target']}")
    
    print(f"\nFacts: {len(result.facts)}")
    for fact in result.facts[:5]:
        print(f"  • {fact}")
    
    print(f"\nGraph stats:")
    stats = extractor.graph.get_stats()
    print(f"  Total nodes: {stats['nodes']}")
    print(f"  Total edges: {stats['edges']}")
