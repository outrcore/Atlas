#!/usr/bin/env python3
"""
Graph enrichment v2 - Uses Kimi for smart extraction on top chunks.
"""

import os, re, json, glob, sqlite3, time, requests
from pathlib import Path
from collections import Counter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from graph import EntityGraph

CHUNKS_DIR = Path("/workspace/clawd/knowledge/700-chat-exports/chunks")
GRAPH_DB = Path(__file__).parent / "graph.db"

FIREWORKS_API_KEY = "fw_Noc4TJAZCNM1MGbXWr9xZ8"
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL = "accounts/fireworks/models/kimi-k2-instruct-0905"

GENERIC_SKIP = {
    'javascript', 'python', 'html', 'css', 'typescript', 'react', 'node.js',
    'git', 'npm', 'api', 'json', 'sql', 'bash', 'linux', 'docker', 'claude',
    'chatgpt', 'gpt-4', 'gpt-3', 'ai', 'machine learning', 'debugging',
    'web app', 'mobile app', 'frontend', 'backend', 'database',
}


def read_chunk(path):
    try:
        with open(path, 'r', errors='replace') as f:
            return f.read()
    except:
        return ""


def extract_frontmatter(text):
    match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            fm[key.strip()] = val.strip()
    return fm


def score_chunk(text):
    """Quick scoring."""
    score = 0
    tl = text.lower()
    
    # Specific project names
    for kw in ['iwander', 'betbots', 'botbets', 'valodin', 'personaplex', 'promptwizz', 
                'onlylocks', 'botgames', 'openclaw', 'memu', 'codegpt', 'earthai']:
        if kw in tl:
            score += 3
    
    # Decision/strategy language
    for kw in ['decided to', "we'll go with", "let's use", 'switching to', 'pivot',
                'strategy', 'business model', 'monetiz', 'revenue', 'launch plan']:
        if kw in tl:
            score += 2
    
    # Architecture/infra
    for kw in ['architecture', 'infrastructure', 'deploy', 'production', 'tech stack',
                'solana', 'blockchain', 'supabase', 'vercel', 'runpod', 'digitalocean']:
        if kw in tl:
            score += 1
    
    # People
    for kw in ['matt', 'henry', 'ethan', 'alex finn', 'boris']:
        if kw in tl:
            score += 1
    
    # Negative: generic coding help
    if re.search(r'\[USER\].*?(explain|what is|how do I|can you help|fix this|error)', tl[:500]):
        score -= 2
    
    return score


