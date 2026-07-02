"""Načítanie tabuliek z DuckDB a agregácia na dennú granularitu.

Konvencie:
- **Deň spánku (wake-day):** nočná udalosť sa priradí ku kalendárnemu dňu prebudenia.
  Realizované posunom časovej značky o +6 h a zobratím dátumu — spánok 23:00→07:00 tak
  celý spadne pod ráno prebudenia. Rovnaká konvencia platí pre spánkové fázy.
- Ostatné (kroky, stres, SpO2, HR, workouty) sa priraďujú podľa kalendárneho dňa
  ``start_time`` / ``day_time``.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

DEFAULT_DB = Path("data/health.duckdb")


def connect(db_path: str | Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path))


def _table(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    """Načítaj tabuľku ako DataFrame; prázdny DataFrame ak neexistuje."""
    exists = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchone()
    if not exists:
        return pd.DataFrame()
    return con.execute(f'SELECT * FROM "{name}"').df()


def _wake_day(ts: pd.Series) -> pd.Series:
    """Priraď nočnú časovú značku ku dňu prebudenia (posun +6 h)."""
    return (pd.to_datetime(ts) + pd.Timedelta(hours=6)).dt.normalize()


def _cal_day(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts).dt.normalize()


def daily_resting_hr(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Denný pokojový HR (proxy: min bpm) a priemerný HR."""
    df = _table(con, "heart_rate")
    if df.empty:
        return pd.DataFrame(columns=["resting_hr", "hr_avg"])
    df = df.assign(day=_cal_day(df["start_time"]))
    out = df.groupby("day").agg(resting_hr=("bpm", "min"), hr_avg=("bpm", "mean"))
    return out


def daily_steps(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _table(con, "steps_daily")
    if df.empty:
        return pd.DataFrame(columns=["steps", "active_minutes", "calories"])
    df = df.assign(day=_cal_day(df["day_time"]))
    active = df["active_time"] if "active_time" in df else 0
    df = df.assign(active_minutes=active)
    out = df.groupby("day").agg(
        steps=("steps", "sum"),
        active_minutes=("active_minutes", "sum"),
        calories=("calorie", "sum"),
    )
    return out


def nightly_sleep(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Denný spánok: minúty, efektivita, skóre, midpoint (pre regularitu)."""
    df = _table(con, "sleep")
    if df.empty:
        return pd.DataFrame(columns=["sleep_minutes", "sleep_efficiency",
                                     "sleep_score", "sleep_midpoint"])
    start = pd.to_datetime(df["start_time"])
    end = pd.to_datetime(df["end_time"])
    minutes = df["sleep_duration"].where(
        df.get("sleep_duration").notna() if "sleep_duration" in df else False,
        (end - start).dt.total_seconds() / 60,
    )
    # midpoint ako desatinné hodiny od 18:00 (kvôli prechodu cez polnoc)
    mid = start + (end - start) / 2
    midpoint_h = ((mid - mid.dt.normalize()).dt.total_seconds() / 3600 - 18) % 24
    df = df.assign(day=_wake_day(df["start_time"]), sleep_minutes=minutes,
                   sleep_midpoint=midpoint_h)
    out = df.groupby("day").agg(
        sleep_minutes=("sleep_minutes", "sum"),
        sleep_efficiency=("efficiency", "mean") if "efficiency" in df else ("sleep_minutes", "size"),
        sleep_score=("score", "max") if "score" in df else ("sleep_minutes", "size"),
        sleep_midpoint=("sleep_midpoint", "mean"),
    )
    return out


_STAGE_NAMES = {1: "awake", 2: "light", 3: "deep", 4: "rem"}


def nightly_stages(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Podiel spánkových fáz (%) na noc (deep/rem/light/awake)."""
    df = _table(con, "sleep_stage")
    cols = [f"{n}_pct" for n in _STAGE_NAMES.values()]
    if df.empty:
        return pd.DataFrame(columns=cols)
    start = pd.to_datetime(df["start_time"])
    end = pd.to_datetime(df["end_time"])
    dur = (end - start).dt.total_seconds() / 60
    df = df.assign(day=_wake_day(df["start_time"]), dur=dur,
                   stage_name=df["stage"].map(_STAGE_NAMES).fillna("light"))
    piv = df.pivot_table(index="day", columns="stage_name", values="dur",
                         aggfunc="sum", fill_value=0.0)
    total = piv.sum(axis=1).replace(0, np.nan)
    out = pd.DataFrame(index=piv.index)
    for name in _STAGE_NAMES.values():
        out[f"{name}_pct"] = (piv[name] / total * 100).round(1) if name in piv else 0.0
    return out


def daily_stress(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _table(con, "stress")
    if df.empty:
        return pd.DataFrame(columns=["stress_avg"])
    df = df.assign(day=_cal_day(df["start_time"]))
    return df.groupby("day").agg(stress_avg=("score", "mean"))


def daily_spo2(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _table(con, "spo2")
    if df.empty:
        return pd.DataFrame(columns=["spo2_min", "spo2_avg"])
    df = df.assign(day=_cal_day(df["start_time"]))
    return df.groupby("day").agg(spo2_min=("spo2", "min"), spo2_avg=("spo2", "mean"))


def body_series(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _table(con, "body_composition")
    keep = ["weight", "body_fat", "skeletal_muscle", "bmi"]
    if df.empty:
        return pd.DataFrame(columns=keep)
    df = df.assign(day=_cal_day(df["start_time"]))
    agg = {c: (c, "mean") for c in keep if c in df.columns}
    return df.groupby("day").agg(**agg)


def raw_exercise(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Surové workouty pre výpočet training load (TRIMP)."""
    return _table(con, "exercise")
