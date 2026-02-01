#!/usr/bin/env python3
"""
Knowledge Search for ATLAS
Semantic search across the knowledge library.
"""

import sys
from pathlib import Path
import lancedb
from sentence_transformers import SentenceTransformer

DB_PATH = Path("/workspace/clawd/data/vector_db")
MODEL_NAME = "all-MiniLM-L6-v2"

def search(query: str, limit: int = 5, category: str = None):
    """Search knowledge base with semantic similarity."""
    
    # Load model and DB
    model = SentenceTransformer(MODEL_NAME)
    db = lancedb.connect(str(DB_PATH))
    
    try:
        table = db.open_table("knowledge")
    except Exception as e:
        print(f"Error: Knowledge base not indexed yet. Run index_knowledge.py first.")
        return []
    
    # Encode query
    query_embedding = model.encode(query).tolist()
    
    # Search
    results = table.search(query_embedding).limit(limit)
    
    if category:
        results = results.where(f"category = '{category}'")
    
    results = results.to_pandas()
    
    return results

def main():
    if len(sys.argv) < 2:
        print("Usage: search_knowledge.py <query> [limit] [category]")
        sys.exit(1)
    
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    category = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"🔍 Searching: '{query}'")
    print("=" * 40)
    
    results = search(query, limit, category)
    
    if results.empty:
        print("No results found.")
        return
    
    for i, row in results.iterrows():
        print(f"\n📄 {row['path']} (chunk {row['chunk_index']})")
        print(f"   Category: {row['category']}")
        print(f"   Score: {row['_distance']:.4f}")
        print(f"   Preview: {row['text'][:200]}...")

if __name__ == "__main__":
    main()
