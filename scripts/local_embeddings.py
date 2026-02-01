#!/usr/bin/env python3
"""
Local Embeddings Client for memU

Uses sentence-transformers for local embedding generation,
avoiding the need for OpenAI API keys.
"""
from typing import List
import numpy as np


class LocalEmbeddingClient:
    """
    Custom embedding client using sentence-transformers.
    Compatible with memU's embedding interface.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the local embedding model.
        
        Args:
            model_name: HuggingFace model name for embeddings
                - "all-MiniLM-L6-v2" (fast, 384 dims)
                - "all-mpnet-base-v2" (better quality, 768 dims)
        """
        from sentence_transformers import SentenceTransformer
        
        self.model_name = model_name
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Dimension: {self.dimension}")
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def get_embedding_dimension(self) -> int:
        """Return the embedding dimension."""
        return self.dimension


def create_memu_agent_with_local_embeddings():
    """
    Create a memU agent using local embeddings instead of OpenAI.
    """
    from memu import MemoryAgent
    from memu.memory.embeddings import EmbeddingClient
    
    # Create local embedding client
    local_client = LocalEmbeddingClient()
    
    # Create memU embedding client with custom provider
    embedding_client = EmbeddingClient(
        provider="custom",
        client=local_client
    )
    
    # For the LLM, we still need Anthropic/OpenAI
    # But embeddings are now local!
    return embedding_client


if __name__ == "__main__":
    # Test the local embeddings
    print("Testing local embeddings...")
    
    client = LocalEmbeddingClient()
    
    # Test single embedding
    text = "Hello, this is a test of local embeddings."
    embedding = client.embed(text)
    print(f"\nSingle embedding test:")
    print(f"  Text: {text}")
    print(f"  Embedding dimension: {len(embedding)}")
    print(f"  First 5 values: {embedding[:5]}")
    
    # Test batch embedding
    texts = [
        "The weather in Chicago is cold.",
        "I love programming in Python.",
        "Trading commodities is interesting."
    ]
    embeddings = client.embed_batch(texts)
    print(f"\nBatch embedding test:")
    print(f"  {len(embeddings)} texts embedded")
    
    # Test similarity
    from numpy import dot
    from numpy.linalg import norm
    
    def cosine_similarity(a, b):
        return dot(a, b) / (norm(a) * norm(b))
    
    print(f"\nSimilarity tests:")
    for i, t in enumerate(texts):
        sim = cosine_similarity(embedding, embeddings[i])
        print(f"  '{t[:30]}...' similarity to test: {sim:.3f}")
    
    print("\n✅ Local embeddings working!")
