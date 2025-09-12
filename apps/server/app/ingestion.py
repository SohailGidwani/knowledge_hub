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

import math
import numpy as np
import cv2
import fitz
import pytesseract
from pytesseract import Output

# ---------- image utils ----------

def _deskew(gray: np.ndarray) -> np.ndarray:
    # Invert for text as white
    inv = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(inv > 0))
    if coords.size == 0:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    # cv2 returns [-90, 0); convert to [-45,45]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def _enhance(gray: np.ndarray) -> np.ndarray:
    # light denoise + contrast boost
    den = cv2.fastNlMeansDenoising(gray, h=8)
    # unsharp mask
    blur = cv2.GaussianBlur(den, (0, 0), 1.0)
    sharp = cv2.addWeighted(den, 1.5, blur, -0.5, 0)
    return sharp

def _binarize_candidates(gray: np.ndarray) -> list[np.ndarray]:
    # Multiple thresholding strategies; we’ll OCR each and pick best by confidence
    thr1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, 31, 10)
    thr2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                 cv2.THRESH_BINARY, 41, 5)
    _, thr3 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return [thr1, thr2, thr3]

def _preprocess_for_ocr(image_bgr: np.ndarray) -> list[np.ndarray]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = _deskew(gray)
    gray = _enhance(gray)
    cands = _binarize_candidates(gray)
    # mild morphology to connect handwriting strokes
    out = []
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    for img in cands:
        closed = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel, iterations=1)
        out.append(closed)
    return out

def _pixmap_to_cv2(pix):
    buf = np.frombuffer(pix.samples, dtype=np.uint8)
    arr = buf.reshape(pix.height, pix.width, pix.n)
    if pix.n == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    else:
        return arr

# ---------- OCR runners ----------

_TESS_CONFIGS = [
    # LSTM-only, assume a block of text
    "--oem 1 --psm 6",
    # sparse text with OSD
    "--oem 1 --psm 11",
    # single column (common for assignments)
    "--oem 1 --psm 4",
]

def _ocr_with_conf(img: np.ndarray, lang: str = "eng") -> tuple[str, float]:
    """
    Returns (text, avg_conf 0..100). Uses image_to_data to compute confidence.
    """
    data = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT, config="--oem 1 --psm 6")
    texts, confs = data.get("text", []), data.get("conf", [])
    pieces = []
    scores = []
    for t, c in zip(texts, confs):
        if t and t.strip() and c != '-1':
            pieces.append(t)
            try:
                scores.append(float(c))
            except Exception:
                pass
    text = " ".join(pieces).strip()
    avg_conf = float(sum(scores) / len(scores)) if scores else 0.0
    return text, avg_conf

def _try_tesseract_variants(bin_imgs: list[np.ndarray], lang: str = "eng") -> tuple[str, float]:
    best_text, best_conf = "", 0.0
    for img in bin_imgs:
        # Run a few PSMs and keep the best confidence
        for cfg in _TESS_CONFIGS:
            data = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT, config=cfg)
            texts, confs = data.get("text", []), data.get("conf", [])
            pieces, scores = [], []
            for t, c in zip(texts, confs):
                if t and t.strip() and c != '-1':
                    pieces.append(t)
                    try:
                        scores.append(float(c))
                    except Exception:
                        pass
            text = " ".join(pieces).strip()
            conf = float(sum(scores) / len(scores)) if scores else 0.0
            if conf > best_conf and len(text) > 0:
                best_conf, best_text = conf, text
    return best_text, best_conf

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
        # Render bigger for handwriting (3x is a good CPU/quality tradeoff)
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        img_bgr = _pixmap_to_cv2(pix)
        bin_variants = _preprocess_for_ocr(img_bgr)
        text, conf = _try_tesseract_variants(bin_variants, lang=lang)
        yield i, text, conf

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
        for page_no, text, conf in ocr_pdf_to_chunks(path, lang=lang):
            chunk = Chunk(
                document_id=d.id,
                version=1,
                page_no=page_no,
                chunk_index=0,
                text=text.strip(),
                modality="text",
                extra_json={"ocr_conf": conf}  # <-- store confidence here
            )
            db.session.add(chunk)
            created += 1
            pages += 1
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