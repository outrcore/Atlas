"""
Semantic Linker - Connects memories using embeddings and LanceDB.
"""
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

try:
    import lancedb
    import pyarrow as pa
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False

# Simple embedding using basic text features (fallback if no ML model)
# This is a placeholder - in production, use sentence-transformers
def simple_hash_embedding(text: str, dim: int = 128) -> List[float]:
    """
    Create a simple hash-based embedding.
    NOT semantically meaningful, but allows the system to work without ML deps.
    """
    import hashlib
    
    # Normalize text
    text = text.lower().strip()
    
    # Create multiple hashes for different "dimensions"
    embedding = []
    for i in range(dim):
        h = hashlib.md5(f"{text}_{i}".encode()).hexdigest()
        # Convert to float between -1 and 1
        val = (int(h[:8], 16) / (2**32)) * 2 - 1
        embedding.append(val)
        
    return embedding


class SemanticLinker:
    """
    Manages semantic memory storage and retrieval using LanceDB.
    
    Uses embeddings to find related memories and create links.
    """
    
    def __init__(
        self,
        db_path: Path,
        embedding_dim: int = 384,
    ):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        
        self.db = None
        self.table = None
        self._initialized = False
        
        # Try to load sentence-transformers
        self.encoder = None
        self._load_encoder()
        
    def _load_encoder(self):
        """Try to load sentence-transformers for real embeddings."""
        try:
            # Try importing - may fail due to version conflicts
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
            self.embedding_dim = 384  # MiniLM dimension
            print("🧠 Using sentence-transformers for embeddings")
        except Exception as e:
            print(f"⚠️ Using fallback hash embeddings: {e}")
            self.encoder = None
            
    def _embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if self.encoder:
            return self.encoder.encode(text).tolist()
        else:
            return simple_hash_embedding(text, self.embedding_dim)
            
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if self.encoder:
            return self.encoder.encode(texts).tolist()
        else:
            return [simple_hash_embedding(t, self.embedding_dim) for t in texts]
            
    async def initialize(self):
        """Initialize the LanceDB connection and table."""
        if not HAS_LANCEDB:
            raise ImportError("LanceDB not installed")
            
        self.db = lancedb.connect(str(self.db_path))
        
        # Check if table exists
        existing_tables = self.db.table_names()
        
        if "memories" in existing_tables:
            self.table = self.db.open_table("memories")
        else:
            # Create schema
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("content", pa.string()),
                pa.field("category", pa.string()),
                pa.field("metadata", pa.string()),  # JSON string
                pa.field("created_at", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.embedding_dim)),
            ])
            
            # Create empty table
            self.table = self.db.create_table(
                "memories",
                schema=schema,
            )
            
        self._initialized = True
        
    async def add_and_link(
        self,
        content: str,
        category: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add content to memory and automatically find/create links.
        
        Args:
            content: The content to store
            category: Dewey Decimal category
            metadata: Optional additional data
            
        Returns:
            Memory ID
        """
        if not self._initialized:
            await self.initialize()
            
        memory_id = str(uuid.uuid4())[:12]
        embedding = self._embed(content)
        
        # Find related memories before adding
        related = await self.search(content, limit=5)
        
        # Add related IDs to metadata
        meta = metadata or {}
        meta["related_ids"] = [r["id"] for r in related if r["score"] > 0.7]
        
        # Insert into table
        self.table.add([{
            "id": memory_id,
            "content": content,
            "category": category,
            "metadata": json.dumps(meta),
            "created_at": datetime.now().isoformat(),
            "vector": embedding,
        }])
        
        return memory_id
        
    async def search(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search for related memories.
        
        Args:
            query: Search query
            limit: Max results
            category: Optional category filter
            
        Returns:
            List of memories with similarity scores
        """
        if not self._initialized:
            await self.initialize()
            
        query_embedding = self._embed(query)
        
        # Build search
        search = self.table.search(query_embedding).limit(limit)
        
        # Execute search
        results = search.to_list()
        
        # Format results
        memories = []
        for r in results:
            # Filter by category if specified
            if category and r.get("category") != category:
                continue
                
            memories.append({
                "id": r["id"],
                "content": r["content"],
                "category": r["category"],
                "metadata": json.loads(r.get("metadata", "{}")),
                "created_at": r["created_at"],
                "score": 1 - r.get("_distance", 0),  # Convert distance to similarity
            })
            
        return memories
        
    async def get_by_id(self, memory_id: str) -> Optional[Dict]:
        """Get a specific memory by ID."""
        if not self._initialized:
            await self.initialize()
            
        # Search for exact ID match
        results = self.table.search().where(f"id = '{memory_id}'").limit(1).to_list()
        
        if results:
            r = results[0]
            return {
                "id": r["id"],
                "content": r["content"],
                "category": r["category"],
                "metadata": json.loads(r.get("metadata", "{}")),
                "created_at": r["created_at"],
            }
        return None
        
    async def get_by_category(
        self,
        category: str,
        limit: int = 50,
    ) -> List[Dict]:
        """Get all memories in a category."""
        if not self._initialized:
            await self.initialize()
            
        results = self.table.search().where(f"category = '{category}'").limit(limit).to_list()
        
        return [{
            "id": r["id"],
            "content": r["content"],
            "category": r["category"],
            "metadata": json.loads(r.get("metadata", "{}")),
            "created_at": r["created_at"],
        } for r in results]
        
    async def update_clusters(self):
        """
        Cluster related memories and update their links.
        (Simplified version - real clustering would use more sophisticated methods)
        """
        # For now, just re-compute links for recent memories
        # Could implement K-means or HDBSCAN clustering here
        pass
        
    def count(self) -> int:
        """Get total memory count."""
        if not self._initialized or not self.table:
            return 0
        return self.table.count_rows()
        
    async def delete(self, memory_id: str):
        """Delete a memory."""
        if not self._initialized:
            await self.initialize()
        self.table.delete(f"id = '{memory_id}'")
