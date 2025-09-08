from __future__ import annotations
import io
from pathlib import Path
from typing import Optional

import cv2
import fitz  # PyMuPDF
import pytesseract
from flask import current_app

from .db import db
from .models import Document, Chunk


def _preprocess_for_ocr(image_bgr):
    # convert to gray
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    # de-noise lightly
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    # adaptive threshold to help handwriting
    thr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )
    return thr


def _pixmap_to_cv2(pix):
    # pix.samples is bytes in RGB
    img = memoryview(pix.samples)
    arr = np.frombuffer(img, dtype=np.uint8)
    arr = arr.reshape(pix.height, pix.width, pix.n)
    # convert RGB -> BGR for OpenCV
    if pix.n == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    else:
        # grayscale
        return arr


# numpy import placed after function defs to keep linters happy
import numpy as np  # noqa: E402


def ocr_pdf_to_chunks(pdf_path: Path, lang: str = "eng"):
    """Yield (page_no, text) for each page in the PDF via OCR.
    Uses PyMuPDF to render at 2x for better OCR of handwriting.
    """
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        # Render at higher dpi for OCR (matrix scales resolution)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bgr = _pixmap_to_cv2(pix)
        proc = _preprocess_for_ocr(img_bgr)
        # OCR
        text = pytesseract.image_to_string(proc, lang=lang)
        yield i, text


def process_document(document_id: int, lang: Optional[str] = None) -> dict:
    """Synchronous ingestion for a single document.
    - If PDF: OCR each page to text chunks
    - If image: OCR the image as page 1
    - For other types: no-op for now
    Returns summary dict with counts.
    """
    lang = lang or "eng"
    d: Document | None = Document.query.get(document_id)
    if not d or not d.source_path:
        return {"error": "document not found or no source_path"}

    path = Path(d.source_path)
    if not path.exists():
        return {"error": f"missing file: {path}"}

    created = 0
    pages = 0

    if (d.mime_type or "").startswith("application/pdf"):
        texts = list(ocr_pdf_to_chunks(path, lang=lang))
        pages = len(texts)
        for page_no, text in texts:
            chunk = Chunk(
                document_id=d.id,
                version=1,
                page_no=page_no,
                chunk_index=0,
                text=text.strip(),
                tokens=None,
                modality="text",
                bbox=None,
                extra_json=None,
            )
            db.session.add(chunk)
            created += 1
        d.pages = pages
        d.status = "ready"
        db.session.commit()
        return {"pages": pages, "chunks_created": created}

    elif (d.mime_type or "").startswith("image/"):
        # Treat single image like a one-page doc
        img = cv2.imread(str(path))
        if img is None:
            return {"error": "failed to read image"}
        proc = _preprocess_for_ocr(img)
        text = pytesseract.image_to_string(proc, lang=lang)
        chunk = Chunk(
            document_id=d.id,
            version=1,
            page_no=1,
            chunk_index=0,
            text=text.strip(),
            modality="text",
        )
        db.session.add(chunk)
        d.pages = 1
        d.status = "ready"
        db.session.commit()
        return {"pages": 1, "chunks_created": 1}

    else:
        # Future: add text/pdfminer path and other formats
        return {"skipped": True, "reason": f"unsupported mime: {d.mime_type}"}