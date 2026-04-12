"""Module-level job registry — singleton, never re-instantiate."""
from __future__ import annotations

JOB_REGISTRY: dict[str, dict] = {}
