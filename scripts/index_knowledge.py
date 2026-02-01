#!/usr/bin/env python3
"""
Knowledge Library Indexer for ATLAS
Indexes markdown files into LanceDB with semantic embeddings.
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
import lancedb
from sentence_transformers import SentenceTransformer

# Config
KNOWLEDGE_DIR = Path("/workspace/clawd/knowledge")
MEMORY_DIR = Path("/workspace/clawd/memory")
DB_PATH = Path("/workspace/clawd/data/vector_db")
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, good quality, 384 dims

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def get_file_hash(path: Path) -> str:
    """Get hash of file contents for change detection."""
    return hashlib.md5(path.read_bytes()).hexdigest()

def index_directory(db, model, base_dir: Path, category: str):
    """Index all markdown files in a directory."""
    records = []
    
    for md_file in base_dir.rglob("*.md"):
        rel_path = md_file.relative_to(base_dir.parent)
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        file_hash = get_file_hash(md_file)
        
        # Chunk the content
        chunks = chunk_text(content)
        
        for i, chunk in enumerate(chunks):
            embedding = model.encode(chunk).tolist()
            records.append({
                "id": f"{rel_path}:{i}",
                "path": str(rel_path),
                "category": category,
                "chunk_index": i,
                "text": chunk,
                "file_hash": file_hash,
                "indexed_at": datetime.utcnow().isoformat(),
                "vector": embedding
            })
    
    return records

def main():
    print("🌐 ATLAS Knowledge Indexer")
    print("=" * 40)
    
    # Initialize model
    print(f"Loading embedding model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    # Initialize LanceDB
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(DB_PATH))
    
    all_records = []
    
    # Index knowledge library
    if KNOWLEDGE_DIR.exists():
        for subdir in KNOWLEDGE_DIR.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("."):
                print(f"Indexing {subdir.name}...")
                records = index_directory(db, model, subdir, subdir.name)
                all_records.extend(records)
                print(f"  → {len(records)} chunks")
    
    # Index memory files
    if MEMORY_DIR.exists():
        print("Indexing memory/...")
        records = index_directory(db, model, MEMORY_DIR, "memory")
        all_records.extend(records)
        print(f"  → {len(records)} chunks")
    
    # Create/overwrite table
    if all_records:
        print(f"\nWriting {len(all_records)} total chunks to LanceDB...")
        
        # Drop existing table if it exists
        try:
            db.drop_table("knowledge")
        except:
            pass
        
        table = db.create_table("knowledge", all_records)
        print(f"✓ Indexed into table 'knowledge'")
    else:
        print("No content found to index.")
    
    print("\n✅ Indexing complete!")

if __name__ == "__main__":
    main()
