"""Diagnostika reálnych dát — ukáž formáty časových stĺpcov a hodnôt v kľúčových tabuľkách.

Použitie:  uv run python scripts/diagnose.py
Výstup pošli asistentovi — z neho presne domapuje parsovanie.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from shealth.metrics.db import _to_dt  # noqa: E402

DB = sys.argv[1] if len(sys.argv) > 1 else "data/health.duckdb"

CHECKS = [
    ("sleep_combined", ["start_time", "end_time", "sleep_duration", "sleep_score", "efficiency"]),
    ("activity_day_summary", ["create_time", "start_time", "step_count", "active_time", "calorie"]),
    ("sleep_stage", ["start_time", "stage"]),
    ("weight", ["update_time", "create_time", "weight", "body_fat", "skeletal_muscle"]),
    ("heart_rate", ["start_time", "end_time", "heart_rate", "bpm", "max", "binning_data"]),
    ("exercise", ["start_time", "duration", "mean_hr", "calorie"]),
    ("stress", ["start_time", "create_time", "score", "max", "min", "binning_data"]),
    ("vitality_score", ["day_time", "total_score", "sleep_score", "max_hr"]),
]


def short(v: object) -> str:
    s = str(v)
    return s if len(s) <= 80 else s[:80] + "…"


def main() -> None:
    con = duckdb.connect(DB)
    for table, cols in CHECKS:
        try:
            df = con.execute(f'SELECT * FROM "{table}"').df()
        except Exception as e:  # noqa: BLE001
            print(f"\n### {table}: CHÝBA ({e})")
            continue
        present = [c for c in cols if c in df.columns]
        print(f"\n### {table}: {len(df)} riadkov; z hľadaných prítomné: {present}")
        for c in present:
            vals = [short(x) for x in df[c].dropna().head(3).tolist()]
            print(f"   {c!r}: {vals}")
        for tc in ("start_time", "create_time", "update_time", "day_time", "end_time"):
            if tc in df.columns:
                parsed = _to_dt(df[tc])
                sample = [str(x) for x in parsed.dropna().head(2).tolist()]
                print(f"   -> _to_dt({tc}): naparsovaných {parsed.notna().sum()}/{len(df)}; {sample}")
                break
    con.close()


if __name__ == "__main__":
    main()
