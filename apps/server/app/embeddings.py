from __future__ import annotations
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

# Load once (lazy singleton)
_model = None

def get_model():
    global _model
    if _model is None:
        # Solid small model; good tradeoff for CPU
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

def embed_texts(texts: List[str]) -> np.ndarray:
    model = get_model()
    # Normalize to unit vectors so inner-product ≈ cosine similarity
    vecs = model.encode(texts, normalize_embeddings=True)
    # Ensure float32 (pgvector expects float4[])
    if vecs.dtype != np.float32:
        vecs = vecs.astype(np.float32)
    return vecs