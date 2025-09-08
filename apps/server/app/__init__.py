"""Flask application factory and bootstrap.

Initializes application settings, database, extensions, and registers API
blueprints. Designed to be used by Gunicorn via ``app:create_app()`` and for
local development.
"""

from flask import Flask, jsonify
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
    - Registers the API blueprint under ``/api``.
    """
    app = Flask(__name__)

    settings = Settings()
    app.config.update(
        SQLALCHEMY_DATABASE_URI=settings.database_url,  # SQLAlchemy connection string
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=settings.secret_key,          # Flask session/signing secret
        STORAGE_DIR=Path(settings.storage_dir),  # base dir for uploaded files
        MAX_CONTENT_LENGTH=1024 * 1024 * 1024,  # 1GB cap; adjust as needed
    )

    db.init_app(app)

    # Ensure pgvector + tables
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        from . import models  # noqa: F401
        db.create_all()

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/health")
    def health():
        """Simple liveness probe for container orchestrators."""
        return jsonify({"status": "ok"})

    return app
