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

    p_met = sub.add_parser("metrics", help="Vypočítaj odvodené denné metriky do DuckDB")
    p_met.add_argument("--db", type=Path, default=Path("data/health.duckdb"))
    p_met.add_argument("--sex", choices=["male", "female"], default="male")
    p_met.add_argument("--hr-max", type=float, default=190.0)
    p_met.add_argument("--target-sleep-min", type=float, default=480.0)
    p_met.add_argument("--tail", type=int, default=7, help="koľko posledných dní vypísať")

    p_srv = sub.add_parser("serve", help="Spusti dashboard (FastAPI + zbuildený frontend)")
    p_srv.add_argument("--db", type=Path, default=Path("data/health.duckdb"))
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8000)

    args = ap.parse_args(argv)

    if args.cmd == "ingest":
        report = ingest_export(args.source, db_path=args.db)
        print(report)
        return 0
    if args.cmd == "metrics":
        from shealth.metrics import MetricParams, build_daily_metrics

        params = MetricParams(sex=args.sex, hr_max=args.hr_max,
                              target_sleep_min=args.target_sleep_min)
        daily = build_daily_metrics(db_path=args.db, params=params)
        cols = [c for c in ["resting_hr", "sleep_minutes", "sleep_debt", "stress_avg",
                            "load", "acwr", "readiness"] if c in daily.columns]
        print(f"metrics_daily: {len(daily)} dní zapísaných do {args.db}")
        print(daily[cols].tail(args.tail).round(1).to_string())
        return 0
    if args.cmd == "serve":
        import os

        import uvicorn

        os.environ["SHEALTH_DB"] = str(args.db)
        print(f"Dashboard: http://{args.host}:{args.port}  (DB: {args.db})")
        uvicorn.run("shealth.api.app:app", host=args.host, port=args.port)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
