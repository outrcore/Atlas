#!/usr/bin/env python3
"""
Backfill graph entities from Feb 9-17 daily logs.
Processes each file through CheapExtractor and inserts into graph.db.
"""

import asyncio
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

sys.path.insert(0, '/workspace/clawd')
from brain.cheap_extractor import CheapExtractor

DB_PATH = '/workspace/clawd/brain/graph.db'
MEMORY_DIR = '/workspace/clawd/memory'
CHUNK_SIZE = 4000  # Max chars per extraction call

# Dates to process
DATES = [
    '2026-02-09', '2026-02-10', '2026-02-11', '2026-02-12',
    '2026-02-13', '2026-02-14', '2026-02-15', '2026-02-16', '2026-02-17'
]

# Importance by type
IMPORTANCE = {
    'person': 0.8,
    'project': 0.8,
    'tool': 0.7,
    'decision': 0.7,
    'concept': 0.6,
    'fact': 0.6,
}


MAX_CHUNKS = 8  # Max chunks per file to avoid excessive API calls

def chunk_text(text, size=CHUNK_SIZE):
    """Split text into chunks, trying to break at paragraph/section boundaries.
    For very large files, sample strategically rather than processing everything."""
    if len(text) <= size:
        return [text]
    
    # Split into all chunks first
    all_chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= size:
            all_chunks.append(remaining)
            break
        break_at = remaining.rfind('\n\n', 0, size)
        if break_at < size // 2:
            break_at = remaining.rfind('\n', 0, size)
        if break_at < size // 2:
            break_at = size
        all_chunks.append(remaining[:break_at])
        remaining = remaining[break_at:].lstrip()
    
    # If under limit, return all
    if len(all_chunks) <= MAX_CHUNKS:
        return all_chunks
    
    # Sample strategically: first 3, last 2, and evenly spaced middle ones
    n = len(all_chunks)
    indices = set()
    # First 3 chunks (usually contain summaries/headers)
    for i in range(min(3, n)):
        indices.add(i)
    # Last 2 chunks
    for i in range(max(0, n-2), n):
        indices.add(i)
    # Fill remaining from middle, evenly spaced
    remaining_slots = MAX_CHUNKS - len(indices)
    if remaining_slots > 0:
        middle_start = 3
        middle_end = n - 2
        if middle_end > middle_start:
            step = max(1, (middle_end - middle_start) // (remaining_slots + 1))
            for i in range(middle_start, middle_end, step):
                indices.add(i)
                if len(indices) >= MAX_CHUNKS:
                    break
    
    sampled = sorted(indices)[:MAX_CHUNKS]
    print(f"  Sampled {len(sampled)} of {n} chunks: indices {sampled}")
    return [all_chunks[i] for i in sampled]


def get_existing_nodes(conn):
    """Load existing nodes for dedup (case-insensitive)."""
    cur = conn.cursor()
    cur.execute("SELECT id, name, type FROM nodes")
    existing = {}
    for row in cur.fetchall():
        key = (row[1].lower().strip(), row[2].lower().strip())
        existing[key] = row[0]
    return existing


def normalize_type(category):
    """Map extraction categories to node types."""
    mapping = {
        'people': 'person',
        'person': 'person',
        'projects': 'project',
        'project': 'project',
        'tools': 'tool',
        'tool': 'tool',
        'decisions': 'decision',
        'decision': 'decision',
        'facts': 'concept',
        'fact': 'concept',
        'concepts': 'concept',
        'concept': 'concept',
    }
    return mapping.get(category.lower(), 'concept')


def extract_entities_from_result(result):
    """Parse extractor result into a flat list of (name, type) tuples."""
    entities = []
    
    # Handle both flat and nested formats
    # Flat: {"people": [...], "projects": [...], ...}
    # Nested: {"key_entities": {"people": [...], ...}, "facts": [...], ...}
    
    sources = {}
    
    # Check for key_entities wrapper
    if 'key_entities' in result and isinstance(result['key_entities'], dict):
        sources.update(result['key_entities'])
    
    # Also check top-level keys
    for key in ['people', 'projects', 'tools', 'decisions', 'facts', 'concepts']:
        if key in result and isinstance(result[key], list):
            sources[key] = result[key]
    
    for category, items in sources.items():
        node_type = normalize_type(category)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str) and item.strip():
                name = item.strip()
                # Skip very short or generic entries
                if len(name) < 2:
                    continue
                entities.append((name, node_type))
            elif isinstance(item, dict):
                # Could be {"name": "...", ...} format
                name = item.get('name', '') or item.get('entity', '') or str(item)
                if isinstance(name, str) and name.strip() and len(name.strip()) >= 2:
                    entities.append((name.strip(), node_type))
    
    return entities


