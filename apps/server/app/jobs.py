from __future__ import annotations
from typing import Optional, Iterable
from sqlalchemy import select
from sqlalchemy.orm import load_only
import numpy as np

from .db import db
from .models import Chunk, Embedding
from .embeddings import embed_texts

def iter_chunk_ids_texts(document_id: Optional[int] = None, batch_size: int = 128) -> Iterable[list[tuple[int, str]]]:
    q = db.session.query(Chunk.id, Chunk.text)
    if document_id:
        q = q.filter(Chunk.document_id == document_id)
    # left join to find chunks without embeddings
    # Simpler approach: filter out chunks that already have at least one embedding
    sub = select(Embedding.chunk_id).subquery()
    q = q.filter(~Chunk.id.in_(sub))
    q = q.order_by(Chunk.id.asc())

    # stream in small pages
    offset = 0
    while True:
        batch = q.limit(batch_size).offset(offset).all()
        if not batch:
            break
        yield [(cid, (txt or "")) for cid, txt in batch]
        offset += batch_size

def index_embeddings(document_id: Optional[int] = None, batch_size: int = 128, model_name: str = "all-MiniLM-L6-v2"):
    total_chunks = 0
    total_vectors = 0

    for batch in iter_chunk_ids_texts(document_id, batch_size=batch_size):
        ids = [cid for cid, _ in batch]
        texts = [t for _, t in batch]
        if not ids:
            continue
        vecs = embed_texts(texts)  # np.ndarray [B, D], normalized

        rows = []
        dim = int(vecs.shape[1])
        for cid, vec in zip(ids, vecs):
            rows.append(Embedding(
                chunk_id=cid,
                model=model_name,
                dim=dim,
                vector=vec.tolist()
            ))
        db.session.bulk_save_objects(rows)
        db.session.commit()

        total_chunks += len(batch)
        total_vectors += len(rows)

    return {"chunks_indexed": total_chunks, "vectors_created": total_vectors}