"""Jednoduché CLI: ingest exportu a rýchly prehľad databázy."""

from __future__ import annotations

import argparse
from pathlib import Path

from shealth.ingest import ingest_export


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shealth", description="Samsung Health dashboard toolkit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="Načítaj export (zip/priečinok) do DuckDB")
    p_ing.add_argument("source", type=Path, help="cesta k export.zip alebo priečinku")
    p_ing.add_argument("--db", type=Path, default=Path("data/health.duckdb"))

    args = ap.parse_args(argv)

    if args.cmd == "ingest":
        report = ingest_export(args.source, db_path=args.db)
        print(report)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
