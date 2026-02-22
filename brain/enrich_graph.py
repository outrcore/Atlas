#!/usr/bin/env python3
"""
Graph enrichment from chat export chunks.
Pass 1: Fast triage via regex/keywords
Pass 2: Cheap extractor (Kimi) for high-value chunks  
Pass 3: Merge into graph with dedup
"""

import os
import re
import json
import glob
import sqlite3
import asyncio
from pathlib import Path
from collections import Counter

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from graph import EntityGraph

CHUNKS_DIR = Path("/workspace/clawd/knowledge/700-chat-exports/chunks")
GRAPH_DB = Path(__file__).parent / "graph.db"

# Keywords that indicate high-value chunks
HIGH_VALUE_KEYWORDS = [
    # Project names (known)
    r'\bproject_alpha\b', r'\bproject_beta?\b', r'\bbotbets?\b', r'\batlas\b', r'\bpersonaplex\b',
    r'\bproject_a\b', r'\bproject_b\b', r'\bmemu\b', r'\byour_project\b', r'\bbotgames\b',
    r'\bopenClaw\b', r'\bopenclaw\b',
    # Decision indicators
    r'\bdecided\b', r'\bwe.?ll go with\b', r'\blet.?s use\b', r'\bswitching to\b',
    r'\binstead of\b', r'\bpivot\b', r'\bstrategy\b',
    # Business/architecture
    r'\bmonetiz\b', r'\brevenue\b', r'\bbusiness model\b', r'\barchitecture\b',
    r'\binfrastructure\b', r'\bdeploy\b', r'\bproduction\b', r'\blaunch\b',
    # People names
    r'\bmatt\b', r'\balex\b', r'\bhenry\b', r'\bethan\b', r'\bboris\b',
    # Specific tech decisions
    r'\bsolana\b', r'\bbase blockchain\b', r'\bsupabase\b', r'\bvercel\b',
    r'\brunpod\b', r'\bdigitalocean\b',
]

# Low-value patterns to skip
LOW_VALUE_PATTERNS = [
    r'^(explain|what is|how do|can you|help me understand)',
    r'(syntax error|undefined|typeerror|referenceerror)',
    r'(tutorial|example code|boilerplate)',
]

GENERIC_TOOLS = {
    'javascript', 'python', 'html', 'css', 'typescript', 'react', 'node.js',
    'git', 'npm', 'api', 'json', 'sql', 'bash', 'linux', 'docker',
    'debugging', 'testing', 'deployment', 'database', 'server', 'client',
    'frontend', 'backend', 'web', 'mobile', 'app',
}


def read_chunk_header(path, max_chars=800):
    """Read frontmatter + first ~500 chars of content."""
    try:
        with open(path, 'r', errors='replace') as f:
            text = f.read(max_chars)
        return text
    except:
        return ""


def score_chunk(text):
    """Score a chunk for value. Higher = more valuable."""
    score = 0
    text_lower = text.lower()
    
    # Check high-value keywords
    for pattern in HIGH_VALUE_KEYWORDS:
        if re.search(pattern, text_lower):
            score += 2
    
    # Check low-value patterns in first USER message
    user_match = re.search(r'\[USER\]:\s*(.+?)(?:\n|$)', text)
    if user_match:
        user_msg = user_match.group(1).lower()
        for pattern in LOW_VALUE_PATTERNS:
            if re.search(pattern, user_msg):
                score -= 3
    
    # Category bonuses
    if 'category: trading' in text_lower or 'category: business' in text_lower:
        score += 1
    if 'category: coding' in text_lower:
        score += 0  # neutral, need keywords
    
    # Has specific project/product discussion
    if re.search(r'\b(build|create|design|implement|deploy|launch)\b.*\b(app|platform|system|tool|bot)\b', text_lower):
        score += 1
    
    # Has decision language
    if re.search(r'\b(decided|chose|picked|selected|went with|opted for)\b', text_lower):
        score += 2
    
    # Has named people beyond just "user"/"assistant"
    if re.search(r'\b[A-Z][a-z]+\b.*\b(said|told|asked|mentioned|wants|suggested)\b', text):
        score += 1
    
    return score


def extract_frontmatter(text):
    """Extract YAML frontmatter."""
    match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            fm[key.strip()] = val.strip()
    return fm


