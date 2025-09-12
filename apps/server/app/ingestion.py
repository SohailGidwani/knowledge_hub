from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterable, Tuple

import logging
import re

import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract
from pytesseract import Output

from .db import db
from sqlalchemy import text as sa_text
from .models import Document, Chunk
from .jobs import index_embeddings
from flask import current_app

log = logging.getLogger(__name__)

# --------- OCR helpers ---------

_TESS_CONFIGS = [
    "--oem 1 --psm 6",   # block of text
    "--oem 1 --psm 4",   # single column
    "--oem 1 --psm 11",  # sparse text
]


def _pixmap_to_cv2(pix) -> np.ndarray:
    buf = np.frombuffer(pix.samples, dtype=np.uint8)
    arr = buf.reshape(pix.height, pix.width, pix.n)
    if pix.n == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    if pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    return arr


def _preprocess_variants(image_bgr: np.ndarray) -> list[np.ndarray]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=8)
    # Try multiple thresholds; pick best by confidence later
    thr1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    thr2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 41, 5)
    _, thr3 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return [thr1, thr2, thr3]


def _ocr_best(img_variants: list[np.ndarray], lang: str = "eng") -> tuple[str, float]:
    best_text, best_conf = "", 0.0
    for img in img_variants:
        for cfg in _TESS_CONFIGS:
            data = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT, config=cfg)
            texts, confs = data.get("text", []), data.get("conf", [])
            pieces, scores = [], []
            for t, c in zip(texts, confs):
                if t and t.strip() and c != "-1":
                    pieces.append(t)
                    try:
                        scores.append(float(c))
                    except Exception:
                        pass
            text = " ".join(pieces).strip()
            conf = float(sum(scores) / len(scores)) if scores else 0.0
            if conf > best_conf and text:
                best_text, best_conf = text, conf
    return best_text, best_conf


# --------- Text-first PDF extraction ---------

def _page_has_text(page: fitz.Page) -> bool:
    txt = (page.get_text("text") or "").strip()
    # Consider presence of letters as a signal; ignore pure numbers/whitespace
    return bool(txt) and bool(re.search(r"[A-Za-z]", txt))


def extract_pdf_pages_textfirst(pdf_path: Path, lang: str = "eng") -> Iterable[Tuple[int, str, float]]:
    """
    Yield (page_no, text, ocr_conf) where ocr_conf is None for embedded text pages.
    Only OCR pages that lack embedded text.
    """
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        if _page_has_text(page):
            text = page.get_text("text") or ""
            log.info("ingest.page text page=%s chars=%s", i, len(text))
            yield i, text, None
            continue
        # OCR path
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        img_bgr = _pixmap_to_cv2(pix)
        variants = _preprocess_variants(img_bgr)
        text, conf = _ocr_best(variants, lang=lang)
        log.info("ingest.page ocr page=%s conf=%.1f chars=%s", i, float(conf or 0.0), len(text))
        yield i, text, conf


# --------- Chunking (300–700 tokens with overlap, heading-aware) ---------

def _rough_tokens(s: str) -> int:
    # fast proxy for tokens; keeps us in range
    return max(0, len(re.findall(r"\w+|\S", s)))


