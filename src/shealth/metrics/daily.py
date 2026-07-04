"""Zostavenie dennej tabuľky metrík ``metrics_daily`` a zápis do DuckDB."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from shealth.metrics import db
from shealth.metrics.load import acwr, daily_load
from shealth.metrics.scoring import compute_readiness, sleep_debt, sleep_regularity


@dataclass
class MetricParams:
    """Parametre výpočtu (transparentné, upraviteľné podľa profilu)."""

    sex: str = "male"
    hr_max: float = 190.0            # ak nepoznáš, ~ 220 - vek
    hr_rest: float | None = None     # None = odvoď z dát (medián pokojového HR)
    target_sleep_min: float = 480.0  # cieľ spánku (min) = 8 h
    acute_days: int = 7
    chronic_days: int = 28
    rhr_baseline_window: int = 30
    sleep_debt_window: int = 14
    regularity_window: int = 7


DEFAULT_PARAMS = MetricParams()


def build_daily_metrics(
    db_path: str | Path = db.DEFAULT_DB,
    params: MetricParams = DEFAULT_PARAMS,
    write: bool = True,
) -> pd.DataFrame:
    """Zostav dennú tabuľku odvodených metrík a (voliteľne) zapíš ju do DuckDB.

    Returns:
        DataFrame indexovaný dňom so surovými aj odvodenými metrikami.
    """
    con = db.connect(db_path)
    try:
        rhr = db.daily_resting_hr(con)
        steps = db.daily_steps(con)
        sleep = db.nightly_sleep(con)
        stages = db.nightly_stages(con)
        stress = db.daily_stress(con)
        spo2 = db.daily_spo2(con)
        body = db.body_series(con)
        exercise = db.raw_exercise(con)

        # zjednotený denný index cez celé rozpätie dostupných dát
        frames = [rhr, steps, sleep, stages, stress, spo2, body]
        idx = _union_index(frames)
        daily = pd.DataFrame(index=idx)
        for f in frames:
            if not f.empty:
                daily = daily.join(f, how="left")

        # pokojový HR pre TRIMP: parameter, inak medián z dát
        hr_rest = params.hr_rest
        if hr_rest is None and "resting_hr" in daily and daily["resting_hr"].notna().any():
            hr_rest = float(daily["resting_hr"].median())
        hr_rest = hr_rest if hr_rest else 60.0

        # training load + ACWR
        load_series = daily_load(exercise, hr_rest, params.hr_max, params.sex)
        load_df = acwr(load_series, idx, params.acute_days, params.chronic_days)
        daily = daily.join(load_df, how="left")

        # sleep debt + regularita
        if "sleep_minutes" in daily:
            daily["sleep_debt"] = sleep_debt(
                daily["sleep_minutes"], params.target_sleep_min, params.sleep_debt_window)
        if "sleep_midpoint" in daily:
            daily["sleep_regularity"] = sleep_regularity(
                daily["sleep_midpoint"], params.regularity_window)

        # body-composition delta (zmena hmotnosti za 7/30 dní)
        if "weight" in daily:
            w = daily["weight"].ffill()
            daily["weight_ffill"] = w
            daily["weight_delta_7d"] = w - w.shift(7)
            daily["weight_delta_30d"] = w - w.shift(30)

        # readiness skóre
        daily = compute_readiness(
            daily, params.target_sleep_min, params.rhr_baseline_window)

        daily.index.name = "day"
        if write:
            _write_metrics(con, daily)
        return daily
    finally:
        con.close()


def _union_index(frames: list[pd.DataFrame]) -> pd.DatetimeIndex:
    days = [f.index for f in frames if not f.empty]
    if not days:
        return pd.DatetimeIndex([], name="day")
    lo = min(d.min() for d in days)
    hi = max(d.max() for d in days)
    return pd.date_range(lo, hi, freq="D")


def _write_metrics(con, daily: pd.DataFrame) -> None:
    out = daily.reset_index()
    con.register("metrics_tmp", out)
    try:
        con.execute('CREATE OR REPLACE TABLE "metrics_daily" AS SELECT * FROM metrics_tmp')
    finally:
        con.unregister("metrics_tmp")
