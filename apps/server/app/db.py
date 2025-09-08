"""Database extension instance.

Holds a global ``SQLAlchemy`` object that is initialized in the application
factory. Import this as ``from .db import db`` across the codebase.
"""

from flask_sqlalchemy import SQLAlchemy

# Global SQLAlchemy handle; initialized via ``db.init_app(app)`` in create_app().
db = SQLAlchemy()
