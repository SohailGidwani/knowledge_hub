"""API package initialization.

Exposes a Flask ``Blueprint`` named ``api_bp`` used by the application factory
to register all API routes under the ``/api`` prefix.
"""

from flask import Blueprint

# Lightweight blueprint; routes are registered in ``routes.py``.
api_bp = Blueprint("api", __name__)
