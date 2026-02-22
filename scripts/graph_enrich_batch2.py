#!/usr/bin/env python3
"""Graph enrichment batch 2 - process remaining high-value chunks."""

import os
import sys
import json
import sqlite3
import hashlib
import re
import time
from pathlib import Path
from datetime import datetime

CHUNKS_DIR = "/workspace/clawd/knowledge/700-chat-exports/chunks/"
GRAPH_DB = "/workspace/clawd/brain/graph.db"

# High-value keywords for scoring
SCORE_KEYWORDS = {
    # People (weight 3)
    'matt': 3, 'atlas': 2,
    # Projects (weight 2)
    'iwander': 2, 'betbots': 2, 'promptwizz': 2, 'valodin': 2, 'openclaw': 2,
    'earthai': 2, 'flip frenzy': 2, 'aimerica': 2, 'voice stack': 2,
    'brain': 1, 'memory': 1,
    # Decision signals (weight 2)
    'decided': 2, 'decision': 2, 'going with': 2, 'switched to': 2,
    'chose': 2, 'picking': 2, 'let\'s use': 2, 'we should': 1,
    # Business/strategy (weight 2)
    'monetiz': 2, 'revenue': 2, 'pricing': 2, 'launch': 1, 'deploy': 1,
    'contract': 1, 'blockchain': 1, 'token': 1, 'solana': 1, 'base': 1,
    # Architecture (weight 1)
    'architecture': 1, 'database': 1, 'api': 1, 'stack': 1, 'infrastructure': 1,
    'supabase': 1, 'vercel': 1, 'digitalocean': 1, 'runpod': 1,
}

# Words that indicate LOW value
LOW_VALUE = ['hello', 'thanks', 'thank you', 'sure', 'okay', 'got it', 
             'sounds good', 'nice', 'cool', 'great job', 'perfect']


def score_chunk(frontmatter, content_start):
    """Score a chunk 0-10 for graph value."""
    text = (' '.join(str(v) for v in frontmatter.values()) + ' ' + content_start).lower()
    
    # Skip very short chunks
    if len(content_start.strip()) < 100:
        return 0
    
    # Skip if mostly pleasantries
    words = text.split()
    if len(words) < 30:
        return 0
    
    score = 0
    for keyword, weight in SCORE_KEYWORDS.items():
        if keyword in text:
            score += weight
    
    # Bonus for [USER] messages (actual conversation vs assistant rambling)
    user_msgs = text.count('[user]')
    if user_msgs >= 2:
        score += 1
    
    # Bonus for specific technical content
    if any(x in text for x in ['github', 'npm', 'pip', 'docker', 'ssh', 'sql']):
        score += 1
    
    # Penalty for generic coding tutorials
    if isinstance(frontmatter, dict) and frontmatter.get('category') == 'coding' and not any(
        p in text for p in ['iwander', 'betbots', 'promptwizz', 'valodin', 
                            'openclaw', 'earthai', 'atlas', 'brain']):
        score -= 2
    
    return min(score, 10)


def parse_chunk(filepath):
    """Parse frontmatter and first 500 chars of content."""
    with open(filepath, 'r', errors='replace') as f:
        text = f.read(2000)  # Read enough for frontmatter + 500 chars
    
    frontmatter = {}
    content = text
    
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            content = parts[2]
            for line in fm_text.strip().split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    frontmatter[key.strip()] = val.strip()
    
    return frontmatter, content[:500]