def extract_entities_regex(text):
    """Fast regex-based entity extraction."""
    entities = {
        'people': set(),
        'projects': set(),
        'decisions': [],
        'tools': set(),
    }
    
    text_lower = text.lower()
    
    # Known project names
    project_patterns = {
        'ProjectAlpha': r'\bproject_alpha\b',
        'ProjectBeta': r'\bproject_beta?\b',
        'BotBets': r'\bbotbets?\b',
        'ATLAS': r'\batlas\b',
        'PersonaPlex': r'\bpersonaplex\b',
        'ProjectGamma': r'\bproject_gamma\b',
        'YourProject': r'\byourproject\b',
        'memU': r'\bmemu\b',
        'YourProject': r'\byour_project\b',
        'BotGames': r'\bbotgames\b',
        'OpenClaw': r'\bopenclaw\b',
        'Brain v2': r'\bbrain v2\b',
        'Voice Stack': r'\bvoice stack\b',
    }
    for name, pat in project_patterns.items():
        if re.search(pat, text_lower):
            entities['projects'].add(name)
    
    # People - look for capitalized names near action verbs
    people_patterns = {
        # 'YourName': r'\bmatt\b',
        'Alex Finn': r'\balex\s*finn\b',
        'Henry': r'\bhenry\b',
        'Ethan Lipnik': r'\bethan\s*lipnik\b',
        'Boris Cherny': r'\bboris\s*cherny\b',
    }
    for name, pat in people_patterns.items():
        if re.search(pat, text_lower):
            entities['people'].add(name)
    
    # New people - capitalized words near "I", "my friend", etc.
    new_people = re.findall(r'\b(?:my (?:friend|brother|partner|colleague|cofounder|co-founder)|(?:talk(?:ed|ing) (?:to|with)))\s+([A-Z][a-z]+)\b', text)
    for p in new_people:
        if p not in {'The', 'This', 'That', 'What', 'How', 'When', 'Where', 'Some', 'Any'}:
            entities['people'].add(p)
    
    # Decisions
    decision_patterns = [
        r'(?:decided|chose|going) to\s+(.{20,80}?)(?:\.|$)',
        r'(?:we.?ll|let.?s|going to)\s+(?:use|go with|switch to)\s+(.{10,60}?)(?:\.|$)',
        r'(?:switched|migrated|moved) (?:from|to)\s+(.{10,60}?)(?:\.|$)',
    ]
    for pat in decision_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            dec = m.group(1).strip()
            if len(dec) > 10:
                entities['decisions'].append(dec)
    
    # New project names - "building/creating [Name]" or "[Name] app/platform"
    new_projects = re.findall(r'(?:building|creating|launching|working on)\s+(?:a\s+)?(?:new\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b', text)
    for p in new_projects:
        if p.lower() not in GENERIC_TOOLS and len(p) > 2:
            entities['projects'].add(p)
    
    return entities


def pass1_triage():
    """First pass: score all chunks, return high-value ones."""
    chunks = sorted(glob.glob(str(CHUNKS_DIR / "chunk_*.md")))
    print(f"Total chunks: {len(chunks)}")
    
    scored = []
    for path in chunks:
        header = read_chunk_header(path)
        score = score_chunk(header)
        if score >= 2:
            scored.append((path, score, header))
    
    # Sort by score descending
    scored.sort(key=lambda x: -x[1])
    print(f"High-value chunks (score >= 2): {len(scored)}")
    
    # Take top 400
    return scored[:400]


def pass2_extract(high_value_chunks):
    """Second pass: extract entities from high-value chunks using regex."""
    all_entities = {
        'people': Counter(),
        'projects': Counter(),
        'decisions': [],
        'chunk_entities': [],  # (chunk_path, frontmatter, entities)
    }
    
    for path, score, header in high_value_chunks:
        # Read full chunk for extraction
        try:
            with open(path, 'r', errors='replace') as f:
                full_text = f.read()
        except:
            continue
        
        fm = extract_frontmatter(full_text)
        entities = extract_entities_regex(full_text)
        
        for p in entities['people']:
            all_entities['people'][p] += 1
        for p in entities['projects']:
            all_entities['projects'][p] += 1
        for d in entities['decisions']:
            all_entities['decisions'].append({'text': d, 'date': fm.get('date', ''), 'source': Path(path).name})
        
        if any(entities[k] for k in ['people', 'projects', 'decisions']):
            all_entities['chunk_entities'].append((path, fm, entities))
    
    return all_entities


