"""
Seed the entity graph with known entities from memory files.
Run this once to bootstrap the graph, then let extractors maintain it.

Created: 2026-02-06 (Nightly Build)
"""

from pathlib import Path
from graph import EntityGraph


def seed_graph():
    """Seed the graph with known entities."""
    graph = EntityGraph()
    
    # ─────────────────────────────────────────────────────────────
    # Core People
    # ─────────────────────────────────────────────────────────────
    
    user_node = graph.add_node('person', 'User', {
        'full_name': 'YOUR_NAME',
        'location': 'YOUR_CITY, YOUR_STATE',
        'role': 'creator',
        'github': 'outrcore',
        'discord_id': '395265690170294303',
        'telegram': '@YourHandle'
    }, importance=1.0)
    
    atlas = graph.add_node('person', 'ATLAS', {
        'role': 'AI assistant',
        'created': '2026-01-30',
        'emoji': '🌐'
    }, importance=0.95)
    
    # ─────────────────────────────────────────────────────────────
    # Projects
    # ─────────────────────────────────────────────────────────────
    
    project_alpha = graph.add_node('project', 'ProjectAlpha', {
        'url': 'project_alpha.app',
        'description': 'AI-powered travel/exploration app',
        'stack': 'Next.js, Node, Supabase',
        'status': 'active',
        'version': '1.5'
    }, importance=0.9)
    
    project_beta = graph.add_node('project', 'ProjectBeta', {
        'url': 'YOUR_PROJECT_URL',
        'description': 'Prediction market for AI agents',
        'launched': '2026-02-03',
        'status': 'active'
    }, importance=0.85)
    
    project_gamma = graph.add_node('project', 'ProjectGamma', {
        'url': 'YOUR_PROJECT_URL',
        'description': 'AI prompt optimizer tool',
        'status': 'early'
    }, importance=0.6)
    
    project_c = graph.add_node('project', 'YourProject', {
        'description': 'iOS app for peptide tracking',
        'status': 'in_progress'
    }, importance=0.5)
    
    uma = graph.add_node('project', 'Unified Memory Architecture', {
        'description': 'Hybrid memory system with graphs + vectors',
        'status': 'planning',
        'phases': 5,
        'current_phase': 1
    }, importance=0.85)
    
    brain = graph.add_node('project', 'Brain System', {
        'description': 'ATLAS memory and recall system',
        'location': '/workspace/clawd/brain/',
        'status': 'active'
    }, importance=0.8)
    
    # ─────────────────────────────────────────────────────────────
    # Tools
    # ─────────────────────────────────────────────────────────────
    
    claude = graph.add_node('tool', 'Claude', {
        'provider': 'Anthropic',
        'model': 'opus-4.5'
    }, importance=0.9)
    
    lancedb = graph.add_node('tool', 'LanceDB', {
        'type': 'vector database',
        'use': 'memory search'
    }, importance=0.7)
    
    supabase = graph.add_node('tool', 'Supabase', {
        'type': 'database',
        'use': 'ProjectAlpha backend'
    }, importance=0.7)
    
    openclaw = graph.add_node('tool', 'OpenClaw', {
        'description': 'AI agent framework',
        'location': '/workspace/Jarvis'
    }, importance=0.85)
    
    # ─────────────────────────────────────────────────────────────
    # Concepts
    # ─────────────────────────────────────────────────────────────
    
    sse = graph.add_node('concept', 'SSE Streaming', {
        'description': 'Server-sent events for real-time updates'
    }, importance=0.6)
    
    lnn = graph.add_node('concept', 'Liquid Neural Networks', {
        'description': 'Continuous-time neural networks from MIT',
        'status': 'future_research'
    }, importance=0.5)
    
    # ─────────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────────
    
    # User's relationships
    graph.add_edge(user_node, project_alpha, 'created')
    graph.add_edge(user_node, project_beta, 'created')
    graph.add_edge(user_node, project_gamma, 'created')
    graph.add_edge(user_node, project_c, 'created')
    graph.add_edge(user_node, atlas, 'created')
    graph.add_edge(user_node, uma, 'decided', evidence='memory/2026-02-06.md')
    
    # ATLAS's relationships
    graph.add_edge(atlas, project_alpha, 'works_on')
    graph.add_edge(atlas, project_beta, 'works_on')
    graph.add_edge(atlas, brain, 'works_on')
    graph.add_edge(atlas, uma, 'works_on')
    graph.add_edge(atlas, openclaw, 'depends_on')
    graph.add_edge(atlas, claude, 'depends_on')
    
    # Project dependencies
    graph.add_edge(project_alpha, supabase, 'depends_on')
    graph.add_edge(project_alpha, sse, 'related_to')
    graph.add_edge(brain, lancedb, 'depends_on')
    graph.add_edge(uma, brain, 'supersedes')
    graph.add_edge(uma, lnn, 'related_to')
    
    # Tool relationships
    graph.add_edge(openclaw, claude, 'depends_on')
    
    # ─────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────
    
    stats = graph.get_stats()
    print(f"✅ Seeded entity graph:")
    print(f"   Nodes: {stats['nodes']}")
    print(f"   Edges: {stats['edges']}")
    print(f"   Types: {stats['node_types']}")
    print(f"\n   Database: {graph.db_path}")


if __name__ == "__main__":
    seed_graph()
