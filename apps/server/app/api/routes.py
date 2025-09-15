"""API routes for document management.

This module exposes a lightweight HTTP API via a Flask Blueprint. It supports:
- Health checks ("/ping")
- Listing recently created documents ("/documents")
- Creating a placeholder document by title (POST "/documents")
- Uploading a file to be stored and registered as a Document (POST "/documents/upload")

Helpers in this file handle default user retrieval, content hashing, and MIME
type detection to keep the route handlers small and focused.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path

import filetype
from flask import request, jsonify, current_app
from typing import Optional
import time
import re
from werkzeug.utils import secure_filename
from sqlalchemy import text as sa_text

from . import api_bp
from ..db import db
from ..models import Document, User
from ..ingestion import process_document
from ..jobs import index_embeddings
from ..embeddings import embed_texts
from ..llm import LLMConfig, ollama_chat, extract_citation_indices
from ..models import Chunk, Embedding

# ---- helpers ----
def get_default_user():
    """Return the first User or create a simple default one.

    In dev/demo environments we often don't implement auth. This ensures there
    is always at least one user to associate with created Documents.
    """
    u = User.query.first()
    if not u:
        u = User(email="dev@local")
        db.session.add(u)
        db.session.commit()
    return u

def compute_sha256(fp: Path) -> str:
    """Compute a streaming SHA‑256 digest for a file on disk.

    Reads the file in 1 MiB chunks to avoid loading large files entirely into
    memory.
    """
    h = hashlib.sha256()
    with fp.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def detect_mime(fp: Path, fallback_name: str) -> str:
    """Best‑effort MIME type detection.

    Tries content‑based detection first (via ``filetype``). If that fails,
    falls back to extension‑based guessing using ``mimetypes``. Defaults to
    ``application/octet-stream`` when unknown.
    """
    kind = filetype.guess(fp)
    if kind:
        return kind.mime
    # fallback to extension guess
    import mimetypes
    mime, _ = mimetypes.guess_type(fallback_name)
    return mime or "application/octet-stream"

def _to_vector_literal(vec) -> str:
    """Format a numpy (or list) vector as a pgvector literal: '[0.1,-0.2,...]'"""
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"


def _rough_tokens_local(s: str) -> int:
    # fast proxy for tokens; mirrors ingestion._rough_tokens
    return max(0, len(re.findall(r"\w+|\S", s or "")))


def _trim_preserve_sentence(text: str, max_chars: int = 800) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars]
    # try to cut on a sentence boundary
    m = re.search(r"[\.!?]\s+[^\.!?]*$", cut)
    if m:
        end = m.start() + 1
        return cut[:end].strip()
    # fallback to last whitespace
    ws = cut.rfind(" ")
    return cut[: ws if ws > 0 else max_chars].strip()


def _hybrid_retrieve_for_answer(q: str, limit: int, doc_id: Optional[int]):
    # This mirrors search_hybrid() but returns python dicts for reuse here.
    # --- Semantic side ---
    qvec = embed_texts([q])[0]
    qvec_lit = _to_vector_literal(qvec)

    where_doc_sem = "AND c.document_id = :doc_id" if doc_id else ""
    sem_sql = f"""
        SELECT
            c.id   AS chunk_id,
            c.document_id,
            d.title AS document_title,
            c.page_no,
            c.chunk_index,
            (e.vector <=> CAST(:qvec AS vector)) AS vdist,
            LEFT(COALESCE(c.text,''), 400) AS preview,
            COALESCE((c.extra_json->>'ocr_conf')::float, 100.0) AS ocr_conf
        FROM embeddings e
        JOIN chunks c   ON c.id = e.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE 1=1
        {where_doc_sem}
        ORDER BY e.vector <=> CAST(:qvec AS vector) ASC
        LIMIT :k
    """
    k = max(limit * 3, 60)
    params_sem = {"qvec": qvec_lit, "k": k}
    if doc_id:
        params_sem["doc_id"] = int(doc_id)
    sem_rows = db.session.execute(sa_text(sem_sql), params_sem).mappings().all()

    # --- FTS side ---
    where_doc_fts = "AND c.document_id = :doc_id" if doc_id else ""
    fts_sql = f"""
        WITH qts AS (SELECT websearch_to_tsquery('english', :q) AS tsq)
        SELECT
            c.id   AS chunk_id,
            c.document_id,
            d.title AS document_title,
            c.page_no,
            c.chunk_index,
            ts_rank_cd(to_tsvector('english', COALESCE(c.text,'')), qts.tsq) AS frank,
            ts_headline('english', COALESCE(c.text,''), qts.tsq,
                'StartSel=<b>,StopSel=</b>,MaxFragments=2,MinWords=5,MaxWords=25') AS snippet,
            COALESCE((c.extra_json->>'ocr_conf')::float, 100.0) AS ocr_conf
        FROM chunks c
        JOIN documents d ON d.id = c.document_id, qts
        WHERE to_tsvector('english', COALESCE(c.text,'')) @@ qts.tsq
        {where_doc_fts}
        ORDER BY frank DESC
        LIMIT :k
    """
    params_fts = {"q": q, "k": k}
    if doc_id:
        params_fts["doc_id"] = int(doc_id)
    fts_rows = db.session.execute(sa_text(fts_sql), params_fts).mappings().all()

    # --- Blend
    from math import isfinite
    def zstats(values):
        vals = [v for v in values if isfinite(v)]
        if not vals:
            return (0.0, 1.0)
        mu = sum(vals) / len(vals)
        var = sum((x - mu) ** 2 for x in vals) / max(1, len(vals) - 1)
        sd = (var ** 0.5) or 1.0
        return (mu, sd)

    sem = {r["chunk_id"]: r for r in sem_rows}
    fts = {r["chunk_id"]: r for r in fts_rows}
    v_sims = [1.0 - float(r["vdist"]) for r in sem_rows]
    f_scores = [float(r["frank"]) for r in fts_rows]
    v_mu, v_sd = zstats(v_sims)
    f_mu, f_sd = zstats(f_scores)
    alpha, beta = 0.6, 0.4
    combined = {}
    for cid, r in sem.items():
        vsim = 1.0 - float(r["vdist"])
        vnorm = (vsim - v_mu) / (v_sd or 1.0)
        combined[cid] = {
            "chunk_id": cid,
            "document_id": r["document_id"],
            "document_title": r["document_title"],
            "page_no": r["page_no"],
            "chunk_index": r["chunk_index"],
            "preview": r["preview"],
            "snippet": None,
            "vscore": vnorm,
            "fscore": 0.0,
            "ocr_conf": float(r["ocr_conf"]) if r["ocr_conf"] is not None else 100.0,
        }
    for cid, r in fts.items():
        fnorm = (float(r["frank"]) - f_mu) / (f_sd or 1.0)
        if cid in combined:
            combined[cid]["fscore"] = fnorm
            combined[cid]["snippet"] = r["snippet"]
        else:
            combined[cid] = {
                "chunk_id": cid,
                "document_id": r["document_id"],
                "document_title": r["document_title"],
                "page_no": r["page_no"],
                "chunk_index": r["chunk_index"],
                "preview": None,
                "snippet": r["snippet"],
                "vscore": 0.0,
                "fscore": fnorm,
                "ocr_conf": float(r["ocr_conf"]) if r["ocr_conf"] is not None else 100.0,
            }
    items = list(combined.values())
    for it in items:
        base = alpha * it.get("vscore", 0.0) + beta * it.get("fscore", 0.0)
        conf = float(it.get("ocr_conf") or 100.0)
        mult = 0.85 + 0.15 * max(0.0, min(conf, 100.0)) / 100.0
        it["score"] = base * mult
        it["low_confidence"] = conf < 60.0
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:limit]


# ---- routes ----
@api_bp.get("/ping")
def ping():
    """Basic health check endpoint.

    Returns a simple JSON payload indicating the API is reachable.
    """
    return jsonify({"ok": True})

@api_bp.get("/documents")
def list_documents():
    """Return up to 50 most recent documents (newest first)."""
    docs = Document.query.order_by(Document.created_at.desc()).limit(50).all()
    return jsonify([
        {
            "id": d.id,
            "title": d.title,
            "status": d.status,
            "mime_type": d.mime_type,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ])

@api_bp.get("/documents/<int:doc_id>")
def get_document(doc_id: int):
    """Return a single document record by id."""
    d = Document.query.get(doc_id)
    if not d:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": d.id,
        "title": d.title,
        "status": d.status,
        "mime_type": d.mime_type,
        "source_path": (d.source_path or "").replace("/app/", "/"),
        "pages": d.pages,
        "bytes": d.bytes,
        "hash_sha256": d.hash_sha256,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    })

@api_bp.post("/documents")
def create_document():
    """Create a simple Document by title (no file upload).

    Request body: JSON with ``title`` (string, required).
    Returns: 201 Created with the new document id + title.
    """
    data = request.get_json(force=True)
    title = data.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400
    user = get_default_user()
    doc = Document(user_id=user.id, title=title, status="ready")
    db.session.add(doc)
    db.session.commit()
    return jsonify({"id": doc.id, "title": doc.title}), 201

@api_bp.post("/documents/upload")
def upload_document():
    """
    Multipart upload handler.

    Form fields:
      - ``file``: the binary file (required)
      - ``title`` (optional): custom title; defaults to the uploaded filename

    Saves the file under the configured ``STORAGE_DIR`` with a unique
    timestamped filename, computes metadata (MIME, size, SHA‑256), persists a
    Document row, and returns a summary payload.
    """
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    # Title
    title = request.form.get("title") or file.filename
    title = title.strip()

    # Paths
    user = get_default_user()
    storage_dir: Path = current_app.config["STORAGE_DIR"]
    # Ensure the storage directory exists. ``parents=True`` makes intermediate
    # directories, ``exist_ok=True`` keeps this idempotent.
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Safe name + unique timestamped path
    # ``secure_filename`` strips/normalizes potentially unsafe characters. Fall
    # back to a generic name if the result is empty.
    safe_name = secure_filename(file.filename) or f"upload_{int(datetime.utcnow().timestamp())}"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    dest = storage_dir / f"{ts}__{safe_name}"

    # Save file
    file.save(dest)

    # Metadata
    mime = detect_mime(dest, safe_name)
    size_bytes = dest.stat().st_size
    sha256 = compute_sha256(dest)

    # Persist Document
    doc = Document(
        user_id=user.id,
        title=title,
        source_path=str(dest),
        mime_type=mime,
        pages=None,            # we’ll fill after parsing
        bytes=size_bytes,
        hash_sha256=sha256,
        status="ready",        # set to "processing" if/when an async pipeline is added
    )
    db.session.add(doc)
    db.session.commit()
    # --- Ingest now (sync) ---
    ingest_result = process_document(doc.id, lang="eng")

    return jsonify({
        "id": doc.id,
        "title": doc.title,
        "mime_type": doc.mime_type,
        "bytes": doc.bytes,
        "hash_sha256": doc.hash_sha256,
        # Present a friendlier path by stripping container‑specific prefix.
        "source_path": doc.source_path.replace("/app/", "/"),
        "status": doc.status,
        "ingest_result": ingest_result,
    }), 201

@api_bp.delete("/documents/<int:doc_id>")
def delete_document(doc_id: int):
    """Delete a document and all related data (chunks, embeddings, tags),
    and optionally remove the stored source file.

    Query params:
      - delete_file=true|false (default true)
    """
    d = Document.query.get(doc_id)
    if not d:
        return jsonify({"error": "document not found"}), 404

    delete_file = (request.args.get("delete_file", "true").lower() != "false")
    file_deleted = False

    # Remove file on disk if it's under STORAGE_DIR for safety
    if delete_file and d.source_path:
        try:
            storage_dir: Path = current_app.config["STORAGE_DIR"].resolve()
            fp = Path(d.source_path).resolve()
            # Only delete if the file resides inside storage_dir
            if str(fp).startswith(str(storage_dir)) and fp.exists():
                fp.unlink()
                file_deleted = True
        except Exception:
            # Swallow file errors but continue DB cleanup
            pass

    # Delete in dependency order with explicit SQL for robustness
    # 1) embeddings -> via chunks
    res_emb = db.session.execute(sa_text(
        """
        DELETE FROM embeddings e
        USING chunks c
        WHERE e.chunk_id = c.id AND c.document_id = :doc_id
        """
    ), {"doc_id": doc_id})

    # 2) chunks
    res_chunks = db.session.execute(sa_text(
        "DELETE FROM chunks WHERE document_id = :doc_id"
    ), {"doc_id": doc_id})

    # 3) document_tags (if any)
    res_tags = db.session.execute(sa_text(
        "DELETE FROM document_tags WHERE document_id = :doc_id"
    ), {"doc_id": doc_id})

    # 4) document
    res_doc = db.session.execute(sa_text(
        "DELETE FROM documents WHERE id = :doc_id"
    ), {"doc_id": doc_id})

    db.session.commit()

    return jsonify({
        "ok": True,
        "document_id": doc_id,
        "deleted": {
            "embeddings": res_emb.rowcount if hasattr(res_emb, "rowcount") else None,
            "chunks": res_chunks.rowcount if hasattr(res_chunks, "rowcount") else None,
            "tags": res_tags.rowcount if hasattr(res_tags, "rowcount") else None,
            "documents": res_doc.rowcount if hasattr(res_doc, "rowcount") else None,
        },
        "file_deleted": file_deleted,
    })

@api_bp.post("/search")
def search_chunks():
    payload = request.get_json(force=True) if request.is_json else {}
    q = (payload.get("q") or "").strip()
    if not q:
        return jsonify({"error": "q is required"}), 400


    limit = int(payload.get("limit", 20))
    offset = int(payload.get("offset", 0))
    doc_id = payload.get("document_id") # optional filter


    # Build SQL with optional document filter. We use plainto_tsquery for simplicity;
    # upgrade to websearch_to_tsquery if you want Google‑like syntax.
    where_doc = "AND c.document_id = :doc_id" if doc_id else ""
    sql = f"""
    WITH q AS (
    SELECT plainto_tsquery('english', :q) AS tsq
    )
    SELECT
    c.id AS chunk_id,
    c.document_id,
    c.page_no,
    c.chunk_index,
    d.title AS document_title,
    ts_rank_cd(to_tsvector('english', coalesce(c.text, '')), q.tsq) AS rank,
    ts_headline('english', coalesce(c.text, ''), q.tsq,
    'StartSel=<b>,StopSel=</b>,MaxFragments=2,MinWords=5,MaxWords=25') AS snippet
    FROM chunks c
    JOIN documents d ON d.id = c.document_id,
    q
    WHERE to_tsvector('english', coalesce(c.text, '')) @@ q.tsq
    {where_doc}
    ORDER BY rank DESC, c.id DESC
    LIMIT :limit OFFSET :offset
    """
    params = {"q": q, "limit": limit, "offset": offset}
    if doc_id:
        params["doc_id"] = int(doc_id)


    rows = db.session.execute(sa_text(sql), params).mappings().all()


    return jsonify({
    "q": q,
    "count": len(rows),
    "results": [
    {
    "chunk_id": r["chunk_id"],
    "document_id": r["document_id"],
    "document_title": r["document_title"],
    "page_no": r["page_no"],
    "chunk_index": r["chunk_index"],
    "rank": float(r["rank"]),
    "snippet": r["snippet"], # contains <b>...</b>
    }
    for r in rows
    ],
    "limit": limit,
    "offset": offset,
    })

@api_bp.get("/documents/<int:doc_id>/chunks")
def get_doc_chunks(doc_id: int):
    limit = int(request.args.get("limit", 50))
    rows = db.session.execute(sa_text(
    """
    SELECT id AS chunk_id, page_no, chunk_index, left(coalesce(text,''), 300) AS sample
    FROM chunks
    WHERE document_id = :doc_id
    ORDER BY page_no, chunk_index
    LIMIT :limit
    """
    ), {"doc_id": doc_id, "limit": limit}).mappings().all()
    return jsonify({
    "document_id": doc_id,
    "count": len(rows),
    "chunks": rows,
    })

@api_bp.post("/embeddings/reindex")
def reindex_embeddings():
    """
    Body (optional):
      - document_id: int (only reindex this doc)
      - batch_size: int (default 128)
    """
    payload = request.get_json(force=True) if request.is_json else {}
    document_id = payload.get("document_id")
    batch_size = int(payload.get("batch_size", 128))

    res = index_embeddings(document_id=document_id, batch_size=batch_size)
    # Optional: ANALYZE to inform ivfflat
    db.session.execute(sa_text("ANALYZE embeddings;"))
    return jsonify({"ok": True, "indexed": res})

@api_bp.post("/search/semantic")
def search_semantic():
    payload = request.get_json(force=True) if request.is_json else {}
    q = (payload.get("q") or "").strip()
    if not q:
        return jsonify({"error": "q is required"}), 400

    limit = int(payload.get("limit", 20))
    offset = int(payload.get("offset", 0))
    doc_id = payload.get("document_id")

    # embed query and format as pgvector literal
    qvec = embed_texts([q])[0]               # numpy array, normalized
    qvec_lit = _to_vector_literal(qvec)      # e.g. "[0.123,-0.456,...]"

    where_doc = "WHERE c.document_id = :doc_id" if doc_id else ""
    sql = f"""
        SELECT
            e.id AS embedding_id,
            c.id AS chunk_id,
            c.document_id,
            d.title AS document_title,
            c.page_no,
            c.chunk_index,
            (e.vector <=> CAST(:qvec AS vector)) AS distance,   -- cosine distance
            LEFT(COALESCE(c.text,''), 400) AS preview
        FROM embeddings e
        JOIN chunks c   ON c.id = e.chunk_id
        JOIN documents d ON d.id = c.document_id
        {where_doc}
        ORDER BY e.vector <=> CAST(:qvec AS vector) ASC
        LIMIT :limit OFFSET :offset
    """

    params = {"qvec": qvec_lit, "limit": limit, "offset": offset}
    if doc_id:
        params["doc_id"] = int(doc_id)

    rows = db.session.execute(sa_text(sql), params).mappings().all()

    # Convert cosine distance (0 = identical) to a similarity-ish score for UI
    results = []
    for r in rows:
        dist = float(r["distance"])
        sim = 1.0 - dist
        results.append({
            "chunk_id": r["chunk_id"],
            "document_id": r["document_id"],
            "document_title": r["document_title"],
            "page_no": r["page_no"],
            "chunk_index": r["chunk_index"],
            "similarity": sim,
            "preview": r["preview"],
        })

    return jsonify({"q": q, "count": len(results), "results": results})

@api_bp.post("/search/hybrid")
def search_hybrid():
    payload = request.get_json(force=True) if request.is_json else {}
    q = (payload.get("q") or "").strip()
    if not q:
        return jsonify({"error": "q is required"}), 400

    limit = int(payload.get("limit", 20))
    doc_id = payload.get("document_id")

    # --- Semantic side ---
    qvec = embed_texts([q])[0]                  # normalized np.array
    qvec_lit = _to_vector_literal(qvec)         # '[...]' string literal

    where_doc_sem = "AND c.document_id = :doc_id" if doc_id else ""
    sem_sql = f"""
        SELECT
            c.id   AS chunk_id,
            c.document_id,
            d.title AS document_title,
            c.page_no,
            c.chunk_index,
            (e.vector <=> CAST(:qvec AS vector)) AS vdist,      -- cosine distance
            LEFT(COALESCE(c.text,''), 400) AS preview,
            COALESCE((c.extra_json->>'ocr_conf')::float, 100.0) AS ocr_conf
        FROM embeddings e
        JOIN chunks c   ON c.id = e.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE 1=1
        {where_doc_sem}
        ORDER BY e.vector <=> CAST(:qvec AS vector) ASC
        LIMIT :k
    """
    k = max(limit * 3, 60)  # fetch more from each side, blend later
    params_sem = {"qvec": qvec_lit, "k": k}
    if doc_id:
        params_sem["doc_id"] = int(doc_id)
    sem_rows = db.session.execute(sa_text(sem_sql), params_sem).mappings().all()

    # --- FTS side ---
    where_doc_fts = "AND c.document_id = :doc_id" if doc_id else ""
    fts_sql = f"""
        WITH qts AS (SELECT websearch_to_tsquery('english', :q) AS tsq)
        SELECT
            c.id   AS chunk_id,
            c.document_id,
            d.title AS document_title,
            c.page_no,
            c.chunk_index,
            ts_rank_cd(to_tsvector('english', COALESCE(c.text,'')), qts.tsq) AS frank,
            ts_headline('english', COALESCE(c.text,''), qts.tsq,
                'StartSel=<b>,StopSel=</b>,MaxFragments=2,MinWords=5,MaxWords=25') AS snippet,
            COALESCE((c.extra_json->>'ocr_conf')::float, 100.0) AS ocr_conf
        FROM chunks c
        JOIN documents d ON d.id = c.document_id, qts
        WHERE to_tsvector('english', COALESCE(c.text,'')) @@ qts.tsq
        {where_doc_fts}
        ORDER BY frank DESC
        LIMIT :k
    """
    params_fts = {"q": q, "k": k}
    if doc_id:
        params_fts["doc_id"] = int(doc_id)
    fts_rows = db.session.execute(sa_text(fts_sql), params_fts).mappings().all()

    # --- Blend scores (z-normalize each stream, then weighted sum) ---
    from math import isfinite

    def zstats(values):
        vals = [v for v in values if isfinite(v)]
        if not vals:
            return (0.0, 1.0)
        mu = sum(vals) / len(vals)
        var = sum((x - mu) ** 2 for x in vals) / max(1, len(vals) - 1)
        sd = (var ** 0.5) or 1.0
        return (mu, sd)

    # Prepare dicts keyed by chunk_id
    sem = {r["chunk_id"]: r for r in sem_rows}
    fts = {r["chunk_id"]: r for r in fts_rows}

    # Convert distances to similarities for semantic, then z-normalize
    v_sims = [1.0 - float(r["vdist"]) for r in sem_rows]
    f_scores = [float(r["frank"]) for r in fts_rows]
    v_mu, v_sd = zstats(v_sims)
    f_mu, f_sd = zstats(f_scores)

    # weights for final blend
    alpha, beta = 0.6, 0.4

    combined = {}

    # seed with semantic
    for cid, r in sem.items():
        vsim = 1.0 - float(r["vdist"])
        vnorm = (vsim - v_mu) / (v_sd or 1.0)
        combined[cid] = {
            "chunk_id": cid,
            "document_id": r["document_id"],
            "document_title": r["document_title"],
            "page_no": r["page_no"],
            "chunk_index": r["chunk_index"],
            "preview": r["preview"],
            "snippet": None,
            "vscore": vnorm,
            "fscore": 0.0,
            "ocr_conf": float(r["ocr_conf"]) if r["ocr_conf"] is not None else 100.0,
        }

    # merge FTS
    for cid, r in fts.items():
        fnorm = (float(r["frank"]) - f_mu) / (f_sd or 1.0)
        if cid in combined:
            combined[cid]["fscore"] = fnorm
            combined[cid]["snippet"] = r["snippet"]
        else:
            combined[cid] = {
                "chunk_id": cid,
                "document_id": r["document_id"],
                "document_title": r["document_title"],
                "page_no": r["page_no"],
                "chunk_index": r["chunk_index"],
                "preview": None,
                "snippet": r["snippet"],
                "vscore": 0.0,
                "fscore": fnorm,
                "ocr_conf": float(r["ocr_conf"]) if r["ocr_conf"] is not None else 100.0,
            }

    # final score & sort
    items = list(combined.values())
    for it in items:
        base = alpha * it.get("vscore", 0.0) + beta * it.get("fscore", 0.0)
        conf = float(it.get("ocr_conf") or 100.0)
        # Slight down-weighting for low OCR confidence: 0.85 .. 1.0 multiplier
        mult = 0.85 + 0.15 * max(0.0, min(conf, 100.0)) / 100.0
        it["score"] = base * mult
        it["low_confidence"] = conf < 60.0
    items.sort(key=lambda x: x["score"], reverse=True)
    items = items[:limit]

    return jsonify({
        "q": q,
        "count": len(items),
        "weights": {"semantic": alpha, "fts": beta},
        "results": [
            {
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "document_title": r["document_title"],
                "page_no": r["page_no"],
                "chunk_index": r["chunk_index"],
                "score": r["score"],
                "snippet": r["snippet"],   # may contain <b>..</b>
                "preview": r["preview"],   # plain text
                "low_confidence": r.get("low_confidence", False),
            } for r in items
        ],
    })


@api_bp.post("/answer")
def answer_api():
    payload = request.get_json(force=True) if request.is_json else {}
    q = (payload.get("q") or "").strip()
    if not q:
        return jsonify({"error": "q is required"}), 400

    filters = payload.get("filters") or {}
    doc_id = filters.get("document_id") if isinstance(filters, dict) else None
    k = int(payload.get("k", 16))
    max_ctx_tokens = int(payload.get("max_context_tokens", 3000))

    t0 = time.monotonic()
    # Retrieve top chunks (hybrid)
    top_items = _hybrid_retrieve_for_answer(q, k, doc_id)
    if not top_items:
        total_ms = int((time.monotonic() - t0) * 1000)
        return jsonify({
            "answer": "Insufficient context; try different keywords or remove filters.",
            "citations": [],
            "used_chunks": [],
            "timings": {"retrieve_ms": total_ms, "llm_ms": 0, "total_ms": total_ms},
        })

    # Fetch full chunk texts for selected chunks
    ids = [it["chunk_id"] for it in top_items]
    q_rows = (
        db.session.query(
            Chunk.id.label("chunk_id"),
            Chunk.text,
            Chunk.page_no,
            Chunk.chunk_index,
            Chunk.document_id,
            Document.title.label("document_title"),
        )
        .join(Document, Document.id == Chunk.document_id)
        .filter(Chunk.id.in_(ids))
        .all()
    )
    by_id = {}
    for row in q_rows:
        by_id[row.chunk_id] = {
            "chunk_id": row.chunk_id,
            "text": row.text,
            "page_no": row.page_no,
            "chunk_index": row.chunk_index,
            "document_id": row.document_id,
            "document_title": row.document_title,
        }

    # Deduplicate by (document_id, page_no), keep highest score
    seen_pages = set()
    packed = []
    tokens_acc = 0
    used_chunk_ids = []
    cit_map = []  # index -> provenance
    for it in top_items:
        r = by_id.get(it["chunk_id"])
        if not r:
            continue
        key = (r["document_id"], r["page_no"]) if r["page_no"] is not None else (r["document_id"], -1)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        text = _trim_preserve_sentence(r.get("text") or "", 800)
        if not text:
            continue
        ctoks = _rough_tokens_local(text)
        if tokens_acc + ctoks > max_ctx_tokens:
            break
        tokens_acc += ctoks
        used_chunk_ids.append(r["chunk_id"])
        cit_map.append({
            "chunk_id": r["chunk_id"],
            "document_id": r["document_id"],
            "page_no": r["page_no"],
            "title": r["document_title"],
        })
        packed.append({
            "title": r["document_title"],
            "page_no": r["page_no"],
            "chunk_index": r["chunk_index"],
            "text": text,
        })

    retrieve_ms = int((time.monotonic() - t0) * 1000)

    # Build prompt
    system_msg = (
        "You answer only from the provided CONTEXT. If insufficient, say so. "
        "Include [CIT-#] after each claim. Be concise but complete. Do not use prior knowledge."
        "You are a helpful assistant that can answer questions about the provided CONTEXT."
        "Don't say 'based on the context' or 'based on the provided information' everytime you answer a question ."
    )
    context_lines = ["CONTEXT:"]
    for i, blk in enumerate(packed, start=1):
        head = f"[CIT-{i}] Title: \"{blk['title']}\""
        if blk.get("page_no"):
            head += f", Page {blk['page_no']}"
        context_lines.append(head)
        context_lines.append(blk["text"])
        context_lines.append("")
    context_block = "\n".join(context_lines).strip()

    scope_hint = f" (scope: document_id={doc_id})" if doc_id else ""
    user_msg = (
        "Return a coherent answer with bullet points and short paragraphs. "
        "Don't invent facts. Always cite.\n\n" + context_block + f"\n\nQUESTION{scope_hint}: {q}"
    )

    # LLM call
    cfg = LLMConfig(
        host=str(current_app.config.get("OLLAMA_HOST")),
        model=str(current_app.config.get("LLM_MODEL")),
        timeout_ms=int(current_app.config.get("LLM_TIMEOUT_MS", 120000)),
        num_ctx=None,
    )
    try:
        answer_text, meta = ollama_chat(system_msg, user_msg, cfg, retries=2)
    except Exception as e:
        total_ms = int((time.monotonic() - t0) * 1000)
        return jsonify({
            "error": "llm_unreachable",
            "detail": str(e),
            "hint": "Ensure Ollama is running and OLLAMA_HOST is reachable from the container.",
            "timings": {"retrieve_ms": retrieve_ms, "llm_ms": 0, "total_ms": total_ms},
        }), 502

    # If no citations, try one stricter retry
    cit_idxs = extract_citation_indices(answer_text)
    if not cit_idxs:
        stricter = user_msg + "\n\nStrictly include citations like [CIT-#] from CONTEXT only."
        try:
            answer_text, meta = ollama_chat(system_msg, stricter, cfg, retries=1)
        except Exception as e:
            total_ms = int((time.monotonic() - t0) * 1000)
            return jsonify({
                "error": "llm_unreachable",
                "detail": str(e),
                "hint": "Ensure Ollama is running and OLLAMA_HOST is reachable from the container.",
                "timings": {"retrieve_ms": retrieve_ms, "llm_ms": 0, "total_ms": total_ms},
            }), 502
        cit_idxs = extract_citation_indices(answer_text)

    # Map citations
    citations = []
    for idx in cit_idxs:
        if 1 <= idx <= len(cit_map):
            p = cit_map[idx - 1]
            citations.append({
                "cit": f"CIT-{idx}",
                "document_id": p["document_id"],
                "page_no": p["page_no"],
                "title": p["title"],
            })

    total_ms = int((time.monotonic() - t0) * 1000)
    timings = {"retrieve_ms": retrieve_ms, "llm_ms": meta.get("llm_ms", 0), "total_ms": total_ms}

    return jsonify({
        "answer": answer_text,
        "citations": citations,
        "used_chunks": used_chunk_ids,
        "timings": timings,
    })
