"""Testy derived metrics engine."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gen_synthetic_export as gen  # noqa: E402

from shealth.ingest import ingest_export  # noqa: E402
from shealth.metrics import build_daily_metrics  # noqa: E402
from shealth.metrics.load import acwr, daily_load, trimp  # noqa: E402
from shealth.metrics.scoring import sleep_debt  # noqa: E402


# ---- TRIMP: kontrola proti ručne dopočítanej hodnote ----
def test_trimp_known_value():
    # HRr = (150-60)/(190-60) = 0.6923; faktor = 0.64*e^(1.92*0.6923)
    hrr = (150 - 60) / (190 - 60)
    expected = 30 * hrr * (0.64 * math.exp(1.92 * hrr))
    got = trimp(mean_hr=150, duration_min=30, hr_rest=60, hr_max=190, sex="male")
    assert got == pytest.approx(expected, rel=1e-9)


def test_trimp_guards():
    assert trimp(float("nan"), 30, 60, 190) == 0.0
    assert trimp(150, 0, 60, 190) == 0.0
    assert trimp(150, 30, 190, 190) == 0.0  # nulový menovateľ


def test_trimp_monotonic_in_intensity():
    low = trimp(120, 30, 60, 190)
    high = trimp(170, 30, 60, 190)
    assert high > low > 0


# ---- ACWR ----
def test_acwr_steady_load_is_one():
    idx = pd.date_range("2024-01-01", periods=40, freq="D")
    load = pd.Series(50.0, index=idx, name="load")
    out = acwr(load, idx)
    # po nabehnutí okien je acute == chronic == 50 -> ACWR 1.0
    assert out["acwr"].iloc[-1] == pytest.approx(1.0, rel=1e-6)


def test_daily_load_sums_per_day():
    ex = pd.DataFrame({
        "start_time": ["2024-01-01 17:00:00", "2024-01-01 19:00:00", "2024-01-02 17:00:00"],
        "end_time": ["2024-01-01 17:30:00", "2024-01-01 19:30:00", "2024-01-02 18:00:00"],
        "duration": [1800_000, 1800_000, 3600_000],
        "mean_hr": [150, 140, 160],
    })
    s = daily_load(ex, hr_rest=60, hr_max=190)
    assert len(s) == 2
    assert s.iloc[0] > 0


# ---- sleep debt ----
def test_sleep_debt_accumulates_deficit():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    minutes = pd.Series([420, 420, 420, 420, 420], index=idx)  # 7h, cieľ 8h -> 60 min deficit/noc
    debt = sleep_debt(minutes, target_min=480, window=14)
    assert debt.iloc[-1] == pytest.approx(300.0)  # 5 * 60


# ---- end-to-end na syntetickom exporte ----
@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    zip_path = tmp_path_factory.mktemp("exp") / "synthetic_export.zip"
    gen.generate(zip_path, days=60, seed=11)
    db = tmp_path_factory.mktemp("db") / "health.duckdb"
    ingest_export(zip_path, db_path=db)
    return db


def test_build_daily_metrics_end_to_end(db_path: Path):
    daily = build_daily_metrics(db_path=db_path)
    assert not daily.empty
    for col in ["resting_hr", "sleep_minutes", "sleep_debt", "readiness", "acwr"]:
        assert col in daily.columns
    # readiness je v rozsahu 0-100
    r = daily["readiness"].dropna()
    assert r.between(0, 100).all()
    # metrics_daily tabuľka bola zapísaná
    import duckdb

    con = duckdb.connect(str(db_path))
    try:
        n = con.execute("SELECT count(*) FROM metrics_daily").fetchone()[0]
    finally:
        con.close()
    assert n == len(daily)


def test_stage_percentages_sum_reasonably(db_path: Path):
    daily = build_daily_metrics(db_path=db_path, write=False)
    stage_cols = [c for c in ["deep_pct", "rem_pct", "light_pct", "awake_pct"]
                  if c in daily.columns]
    assert stage_cols
    totals = daily[stage_cols].sum(axis=1).dropna()
    # noci s fázami by mali dávať ~100 %
    non_zero = totals[totals > 0]
    assert np.allclose(non_zero, 100.0, atol=1.0)
