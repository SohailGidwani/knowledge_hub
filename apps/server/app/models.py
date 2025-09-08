"""SQLAlchemy ORM models for Knowledge Hub.

Defines core entities: ``User``, ``Document``, ``Chunk``, ``Embedding``,
``Tag`` and the junction table ``DocumentTag``. Relationships are configured
with cascading deletes for dependent records to keep the database tidy.
"""

from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from .db import db


class User(db.Model):
    """Represents an end user/owner of documents."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to Document: A user can have multiple documents.
    # 'cascade="all,delete-orphan"' ensures that documents are deleted if the user is deleted.
    documents = relationship("Document", back_populates="user", cascade="all,delete-orphan")


class Document(db.Model):
    """A document uploaded/registered by a user.

    Stores source path, MIME metadata, size/hash, and processing status.
    """
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to User model.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(512), nullable=False)
    source_path = db.Column(db.String(1024), nullable=True)  # Path to the original file (e.g., /app/storage/...).
    mime_type = db.Column(db.String(128), nullable=True)
    pages = db.Column(db.Integer, nullable=True)
    bytes = db.Column(db.BigInteger, nullable=True)
    hash_sha256 = db.Column(db.String(64), nullable=True, index=True)
    # Status of the document processing (e.g., "ready", "processing", "error").
    status = db.Column(db.String(32), default="ready", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to User: A document belongs to one user.
    user = relationship("User", back_populates="documents")
    # Relationship to Chunk: A document can have multiple chunks.
    # 'cascade="all,delete-orphan"' ensures that chunks are deleted if the document is deleted.
    chunks = relationship("Chunk", back_populates="document", cascade="all,delete-orphan")


class Chunk(db.Model):
    """A segment of a document (e.g., page section or table)."""
    __tablename__ = "chunks"
    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to Document model.
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)

    version = db.Column(db.Integer, default=1, nullable=False)
    page_no = db.Column(db.Integer, nullable=True)
    chunk_index = db.Column(db.Integer, nullable=True)

    text = db.Column(db.Text, nullable=True)
    tokens = db.Column(db.Integer, nullable=True)
    # Modality of the chunk (e.g., "text", "table", "image").
    modality = db.Column(db.String(32), default="text", nullable=False)
    # Bounding box for visual elements {x,y,w,h}.
    bbox = db.Column(JSONB, nullable=True)
    extra_json = db.Column(JSONB, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to Document: A chunk belongs to one document.
    document = relationship("Document", back_populates="chunks")
    # Relationship to Embedding: A chunk can have multiple embeddings.
    # 'cascade="all,delete-orphan"' ensures that embeddings are deleted if the chunk is deleted.
    embeddings = relationship("Embedding", back_populates="chunk", cascade="all,delete-orphan")


class Embedding(db.Model):
    """Vector embedding for a chunk (model + dimension + vector)."""
    __tablename__ = "embeddings"
    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to Chunk model.
    chunk_id = db.Column(db.Integer, db.ForeignKey("chunks.id"), nullable=False)

    model = db.Column(db.String(128), nullable=False)
    dim = db.Column(db.Integer, nullable=False)
    # Vector column for storing embeddings. 'dim' should match the embedding model's dimension.
    vector = db.Column(Vector(dim=768))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to Chunk: An embedding belongs to one chunk.
    chunk = relationship("Chunk", back_populates="embeddings")


class Tag(db.Model):
    """Simple tag used to label documents."""
    __tablename__ = "tags"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)


class DocumentTag(db.Model):
    """Junction table for many-to-many Document–Tag relationships."""
    __tablename__ = "document_tags"
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), primary_key=True)
