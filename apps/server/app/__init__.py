"""Flask application factory and bootstrap.

Initializes application settings, database, extensions, and registers API
blueprints. Designed to be used by Gunicorn via ``app:create_app()`` and for
local development.
"""

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text
from pathlib import Path

from .config import Settings
from .db import db
from .api.routes import api_bp
# from .models import User  # only needed if you seed at startup


def create_app():
    """Create and configure a Flask app instance.

    - Loads settings from ``Settings`` and applies them to ``app.config``.
    - Initializes the SQLAlchemy extension.
    - Ensures the ``vector`` extension exists and creates tables.
    - Creates helpful indexes (FTS + IVFFlat).
    - Registers the API blueprint under ``/api``.
    """
    app = Flask(__name__)
    # Allow the Next.js dev server to call the API during development
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    settings = Settings()
    app.config.update(
        SQLALCHEMY_DATABASE_URI=settings.database_url,   # SQLAlchemy connection string
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=settings.secret_key,                  # Flask session/signing secret
        STORAGE_DIR=Path(settings.storage_dir),          # base dir for uploaded files
        MAX_CONTENT_LENGTH=1024 * 1024 * 1024,           # 1GB cap; adjust as needed
        EMBEDDINGS_BATCH_SIZE=int(getattr(settings, "embeddings_batch_size", 128)),
    )

    db.init_app(app)

    # Ensure pgvector + tables + indexes
    with app.app_context():
        with db.engine.connect() as conn:
            # 1) pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

        # 2) Create tables
        from . import models  # noqa: F401 (register models)
        db.create_all()

        # 3) Create indexes (safe if run multiple times)
        with db.engine.connect() as conn:
            # Ensure embeddings.vector has correct dimension (384) matching MiniLM
            # Safe to attempt; ignore if already correct or table doesn't exist yet
            try:
                conn.execute(text("ALTER TABLE embeddings ALTER COLUMN vector TYPE vector(384)"))
                conn.commit()
            except Exception:
                pass

            # FTS GIN index on chunks.text
            conn.execute(text(
                """
                CREATE INDEX IF NOT EXISTS chunks_fts_idx
                ON chunks USING GIN (to_tsvector('english', coalesce(text, '')));
                """
            ))

            # IVFFlat index on embeddings.vector for scalable ANN search.
            # 'lists' controls the coarse quantization buckets. Tune as data grows.
            conn.execute(text(
                """
                CREATE INDEX IF NOT EXISTS embeddings_vec_idx
                ON embeddings USING ivfflat (vector) WITH (lists = 100);
                """
            ))
            conn.commit()

            # Optional but recommended: analyze so the planner has stats,
            # especially after bulk inserts of embeddings.
            conn.execute(text("ANALYZE embeddings;"))
            conn.execute(text("ANALYZE chunks;"))
            conn.commit()

    # API routes
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/health")
    def health():
        """Simple liveness probe for container orchestrators."""
        return jsonify({"status": "ok"})

    return app