def extract_entities_local(content_full):
    """Extract entities from chunk content using pattern matching.
    Fast, no API calls needed."""
    entities = []
    edges = []
    text = content_full.lower()
    
    # Person detection - look for names mentioned in context
    known_people = {
        'matt': ('person', 'Matt', 0.9),
        'atlas': ('person', 'ATLAS', 0.8),
        'alex finn': ('person', 'Alex Finn', 0.5),
        'sonnet': ('tool', 'Sonnet', 0.5),
        'opus': ('tool', 'Opus', 0.5),
        'haiku': ('tool', 'Haiku', 0.5),
    }
    
    known_projects = {
        'iwander': ('project', 'iWander', 0.9),
        'betbots': ('project', 'BetBots', 0.8),
        'promptwizz': ('project', 'PromptWizz', 0.7),
        'valodin': ('project', 'Valodin', 0.7),
        'openclaw': ('project', 'OpenClaw', 0.8),
        'earthai': ('project', 'EarthAI', 0.7),
        'earth ai': ('project', 'EarthAI', 0.7),
        'flip frenzy': ('project', 'Flip Frenzy', 0.6),
        'aimerica': ('project', 'AIMerica', 0.6),
        'brain system': ('project', 'Brain System', 0.7),
        'brain v2': ('project', 'ATLAS Brain v2', 0.7),
        'voice stack': ('project', 'Voice Stack', 0.6),
        'agent council': ('project', 'Agent Council', 0.6),
        'memory system': ('project', 'Memory System', 0.6),
        'swarm': ('project', 'AI Swarm', 0.5),
    }
    
    known_tools = {
        'supabase': ('tool', 'Supabase', 0.6),
        'vercel': ('tool', 'Vercel', 0.5),
        'lancedb': ('tool', 'LanceDB', 0.6),
        'digitalocean': ('tool', 'DigitalOcean', 0.5),
        'runpod': ('tool', 'RunPod', 0.5),
        'cloudflare': ('tool', 'Cloudflare', 0.5),
        'solana': ('tool', 'Solana', 0.6),
        'anchor': ('tool', 'Anchor', 0.5),
        'nextjs': ('tool', 'Next.js', 0.5),
        'next.js': ('tool', 'Next.js', 0.5),
        'react': ('tool', 'React', 0.4),
        'typescript': ('tool', 'TypeScript', 0.4),
        'python': ('tool', 'Python', 0.4),
        'playwright': ('tool', 'Playwright', 0.5),
        'elevenlabs': ('tool', 'ElevenLabs', 0.5),
        'openai': ('tool', 'OpenAI', 0.5),
        'anthropic': ('tool', 'Anthropic', 0.5),
        'claude': ('tool', 'Claude', 0.7),
        'telegram': ('tool', 'Telegram', 0.5),
        'discord': ('tool', 'Discord', 0.5),
        'docker': ('tool', 'Docker', 0.4),
        'pm2': ('tool', 'PM2', 0.4),
        'stripe': ('tool', 'Stripe', 0.5),
        'mapbox': ('tool', 'Mapbox', 0.5),
        'postgres': ('tool', 'PostgreSQL', 0.5),
        'postgresql': ('tool', 'PostgreSQL', 0.5),
        'redis': ('tool', 'Redis', 0.4),
        'base blockchain': ('tool', 'Base', 0.6),
        'base chain': ('tool', 'Base', 0.6),
    }
    
    found_entities = set()
    
    for lookup in [known_people, known_projects, known_tools]:
        for key, (etype, name, imp) in lookup.items():
            if key in text:
                found_entities.add((etype, name, imp))
    
    # Decision extraction - look for decision patterns
    decision_patterns = [
        r'(?:decided|going) (?:to |with )(.{20,80}?)(?:\.|$|\n)',
        r'(?:let\'s|we should|I\'ll) (.{20,80}?)(?:\.|$|\n)',
        r'(?:switched|switching) (?:to |from )(.{20,80}?)(?:\.|$|\n)',
        r'(?:the plan is|plan:) (.{20,80}?)(?:\.|$|\n)',
    ]
    
    for pattern in decision_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            clean = m.strip()
            if len(clean) > 15 and len(clean) < 100:
                # Only keep decisions that reference known entities
                if any(k in clean.lower() for k in list(known_projects.keys()) + list(known_tools.keys())):
                    found_entities.add(('decision', clean.capitalize(), 0.6))
    
    return list(found_entities)


def get_full_content(filepath):
    """Read full chunk content."""
    with open(filepath, 'r', errors='replace') as f:
        return f.read()


