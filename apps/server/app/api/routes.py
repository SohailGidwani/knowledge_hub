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
from werkzeug.utils import secure_filename

from . import api_bp
from ..db import db
from ..models import Document, User
from ..ingestion import process_document

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