def pass3_merge(all_entities):
    """Third pass: merge into graph with dedup."""
    graph = EntityGraph(str(GRAPH_DB))
    stats = {'new_nodes': 0, 'updated_nodes': 0, 'new_edges': 0, 'skipped': 0}
    
    # Get existing nodes for dedup
    conn = sqlite3.connect(str(GRAPH_DB))
    existing_names = {}
    for row in conn.execute("SELECT id, type, name FROM nodes").fetchall():
        existing_names[(row[1], row[2].lower())] = row[0]
    conn.close()
    
    def find_existing(type_, name):
        """Find existing node by type+name (case-insensitive)."""
        return existing_names.get((type_, name.lower()))
    
    def ensure_node(type_, name, metadata=None, importance=0.5):
        """Add node if new, return id."""
        existing_id = find_existing(type_, name)
        if existing_id:
            stats['updated_nodes'] += 1
            # Touch the node
            graph.touch_node(existing_id)
            if metadata:
                graph.update_node(existing_id, metadata=metadata)
            return existing_id
        else:
            nid = graph.add_node(type_, name, metadata=metadata, importance=importance)
            existing_names[(type_, name.lower())] = nid
            stats['new_nodes'] += 1
            print(f"  NEW [{type_}] {name}")
            return nid
    
    # Add people
    for person, count in all_entities['people'].most_common():
        if count < 2 and person not in {'User', 'Alex Finn', 'Henry'}:
            continue  # Skip one-off mentions
        ensure_node('person', person, {'mention_count': count}, importance=0.6)
    
    # Add projects
    for project, count in all_entities['projects'].most_common():
        if count < 2:
            continue
        ensure_node('project', project, {'mention_count': count}, importance=0.7)
    
    # Add decisions (only unique, consequential ones)
    seen_decisions = set()
    conn2 = sqlite3.connect(str(GRAPH_DB))
    existing_decisions = set(
        row[0].lower() for row in conn2.execute("SELECT name FROM nodes WHERE type='decision'").fetchall()
    )
    conn2.close()
    
    for dec in all_entities['decisions']:
        text = dec['text'].strip()
        # Skip if too generic or already exists
        text_lower = text.lower()
        if text_lower in seen_decisions:
            continue
        if any(text_lower.startswith(g) for g in ['use ', 'add ', 'fix ', 'update ', 'make ']):
            # Too generic unless it's specific
            if len(text) < 30:
                continue
        # Check similarity to existing
        skip = False
        for ed in existing_decisions:
            if text_lower in ed or ed in text_lower:
                skip = True
                break
        if skip:
            stats['skipped'] += 1
            continue
        
        seen_decisions.add(text_lower)
        nid = ensure_node('decision', text, {'date': dec['date'], 'source': dec['source']}, importance=0.5)
    
    # Add edges from chunk_entities
    for path, fm, entities in all_entities['chunk_entities']:
        date = fm.get('date', '')
        
        # Link people to projects mentioned in same chunk
        people_ids = []
        project_ids = []
        for p in entities['people']:
            pid = find_existing('person', p)
            if pid:
                people_ids.append(pid)
        for p in entities['projects']:
            pid = find_existing('project', p)
            if pid:
                project_ids.append(pid)
        
        for person_id in people_ids:
            for proj_id in project_ids:
                eid = graph.add_edge(person_id, proj_id, 'works_on', evidence=f"co-mentioned in {Path(path).name}")
                stats['new_edges'] += 1
    
    return stats


def main():
    print("=" * 60)
    print("PASS 1: Triaging chunks for value...")
    print("=" * 60)
    high_value = pass1_triage()
    
    print(f"\nTop 10 chunks by score:")
    for path, score, _ in high_value[:10]:
        fm = extract_frontmatter(_)
        print(f"  [{score}] {Path(path).name}: {fm.get('title', '?')[:60]}")
    
    print("\n" + "=" * 60)
    print("PASS 2: Extracting entities...")
    print("=" * 60)
    all_entities = pass2_extract(high_value)
    
    print(f"\nPeople found: {dict(all_entities['people'].most_common(20))}")
    print(f"Projects found: {dict(all_entities['projects'].most_common(20))}")
    print(f"Decisions found: {len(all_entities['decisions'])}")
    
    print("\n" + "=" * 60)
    print("PASS 3: Merging into graph...")
    print("=" * 60)
    stats = pass3_merge(all_entities)
    
    print(f"\n{'=' * 60}")
    print(f"RESULTS:")
    print(f"  New nodes added: {stats['new_nodes']}")
    print(f"  Existing nodes updated: {stats['updated_nodes']}")
    print(f"  New edges added: {stats['new_edges']}")
    print(f"  Decisions skipped (dups): {stats['skipped']}")
    
    # Final graph stats
    graph = EntityGraph(str(GRAPH_DB))
    final = graph.get_stats()
    print(f"\nFinal graph: {final['nodes']} nodes, {final['edges']} edges")
    print(f"Node types: {final['node_types']}")


if __name__ == "__main__":
    main()
