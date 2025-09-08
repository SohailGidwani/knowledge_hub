# Knowledge Hub API

A minimal document management and ingestion service built with Flask, SQLAlchemy, and Postgres + pgvector. It exposes a small HTTP API to upload and list documents, with optional OCR-based ingestion to turn PDFs/images into text chunks.

## Features
- Health checks and simple JSON API
- Upload documents and store metadata (MIME, size, SHA-256)
- List recent documents
- Postgres schema with Users, Documents, Chunks, Embeddings, and Tags
- Optional OCR ingestion (PDFs/images → text chunks) using Tesseract, OpenCV, and PyMuPDF
- Docker and Docker Compose for local development

## Quick Start (Docker Compose)
Prerequisites: Docker and Docker Compose

```bash
# Build and launch database + API
docker compose up --build

# API available at
http://localhost:8000

# Health check
curl http://localhost:8000/health
curl http://localhost:8000/api/ping
```

By default, the database stores data in `./data/postgres`, and uploaded files are bind mounted into `./storage`. Adjust paths in `compose.yaml` as needed.

## Configuration
Configuration values are loaded via Pydantic from environment variables and `.env`.

Important variables (see `.env`):
- `DATABASE_URL`: SQLAlchemy DSN used by the API (Compose points to the `db` service)
- `SECRET_KEY`: Flask secret for signing

The Flask app also sets:
- `STORAGE_DIR`: Where uploads are stored (defaults to `/app/storage` inside the container)
- `MAX_CONTENT_LENGTH`: Upload size cap (1 GiB by default)

## API Endpoints
Base URL when using Compose: `http://localhost:8000/api`

- `GET /ping`: Health check
- `GET /documents`: List up to 50 most recent documents
- `POST /documents`: Create a document by title (JSON)
- `POST /documents/upload`: Multipart upload of a file

Examples:

```bash
# Ping
curl http://localhost:8000/api/ping

# List documents
curl http://localhost:8000/api/documents

# Create a document by title
curl -X POST http://localhost:8000/api/documents \
  -H 'Content-Type: application/json' \
  -d '{"title": "My Note"}'

# Upload a file with optional custom title
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/path/to/file.pdf" \
  -F "title=Project Plan"
```

## Project Structure
```
apps/server/
  app/
    __init__.py          # Flask app factory
    config.py            # Pydantic-based settings
    db.py                # SQLAlchemy instance
    models.py            # ORM models (User, Document, Chunk, ...)
    ingestion.py         # Optional OCR ingestion utilities
    api/
      __init__.py        # API blueprint
      routes.py          # API endpoints
  Dockerfile             # Container image for the API

compose.yaml             # Compose stack (db + api)
.env                     # Local environment config
README.md                # This file
```

## Database
- Uses Postgres with the `pgvector` extension. On startup, the app ensures the `vector` extension exists.
- Tables are created automatically on app boot via `db.create_all()`.

## Ingestion (Optional)
The `apps/server/app/ingestion.py` module provides simple OCR-based ingestion:
- PDFs: render pages (PyMuPDF), preprocess (OpenCV), OCR (Tesseract), store chunks
- Images: preprocess and OCR into a single-page document

Dependencies (not included in the default Dockerfile/requirements):
- Python: `opencv-python`, `pytesseract`, `PyMuPDF` (fitz), `numpy`
- System: `tesseract-ocr` binary available on PATH

If you want ingestion in Docker, extend the image to install system packages and Python deps, e.g.:

```dockerfile
# Dockerfile snippet (example)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*

# requirements.txt additions
# opencv-python
# pytesseract
# PyMuPDF
# numpy
```

Note: OCR and image handling can significantly increase image size and build time. Keep it separate if you don’t need it in production.

## Development (Local, without Docker)
Prerequisites: Python 3.11, Postgres 16 with `pgvector` extension.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/server/requirements.txt

# Ensure DATABASE_URL points to your local Postgres in .env
export FLASK_APP=app:create_app
cd apps/server
gunicorn -b 127.0.0.1:8000 app:create_app()
```

## Production Notes
- Use strong `SECRET_KEY` and managed secrets
- Put a reverse proxy (e.g., Nginx) in front of Gunicorn
- Configure logging, metrics, and health endpoints for your orchestrator
- Consider migrations (Alembic) as schema evolves
- Enforce authn/z; this sample seeds/uses a default user for simplicity

## License
Proprietary or internal use by default. Add a specific license here if needed.