async def process_file(extractor, filepath, filename):
    """Process a single file through the extractor."""
    print(f"\n{'='*60}")
    print(f"Processing: {filename}")
    
    with open(filepath, 'r') as f:
        text = f.read()
    
    print(f"  File size: {len(text)} chars")
    chunks = chunk_text(text)
    print(f"  Chunks: {len(chunks)}")
    
    all_entities = []
    
    for i, chunk in enumerate(chunks):
        try:
            print(f"  Extracting chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
            result = await extractor.extract(chunk)
            
            if result.get('_success'):
                entities = extract_entities_from_result(result)
                print(f"    Found {len(entities)} entities")
                all_entities.extend(entities)
            else:
                print(f"    Extraction failed for chunk {i+1}")
        except Exception as e:
            print(f"    Error on chunk {i+1}: {e}")
            continue
        
        # Small delay between API calls to avoid rate limiting
        if i < len(chunks) - 1:
            await asyncio.sleep(0.5)
    
    print(f"  Total entities from {filename}: {len(all_entities)}")
    return all_entities


async def main():
    extractor = CheapExtractor()
    conn = sqlite3.connect(DB_PATH)
    
    # Get existing nodes for dedup
    existing_nodes = get_existing_nodes(conn)
    print(f"Existing nodes in graph: {len(existing_nodes)}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    files_processed = 0
    total_new_nodes = 0
    total_new_edges = 0
    
    for date in DATES:
        filename = f'{date}.md'
        filepath = os.path.join(MEMORY_DIR, filename)
        
        if not os.path.exists(filepath):
            print(f"\nSkipping {filename} (not found)")
            continue
        
        try:
            entities = await process_file(extractor, filepath, filename)
            files_processed += 1
            
            if not entities:
                print(f"  No entities extracted, skipping DB insert")
                continue
            
            # Deduplicate within this file's results
            seen = set()
            unique_entities = []
            for name, etype in entities:
                key = (name.lower().strip(), etype)
                if key not in seen:
                    seen.add(key)
                    unique_entities.append((name, etype))
            
            print(f"  Unique entities: {len(unique_entities)}")
            
            # Insert new nodes
            new_node_ids = []
            cur = conn.cursor()
            
            for name, etype in unique_entities:
                dedup_key = (name.lower().strip(), etype.lower().strip())
                
                if dedup_key in existing_nodes:
                    # Already exists, just record its ID for edges
                    new_node_ids.append(existing_nodes[dedup_key])
                    continue
                
                node_id = uuid.uuid4().hex[:8]
                importance = IMPORTANCE.get(etype, 0.6)
                metadata = json.dumps({
                    'source': filename,
                    'extracted_at': now,
                    'backfill': True
                })
                
                try:
                    cur.execute(
                        "INSERT INTO nodes (id, type, name, metadata, importance, access_count, last_accessed, created_at, decay_score) VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1.0)",
                        (node_id, etype, name, metadata, importance, now, now)
                    )
                    existing_nodes[dedup_key] = node_id
                    new_node_ids.append(node_id)
                    total_new_nodes += 1
                except sqlite3.IntegrityError:
                    # Node somehow already exists
                    pass
            
            # Commit nodes first
            conn.commit()
            
            # Create edges between entities from same file
            # Schema: id, source_id, target_id, relation, weight, evidence, created_at
            edges_added = 0
            for i in range(len(new_node_ids)):
                for j in range(i + 1, min(len(new_node_ids), i + 20)):  # Limit edge fan-out
                    if new_node_ids[i] == new_node_ids[j]:
                        continue
                    
                    # Check if edge already exists
                    cur.execute(
                        "SELECT id FROM edges WHERE (source_id = ? AND target_id = ?) OR (source_id = ? AND target_id = ?)",
                        (new_node_ids[i], new_node_ids[j], new_node_ids[j], new_node_ids[i])
                    )
                    if cur.fetchone():
                        continue
                    
                    edge_id = uuid.uuid4().hex[:8]
                    try:
                        cur.execute(
                            "INSERT INTO edges (id, source_id, target_id, relation, weight, evidence, created_at) VALUES (?, ?, ?, 'related_to', 0.5, ?, ?)",
                            (edge_id, new_node_ids[i], new_node_ids[j], filename, now)
                        )
                        edges_added += 1
                    except sqlite3.IntegrityError:
                        pass
            
            total_new_edges += edges_added
            conn.commit()
            print(f"  Inserted: {total_new_nodes} new nodes so far, {edges_added} new edges from this file")
            
        except Exception as e:
            print(f"\nERROR processing {filename}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Final summary
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM nodes")
    final_nodes = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM edges")
    final_edges = cur.fetchone()[0]
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"BACKFILL COMPLETE")
    print(f"{'='*60}")
    print(f"Files processed:  {files_processed}")
    print(f"New nodes added:  {total_new_nodes}")
    print(f"New edges added:  {total_new_edges}")
    print(f"Total graph size: {final_nodes} nodes, {final_edges} edges")
    print(f"{'='*60}")


if __name__ == '__main__':
    asyncio.run(main())