def main():
    conn = sqlite3.connect(GRAPH_DB)
    c = conn.cursor()
    
    # Load existing nodes for dedup
    c.execute('SELECT name, type, id FROM nodes')
    existing = {}
    for name, ntype, nid in c.fetchall():
        existing[(name.lower(), ntype)] = nid
    
    existing_names = set(n.lower() for n, _ in existing.keys())
    print(f"Existing nodes: {len(existing)}")
    
    # Phase 1: Score all chunks
    print("Phase 1: Scoring all 5,844 chunks...")
    chunk_scores = []
    chunk_files = sorted(os.listdir(CHUNKS_DIR))
    
    for i, fname in enumerate(chunk_files):
        if not fname.endswith('.md'):
            continue
        filepath = os.path.join(CHUNKS_DIR, fname)
        fm, content_start = parse_chunk(filepath)
        score = score_chunk(fm, content_start)
        if score >= 3:
            chunk_scores.append((filepath, fname, score, fm))
        
        if (i + 1) % 1000 == 0:
            print(f"  Scanned {i+1}/{len(chunk_files)}...")
    
    chunk_scores.sort(key=lambda x: -x[2])
    print(f"Found {len(chunk_scores)} chunks with score >= 3")
    
    # Phase 2: Extract entities from high-value chunks
    print("\nPhase 2: Extracting entities...")
    new_nodes = 0
    new_edges = 0
    all_entities = {}  # (name_lower, type) -> (name, type, importance, sources)
    chunk_entity_map = {}  # chunk_file -> list of entity keys
    
    for filepath, fname, score, fm in chunk_scores:
        content = get_full_content(filepath)
        entities = extract_entities_local(content)
        
        chunk_entities = []
        for etype, name, importance in entities:
            key = (name.lower(), etype)
            if key not in all_entities:
                all_entities[key] = (name, etype, importance, [fname])
            else:
                # Increase importance with more mentions
                old = all_entities[key]
                new_imp = min(old[2] + 0.05, 1.0)
                all_entities[key] = (old[0], old[1], new_imp, old[3] + [fname])
            chunk_entities.append(key)
        
        chunk_entity_map[fname] = chunk_entities
    
    print(f"Found {len(all_entities)} unique entities across chunks")
    
    # Phase 3: Insert new nodes (dedup against existing)
    print("\nPhase 3: Inserting new nodes...")
    inserted_nodes = {}
    
    for key, (name, etype, importance, sources) in all_entities.items():
        if key in existing:
            inserted_nodes[key] = existing[key]
            continue
        
        # Check fuzzy match
        if name.lower() in existing_names:
            # Find existing ID
            for (en, et), eid in existing.items():
                if en == name.lower():
                    inserted_nodes[key] = eid
                    break
            continue
        
        # New node
        node_id = hashlib.md5(f"{etype}:{name}".encode()).hexdigest()[:16]
        metadata = json.dumps({"source_chunks": sources[:5], "chunk_count": len(sources)})
        
        try:
            c.execute("""INSERT INTO nodes (id, type, name, metadata, importance, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (node_id, etype, name, metadata, importance, datetime.utcnow().isoformat()))
            inserted_nodes[key] = node_id
            existing[key] = node_id
            existing_names.add(name.lower())
            new_nodes += 1
        except sqlite3.IntegrityError:
            pass
    
    print(f"Inserted {new_nodes} new nodes")
    
    # Phase 4: Create edges based on co-occurrence in chunks
    print("\nPhase 4: Creating edges from co-occurrence...")
    for fname, entity_keys in chunk_entity_map.items():
        if len(entity_keys) < 2:
            continue
        
        for i in range(len(entity_keys)):
            for j in range(i + 1, len(entity_keys)):
                k1, k2 = entity_keys[i], entity_keys[j]
                if k1 not in inserted_nodes or k2 not in inserted_nodes:
                    continue
                
                id1 = inserted_nodes[k1]
                id2 = inserted_nodes[k2]
                
                # Determine relation type
                t1, t2 = k1[1], k2[1]
                if t1 == 'person' and t2 == 'project':
                    relation = 'works_on'
                elif t1 == 'project' and t2 == 'person':
                    relation = 'worked_on_by'
                    id1, id2 = id2, id1
                elif t1 == 'project' and t2 == 'tool':
                    relation = 'uses'
                elif t1 == 'tool' and t2 == 'project':
                    relation = 'used_by'
                    id1, id2 = id2, id1
                elif t1 == 'decision':
                    relation = 'decided'
                elif t2 == 'decision':
                    relation = 'decided'
                    id1, id2 = id2, id1
                else:
                    relation = 'related_to'
                
                edge_id = hashlib.md5(f"{id1}:{id2}:{relation}".encode()).hexdigest()[:16]
                try:
                    c.execute("""INSERT INTO edges (id, source_id, target_id, relation, weight, evidence, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                             (edge_id, id1, id2, relation, 1.0, f"Co-occurrence in {fname}", 
                              datetime.utcnow().isoformat()))
                    new_edges += 1
                except sqlite3.IntegrityError:
                    # Edge exists, update weight
                    c.execute("""UPDATE edges SET weight = weight + 0.1 
                                WHERE source_id = ? AND target_id = ? AND relation = ?""",
                             (id1, id2, relation))
    
    # Phase 5: Add memory links
    print("\nPhase 5: Adding memory links...")
    links_added = 0
    for fname, entity_keys in chunk_entity_map.items():
        for key in entity_keys:
            if key in inserted_nodes:
                try:
                    c.execute("INSERT INTO memory_links (node_id, chunk_id, relevance) VALUES (?, ?, ?)",
                             (inserted_nodes[key], fname, 0.8))
                    links_added += 1
                except sqlite3.IntegrityError:
                    pass
    
    conn.commit()
    
    # Final stats
    c.execute('SELECT COUNT(*) FROM nodes')
    total_nodes = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM edges')
    total_edges = c.fetchone()[0]
    
    print(f"\n{'='*50}")
    print(f"RESULTS:")
    print(f"  New nodes added: {new_nodes}")
    print(f"  New edges added: {new_edges}")
    print(f"  Memory links added: {links_added}")
    print(f"  Total nodes now: {total_nodes}")
    print(f"  Total edges now: {total_edges}")
    print(f"  Chunks processed: {len(chunk_scores)}")
    
    # Show new nodes by type
    print(f"\nNew nodes by type:")
    new_by_type = {}
    for key, (name, etype, imp, sources) in all_entities.items():
        if key not in existing or existing[key] == inserted_nodes.get(key):
            new_by_type.setdefault(etype, []).append(name)
    
    for etype, names in sorted(new_by_type.items()):
        # Only show truly new ones
        pass
    
    # Show newly added
    print(f"\nNewly added entities:")
    c.execute("SELECT type, name, importance FROM nodes WHERE created_at >= ? ORDER BY importance DESC",
             (datetime.utcnow().replace(hour=0).isoformat(),))
    for row in c.fetchall():
        print(f"  [{row[0]:10s}] {row[1]} (imp: {row[2]:.2f})")
    
    conn.close()


if __name__ == '__main__':
    main()