def kimi_extract(texts_batch):
    """Send batch of chunk texts to Kimi for entity extraction."""
    combined = ""
    for i, (chunk_name, text) in enumerate(texts_batch):
        # Trim each chunk
        combined += f"\n--- CHUNK {chunk_name} ---\n{text[:2000]}\n"
    
    prompt = f"""Extract entities from these conversation chunks. These are chat logs between a user (Matt) and AI assistants about his projects.

{combined}

Return JSON with these fields:
- projects: list of specific project/product names (NOT generic like "web app")
- people: list of named people (NOT "user" or "someone")  
- decisions: list of objects with "text" (specific consequential decision), "chunk" (which chunk), "date" (if available)
- locations: list of specific locations mentioned
- relationships: list of objects with "from", "to", "relation" (e.g. "Matt" -> "iWander" -> "created")

Only include specific, consequential items. Skip generic concepts.
JSON only:"""

    try:
        resp = requests.post(
            FIREWORKS_URL,
            headers={"Authorization": f"Bearer {FIREWORKS_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 2000, "temperature": 0.1},
            timeout=60
        )
        if resp.status_code != 200:
            print(f"  Kimi error: {resp.status_code}")
            return None
        
        content = resp.json()['choices'][0]['message']['content']
        
        # Parse JSON
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            content = match.group(1)
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return json.loads(match.group())
        return None
    except Exception as e:
        print(f"  Kimi error: {e}")
        return None


def main():
    # Pass 1: Score all chunks
    print("PASS 1: Scoring chunks...")
    chunks = sorted(glob.glob(str(CHUNKS_DIR / "chunk_*.md")))
    
    scored = []
    for path in chunks:
        header = read_chunk(path)[:800]
        s = score_chunk(header)
        if s >= 3:
            scored.append((path, s))
    
    scored.sort(key=lambda x: -x[1])
    print(f"  {len(scored)} chunks scored >= 3 (from {len(chunks)} total)")
    
    # Take top 200
    top_chunks = scored[:200]
    
    # Pass 2: Extract via Kimi in batches of 5
    print(f"\nPASS 2: Extracting from top {len(top_chunks)} chunks via Kimi...")
    
    all_projects = Counter()
    all_people = Counter()
    all_decisions = []
    all_locations = set()
    all_relationships = []
    
    batch_size = 5
    for i in range(0, len(top_chunks), batch_size):
        batch = top_chunks[i:i+batch_size]
        texts = []
        for path, _ in batch:
            text = read_chunk(path)
            fm = extract_frontmatter(text)
            name = Path(path).name
            texts.append((f"{name} (date:{fm.get('date','?')})", text))
        
        print(f"  Batch {i//batch_size + 1}/{(len(top_chunks)+batch_size-1)//batch_size}...", end=" ", flush=True)
        result = kimi_extract(texts)
        
        if result:
            for p in result.get('projects', []):
                if isinstance(p, str) and p.lower() not in GENERIC_SKIP and len(p) > 2:
                    all_projects[p] += 1
            for p in result.get('people', []):
                if isinstance(p, str) and p.lower() not in {'user', 'assistant', 'someone', 'a friend'}:
                    all_people[p] += 1
            for d in result.get('decisions', []):
                if isinstance(d, dict) and 'text' in d:
                    all_decisions.append(d)
                elif isinstance(d, str):
                    all_decisions.append({'text': d})
            for loc in result.get('locations', []):
                if isinstance(loc, str):
                    all_locations.add(loc)
            for rel in result.get('relationships', []):
                if isinstance(rel, dict):
                    all_relationships.append(rel)
            print(f"OK (p:{len(result.get('projects',[]))} ppl:{len(result.get('people',[]))} d:{len(result.get('decisions',[]))})")
        else:
            print("FAIL")
        
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n  Projects: {dict(all_projects.most_common(30))}")
    print(f"  People: {dict(all_people.most_common(20))}")
    print(f"  Decisions: {len(all_decisions)}")
    print(f"  Locations: {all_locations}")
    print(f"  Relationships: {len(all_relationships)}")
    
    # Pass 3: Merge into graph
    print(f"\nPASS 3: Merging into graph...")
    graph = EntityGraph(str(GRAPH_DB))
    
    stats = {'new_nodes': 0, 'updated_nodes': 0, 'new_edges': 0}
    
    # Helper
    def ensure_node(type_, name, metadata=None, importance=0.5):
        existing = graph.find_node(type_, name)
        if existing:
            stats['updated_nodes'] += 1
            graph.touch_node(existing.id)
            if metadata:
                graph.update_node(existing.id, metadata=metadata)
            return existing.id
        else:
            nid = graph.add_node(type_, name, metadata=metadata, importance=importance)
            stats['new_nodes'] += 1
            print(f"  NEW [{type_}] {name}")
            return nid
    
    # Add projects (min 2 mentions)
    for proj, count in all_projects.most_common():
        if count >= 2:
            ensure_node('project', proj, {'mention_count': count, 'source': 'chat_export'}, 0.7)
    
    # Add people (min 2 mentions or known)
    known_people = {'Matt', 'Henry', 'Alex Finn', 'Ethan Lipnik', 'Boris Cherny'}
    for person, count in all_people.most_common():
        if count >= 2 or person in known_people:
            ensure_node('person', person, {'mention_count': count, 'source': 'chat_export'}, 0.6)
    
    # Add locations
    for loc in all_locations:
        if len(loc) > 2 and loc.lower() not in {'here', 'there', 'online'}:
            ensure_node('location', loc, {'source': 'chat_export'}, 0.4)
    
    # Add quality decisions (filter aggressively)
    existing_decisions = set()
    conn = sqlite3.connect(str(GRAPH_DB))
    for row in conn.execute("SELECT name FROM nodes WHERE type='decision'").fetchall():
        existing_decisions.add(row[0].lower())
    conn.close()
    
    for dec in all_decisions:
        text = dec.get('text', '').strip()
        if len(text) < 15 or len(text) > 150:
            continue
        if text.lower() in existing_decisions:
            continue
        # Must sound like a real decision
        if not any(kw in text.lower() for kw in ['use', 'switch', 'chose', 'pick', 'go with', 'deploy',
                                                    'build', 'implement', 'create', 'move', 'adopt',
                                                    'launch', 'pivot', 'start', 'stop', 'replace']):
            continue
        ensure_node('decision', text, {'date': dec.get('date', ''), 'source': 'chat_export'}, 0.5)
        existing_decisions.add(text.lower())
    
    # Add relationships as edges
    for rel in all_relationships:
        from_name = rel.get('from', '')
        to_name = rel.get('to', '')
        relation = rel.get('relation', 'related_to')
        
        if not from_name or not to_name:
            continue
        
        # Try to find nodes
        from_node = None
        to_node = None
        for type_ in ['person', 'project', 'tool', 'concept']:
            if not from_node:
                from_node = graph.find_node(type_, from_name)
            if not to_node:
                to_node = graph.find_node(type_, to_name)
        
        if from_node and to_node:
            # Normalize relation
            rel_map = {
                'created': 'created', 'built': 'created', 'made': 'created',
                'works_on': 'works_on', 'working on': 'works_on',
                'uses': 'uses', 'used': 'uses',
                'related': 'related_to',
            }
            norm_rel = rel_map.get(relation.lower(), 'related_to')
            graph.add_edge(from_node.id, to_node.id, norm_rel, evidence='chat_export')
            stats['new_edges'] += 1
    
    print(f"\nRESULTS:")
    print(f"  New nodes: {stats['new_nodes']}")
    print(f"  Updated nodes: {stats['updated_nodes']}")
    print(f"  New edges: {stats['new_edges']}")
    
    final = graph.get_stats()
    print(f"\nFinal graph: {final['nodes']} nodes, {final['edges']} edges")
    print(f"Node types: {final['node_types']}")


if __name__ == "__main__":
    main()
