"""Module-level upload registry — maps file_id (UUID str) to absolute upload path.
upload.py writes here on save; process.py reads here to resolve file_id -> path.
Singleton — never re-instantiate in routes.
"""
from __future__ import annotations

UPLOAD_REGISTRY: dict[str, str] = {}
