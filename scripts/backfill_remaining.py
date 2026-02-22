#!/usr/bin/env python3
"""Backfill remaining files: Feb 16 and Feb 17."""
import asyncio, json, os, sqlite3, sys, uuid
from datetime import datetime, timezone
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, '/workspace/clawd')
from brain.cheap_extractor import CheapExtractor

DB_PATH = '/workspace/clawd/brain/graph.db'
DATES = ['2026-02-16', '2026-02-17']
IMPORTANCE = {'person': 0.8, 'project': 0.8, 'tool': 0.7, 'decision': 0.7, 'concept': 0.6, 'fact': 0.6}

def normalize_type(cat):
    m = {'people':'person','person':'person','projects':'project','project':'project',
         'tools':'tool','tool':'tool','decisions':'decision','decision':'decision',
         'facts':'concept','fact':'concept','concepts':'concept','concept':'concept'}
    return m.get(cat.lower(), 'concept')

def chunk_text(text, size=4000):
    if len(text) <= size: return [text]
    chunks = []
    while text:
        if len(text) <= size: chunks.append(text); break
        b = text.rfind('\n\n', 0, size)
        if b < size//2: b = text.rfind('\n', 0, size)
        if b < size//2: b = size
        chunks.append(text[:b]); text = text[b:].lstrip()
    return chunks

def extract_entities(result):
    entities = []
    sources = {}
    if 'key_entities' in result and isinstance(result['key_entities'], dict):
        sources.update(result['key_entities'])
    for key in ['people','projects','tools','decisions','facts','concepts']:
        if key in result and isinstance(result[key], list):
            sources[key] = result[key]
    for cat, items in sources.items():
        ntype = normalize_type(cat)
        if not isinstance(items, list): continue
        for item in items:
            if isinstance(item, str) and len(item.strip()) >= 2:
                entities.append((item.strip(), ntype))
            elif isinstance(item, dict):
                name = item.get('name','') or item.get('entity','')
                if isinstance(name, str) and len(name.strip()) >= 2:
                    entities.append((name.strip(), ntype))
    return entities

async def main():
    extractor = CheapExtractor()
    conn = sqlite3.connect(DB_PATH)
    
    # Load existing nodes
    existing = {}
    for r in conn.execute("SELECT id, name, type FROM nodes").fetchall():
        existing[(r[1].lower().strip(), r[2].lower().strip())] = r[0]
    print(f"Existing nodes: {len(existing)}")
    
    now = datetime.now(timezone.utc).isoformat()
    total_new_nodes = 0
    total_new_edges = 0
    
    for date in DATES:
        filepath = f'/workspace/clawd/memory/{date}.md'
        filename = f'{date}.md'
        if not os.path.exists(filepath):
            print(f"Skip {filename}"); continue
        
        print(f"\nProcessing {filename}")
        with open(filepath) as f: text = f.read()
        chunks = chunk_text(text)
        print(f"  {len(text)} chars, {len(chunks)} chunks")
        
        all_ents = []
        for i, chunk in enumerate(chunks):
            try:
                print(f"  Chunk {i+1}/{len(chunks)}...", end=' ')
                result = await extractor.extract(chunk)
                if result.get('_success'):
                    ents = extract_entities(result)
                    print(f"{len(ents)} entities")
                    all_ents.extend(ents)
                else:
                    print("failed")
            except Exception as e:
                print(f"error: {e}")
            if i < len(chunks)-1: await asyncio.sleep(0.5)
        
        # Dedup
        seen = set()
        unique = []
        for name, etype in all_ents:
            key = (name.lower().strip(), etype)
            if key not in seen: seen.add(key); unique.append((name, etype))
        
        print(f"  {len(all_ents)} total, {len(unique)} unique")
        
        # Insert nodes
        cur = conn.cursor()
        node_ids = []
        file_new = 0
        for name, etype in unique:
            dk = (name.lower().strip(), etype.lower().strip())
            if dk in existing:
                node_ids.append(existing[dk]); continue
            nid = uuid.uuid4().hex[:8]
            meta = json.dumps({'source': filename, 'extracted_at': now, 'backfill': True})
            imp = IMPORTANCE.get(etype, 0.6)
            cur.execute("INSERT INTO nodes (id,type,name,metadata,importance,access_count,last_accessed,created_at,decay_score) VALUES (?,?,?,?,?,1,?,?,1.0)",
                       (nid, etype, name, meta, imp, now, now))
            existing[dk] = nid
            node_ids.append(nid)
            file_new += 1
        conn.commit()
        total_new_nodes += file_new
        
        # Insert edges
        edges = 0
        for i in range(len(node_ids)):
            for j in range(i+1, min(len(node_ids), i+20)):
                if node_ids[i] == node_ids[j]: continue
                if cur.execute("SELECT 1 FROM edges WHERE (source_id=? AND target_id=?) OR (source_id=? AND target_id=?)",
                              (node_ids[i],node_ids[j],node_ids[j],node_ids[i])).fetchone(): continue
                eid = uuid.uuid4().hex[:8]
                cur.execute("INSERT INTO edges (id,source_id,target_id,relation,weight,evidence,created_at) VALUES (?,?,?,'related_to',0.5,?,?)",
                           (eid, node_ids[i], node_ids[j], filename, now))
                edges += 1
        conn.commit()
        total_new_edges += edges
        print(f"  Added {file_new} nodes, {edges} edges")
    
    fn = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    fe = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"DONE: +{total_new_nodes} nodes, +{total_new_edges} edges")
    print(f"Total graph: {fn} nodes, {fe} edges")

asyncio.run(main())
