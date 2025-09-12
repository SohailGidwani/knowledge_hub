"""Configuration management using Pydantic settings.

Loads values from environment variables (and ``.env`` in development) and
exposes a typed ``Settings`` object used by the Flask app.
"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application configuration.

    Fields can be overridden via environment variables. See ``.env`` for
    examples and defaults used in local development.
    """
    database_url: str = "postgresql+psycopg2://khub:khubpassword@localhost:5432/knowledgehub"
    secret_key: str = "devsecret"
    storage_dir: Path = Path("/app/storage")
    # Embedding job batch size (controls memory usage)
    embeddings_batch_size: int = 128

    class Config:
        """Pydantic config: load variables from a ``.env`` file if present."""
        env_file = ".env"
