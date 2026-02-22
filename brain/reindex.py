#!/usr/bin/env python3
"""Re-index all memory/knowledge into LanceDB with Nomic embeddings."""
import os, sys, time, hashlib, glob
from datetime import datetime, timezone

sys.path.insert(0, '/workspace/clawd')

WORKSPACE = '/workspace/clawd'
LANCEDB_PATH = f'{WORKSPACE}/brain/lancedb'
TABLE_NAME = 'memories'

SOURCES = {
    'files': [
        f'{WORKSPACE}/MEMORY.md',
        f'{WORKSPACE}/TOOLS.md',
        f'{WORKSPACE}/USER.md',
        f'{WORKSPACE}/SOUL.md',
    ],
    'dirs': [
        f'{WORKSPACE}/memory/',
        f'{WORKSPACE}/knowledge/',
    ]
}

SKIP_DIRS = {s.strip() for s in os.environ.get('KNOWLEDGE_SKIP_DIRS', '700-chat-exports').split(',') if s.strip()}

def collect_files():
    files = []
    for f in SOURCES['files']:
        if os.path.isfile(f):
            files.append(f)
    for d in SOURCES['dirs']:
        for root, dirs, fnames in os.walk(d):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            if any(skip in root for skip in SKIP_DIRS):
                continue
            for fn in fnames:
                if fn.endswith('.md'):
                    files.append(os.path.join(root, fn))
    return files

def chunk_file(path, max_words=500):
    with open(path, 'r', errors='replace') as f:
        text = f.read()
    if not text.strip():
        return []
    
    # Split by ## headers
    sections = []
    if '\n## ' in text or text.startswith('## '):
        parts = text.split('\n## ')
        for i, part in enumerate(parts):
            if i > 0:
                part = '## ' + part
            if part.strip():
                sections.append(part.strip())
    else:
        sections = [text.strip()]
    
    # Further split large sections
    chunks = []
    for section in sections:
        words = section.split()
        if len(words) <= max_words:
            chunks.append(section)
        else:
            for i in range(0, len(words), max_words):
                chunk = ' '.join(words[i:i+max_words])
                if chunk.strip():
                    chunks.append(chunk.strip())
    return chunks

def main():
    import lancedb
    import pyarrow as pa
    from brain.embedder import get_embedder

    start = time.time()
    
    print("Collecting files...")
    print(f"Skipping dirs: {sorted(SKIP_DIRS)}")
    files = collect_files()
    print(f"Found {len(files)} files")

    # Chunk all files
    all_chunks = []  # (content, source)
    for fp in files:
        rel = os.path.relpath(fp, WORKSPACE)
        chunks = chunk_file(fp)
        for c in chunks:
            all_chunks.append((c, rel))
    
    print(f"Created {len(all_chunks)} chunks")
    
    # Embed in batches
    embedder = get_embedder()
    batch_size = 32
    all_vectors = []
    
    for i in range(0, len(all_chunks), batch_size):
        batch_texts = [c[0] for c in all_chunks[i:i+batch_size]]
        vecs = embedder.embed_batch(batch_texts)
        all_vectors.extend(vecs)
        if (i // batch_size) % 10 == 0:
            print(f"  Embedded {min(i+batch_size, len(all_chunks))}/{len(all_chunks)} chunks...")
    
    print(f"Embedding complete in {time.time()-start:.1f}s")

    # Build records
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for idx, ((content, source), vec) in enumerate(zip(all_chunks, all_vectors)):
        rid = hashlib.md5(f"{source}:{idx}:{content[:100]}".encode()).hexdigest()
        records.append({
            "id": rid,
            "content": content,
            "source": source,
            "vector": vec.tolist(),
            "timestamp": now,
        })

    # Write to LanceDB
    os.makedirs(LANCEDB_PATH, exist_ok=True)
    db = lancedb.connect(LANCEDB_PATH)
    
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("content", pa.string()),
        pa.field("source", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 768)),
        pa.field("timestamp", pa.string()),
    ])
    
    # Drop existing table if present
    try:
        db.drop_table(TABLE_NAME)
    except:
        pass
    
    tbl = db.create_table(TABLE_NAME, data=records, schema=schema)
    
    elapsed = time.time() - start
    print(f"\n=== Reindex Complete ===")
    print(f"Files: {len(files)}")
    print(f"Chunks: {len(all_chunks)}")
    print(f"Rows in DB: {tbl.count_rows()}")
    print(f"Time: {elapsed:.1f}s")
    
    # Test search
    print(f"\n--- Test Search: 'BetBots fee structure' ---")
    q = embedder.embed("BetBots fee structure")
    results = tbl.search(q.tolist()).limit(5).to_list()
    for r in results:
        print(f"  {r['content'][:80]}  ({r['source']})")

if __name__ == '__main__':
    main()
