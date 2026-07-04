"""FastAPI backend — servuje dashboard a /api dáta z DuckDB."""

from shealth.api.app import create_app

__all__ = ["create_app"]
