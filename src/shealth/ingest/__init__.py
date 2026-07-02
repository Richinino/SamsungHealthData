"""Ingest: rozbalenie exportu, parsovanie CSV/JSON a načítanie do DuckDB."""

from shealth.ingest.load import ingest_export

__all__ = ["ingest_export"]
