<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,15,19,22,27&height=180&section=header&text=Knowledge%20Hub&fontSize=56&fontAlignY=35&animation=fadeIn&fontColor=ffffff" alt="header" />
</div>

<h3 align="center">
  <em>A minimal, container-ready document API with optional OCR ingestion</em>
</h3>

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.0-000?logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/Postgres-16-4169E1?logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/pgvector-enabled-2E7D32" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/Status-Experimental-FF6A00" />
</div>

<br />

## ✨ What Is This?
Knowledge Hub is a lightweight document management and ingestion service built with Flask, SQLAlchemy, and Postgres+pgvector. It exposes simple endpoints to upload, list, and manage documents — with an optional OCR pipeline to turn PDFs/images into searchable text chunks.

<div align="center">
  <sub>Quick links</sub><br />
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api">API</a> •
  <a href="#-tech-stack">Tech Stack</a> •
  <a href="#-ingestion-ocr-optional">OCR</a> •
  <a href="#-development">Dev</a>
</div>

---

## 🚀 Quick Start
Prereqs: Docker + Docker Compose

```bash
# Build and launch database + API
docker compose up --build

# API base URL
open http://localhost:8000

# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/api/ping
```

Data lives under `./data/postgres`, and uploads under `./storage`. Tweak `compose.yaml` to your needs.

---

## 🔌 API
Base: `http://localhost:8000/api`

- `GET /ping` — simple OK check
- `GET /documents` — list latest 50 documents
- `POST /documents` — create by title (JSON)
- `POST /documents/upload` — multipart file upload (with optional `title`)

Examples

```bash
# List documents
curl http://localhost:8000/api/documents

# Create by title
curl -X POST http://localhost:8000/api/documents \
  -H 'Content-Type: application/json' \
  -d '{"title": "My Note"}'

# Upload a PDF
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/path/to/file.pdf" \
  -F "title=Project Plan"
```

---

## 🧱 Architecture
```mermaid
flowchart LR
  subgraph Client
    A[HTTP requests]
  end

  subgraph API[Flask API]
    R[Routes /api/*]
    M[Models + SQLAlchemy]
    I[Ingestion (OCR)]
  end

  DB[(Postgres + pgvector)]
  FS[(Storage dir)]

  A --> R
  R --> M
  M <-.-> DB
  R --> FS
  R --> I
  I --> M
```

---

## 🧰 Tech Stack
<div align="center">
  <img src="https://skillicons.dev/icons?i=python,flask,postgres,docker" height="48" />
  <br />
  <sub>Plus: SQLAlchemy, Gunicorn, pgvector, Pydantic Settings</sub>
  <br />
  <sub>OCR (optional): OpenCV, PyMuPDF, Tesseract, NumPy</sub>
  <br /><br />
</div>

Project layout

```
apps/server/
  app/
    __init__.py     # Flask app factory
    config.py       # Pydantic-based settings
    db.py           # SQLAlchemy instance
    models.py       # ORM models
    ingestion.py    # OCR ingestion utilities (optional)
    api/
      __init__.py   # API blueprint
      routes.py     # Endpoints
  Dockerfile        # API container image

compose.yaml        # Compose stack (db + api)
.env                # Local environment config
```

---

## 🧪 Configuration
Values are pulled from env and `.env` via Pydantic (see `apps/server/app/config.py`).

- `DATABASE_URL` — SQLAlchemy DSN used by the API
- `SECRET_KEY` — Flask secret for signing
- `STORAGE_DIR` — upload directory (default `/app/storage`)
- `MAX_CONTENT_LENGTH` — upload size cap (1 GiB default)

---

## 🔎 Ingestion (OCR) — Optional
`apps/server/app/ingestion.py` can OCR PDFs/images into text chunks and store them as `Chunk` rows.

You’ll need extra deps to enable OCR:

Python packages

```text
opencv-python
pytesseract
PyMuPDF
numpy
```

System packages (inside Docker)

```dockerfile
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*
```

Note: OCR increases image size; keep it separate if you don’t need it in prod.

---

## 🛠 Development
Local (without Docker): Python 3.11 + Postgres 16 (with pgvector)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/server/requirements.txt

export FLASK_APP=app:create_app
cd apps/server
gunicorn -b 127.0.0.1:8000 app:create_app()
```

---

## ✅ Production Notes
- Strong `SECRET_KEY` and managed secrets
- Reverse proxy (e.g., Nginx) in front of Gunicorn
- Logging/metrics/health for your orchestrator
- Schema migrations with Alembic as you evolve
- Add real authn/z (defaults use a single dev user)

<div align="center">
  <br />
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,15,19,22,27&height=120&section=footer" alt="footer" />
</div>
