"""
Nomic Embed Text v1.5 Embedding Service - Singleton

Provides fast GPU-accelerated embeddings for UMA semantic search.
Created: 2026-02-06
"""

import numpy as np
from typing import List, Optional

_instance = None


class Embedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        print("Loading nomic-embed-text-v1.5 (prefer CUDA)...")
        try:
            self.model = SentenceTransformer(
                'nomic-ai/nomic-embed-text-v1.5',
                trust_remote_code=True,
                device='cuda'
            )
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print("CUDA OOM loading embedder, falling back to CPU...")
                self.model = SentenceTransformer(
                    'nomic-ai/nomic-embed-text-v1.5',
                    trust_remote_code=True,
                    device='cpu'
                )
            else:
                raise
        if hasattr(self.model, "max_seq_length"):
            self.model.max_seq_length = 8192
        self._cache = {}
        print("Embedder ready.")

    def embed(self, text: str) -> np.ndarray:
        if text not in self._cache:
            self._cache[text] = self.model.encode(text, normalize_embeddings=True)
        return self._cache[text]

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        uncached = [t for t in texts if t not in self._cache]
        if uncached:
            vecs = self.model.encode(uncached, normalize_embeddings=True, batch_size=64)
            for t, v in zip(uncached, vecs):
                self._cache[t] = v
        return [self._cache[t] for t in texts]

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.embed(a), self.embed(b)
        return float(np.dot(va, vb))

    def cosine_similarity(self, va: np.ndarray, vb: np.ndarray) -> float:
        """Cosine similarity between pre-computed embeddings."""
        return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))


def get_embedder() -> Embedder:
    global _instance
    if _instance is None:
        _instance = Embedder()
    return _instance