def _is_heading(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if len(line) > 80:
        return False
    if line.endswith(('.', ':', ';')):
        return False
    if re.match(r"^(\d+\.|[\-\*•])\s", line):
        return False
    # Title Case or ALL CAPS heuristic
    return (line.isupper() and len(line) >= 3) or (
        sum(1 for w in line.split() if w[:1].isupper()) >= max(1, len(line.split()) // 2)
    )


def _chunk_page_text(page_no: int, text: str, target_min: int = 300, target_max: int = 700, overlap: int = 50):
    lines = [ln.rstrip() for ln in text.splitlines()]
    headings = []  # keep last few headings
    paras: list[str] = []
    buf: list[str] = []

    for ln in lines + [""]:
        if _is_heading(ln):
            headings.append(ln.strip())
        if ln.strip():
            buf.append(ln)
        else:
            if buf:
                paras.append("\n".join(buf).strip())
                buf = []

    # Greedy pack paragraphs into chunks with overlap
    chunks = []
    cur: list[str] = []
    cur_tokens = 0
    i = 0
    for p in paras:
        ptoks = _rough_tokens(p)
        if cur_tokens + ptoks <= target_max:
            cur.append(p)
            cur_tokens += ptoks
            continue
        # flush if we have enough
        if cur_tokens >= target_min or not cur:
            chunks.append("\n\n".join(cur).strip())
            # start next with overlap from tail
            if overlap > 0 and chunks[-1]:
                tail = chunks[-1].split()
                tail = tail[-overlap:]
                cur = [" ".join(tail), p]
                cur_tokens = _rough_tokens(cur[0]) + ptoks
            else:
                cur = [p]
                cur_tokens = ptoks
        else:
            # not enough yet; just add
            cur.append(p)
            cur_tokens += ptoks
        i += 1
    if cur:
        chunks.append("\n\n".join(cur).strip())

    # Compose heading path (last 2 headings) for context
    heading_path = " > ".join(headings[-2:]) if headings else None

    for idx, ch in enumerate(chunks):
        yield idx, ch, heading_path


def process_document(document_id: int, lang: Optional[str] = None) -> dict:
    """
    Synchronous ingestion for a single document.
    - For PDF: prefer embedded text; OCR only pages lacking text.
    - For images: OCR as a single-page doc.
    - Chunk into 300–700 token segments with small overlaps.
    Returns summary dict with counts and stages.
    """
    lang = lang or "eng"
    d: Document | None = Document.query.get(document_id)
    if not d or not d.source_path:
        return {"error": "document not found or no source_path"}

    path = Path(d.source_path)
    if not path.exists():
        return {"error": f"missing file: {path}"}

    total_chunks = 0
    pages = 0

    if (d.mime_type or "").startswith("application/pdf"):
        log.info("ingest.start pdf document_id=%s path=%s", d.id, path)
        for page_no, text, conf in extract_pdf_pages_textfirst(path, lang=lang):
            pages += 1
            base_conf = conf if conf is not None else 100.0
            per_page_chunks = 0
            for idx, ch_text, heading_path in _chunk_page_text(page_no, text):
                chunk = Chunk(
                    document_id=d.id,
                    version=1,
                    page_no=page_no,
                    chunk_index=idx,
                    text=(ch_text or "").strip(),
                    modality="text",
                    tokens=_rough_tokens(ch_text or ""),
                    extra_json={
                        "ocr_conf": base_conf,
                        **({"heading_path": heading_path} if heading_path else {}),
                    },
                )
                db.session.add(chunk)
                total_chunks += 1
                per_page_chunks += 1
            log.info("ingest.page_chunks page=%s chunks=%s", page_no, per_page_chunks)

        d.pages = pages
        d.status = "ready"
        db.session.commit()
        log.info("ingest.done pdf document_id=%s pages=%s chunks=%s", d.id, pages, total_chunks)

    elif (d.mime_type or "").startswith("image/"):
        log.info("ingest.start image document_id=%s path=%s", d.id, path)
        img = cv2.imread(str(path))
        if img is None:
            return {"error": "failed to read image"}
        text, conf = _ocr_best(_preprocess_variants(img), lang=lang)
        for idx, ch_text, heading_path in _chunk_page_text(1, text):
            chunk = Chunk(
                document_id=d.id,
                version=1,
                page_no=1,
                chunk_index=idx,
                text=(ch_text or "").strip(),
                modality="text",
                tokens=_rough_tokens(ch_text or ""),
                extra_json={
                    "ocr_conf": float(conf or 0.0),
                    **({"heading_path": heading_path} if heading_path else {}),
                },
            )
            db.session.add(chunk)
            total_chunks += 1
        d.pages = 1
        d.status = "ready"
        db.session.commit()
        log.info("ingest.done image document_id=%s pages=1 chunks=%s", d.id, total_chunks)

    else:
        return {"skipped": True, "reason": f"unsupported mime: {d.mime_type}"}

    # Auto-index embeddings for new chunks
    try:
        batch_size = int(current_app.config.get("EMBEDDINGS_BATCH_SIZE", 128))
    except Exception:
        batch_size = 128
    idx_res = index_embeddings(document_id=d.id, batch_size=batch_size)
    # Hints for planner/ivfflat after large ingests
    db.session.execute(sa_text("ANALYZE embeddings;"))
    db.session.execute(sa_text("ANALYZE chunks;"))
    return {"pages": pages, "chunks_created": total_chunks, "indexed": idx_res}
