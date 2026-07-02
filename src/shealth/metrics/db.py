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


def _table_any(con: duckdb.DuckDBPyConnection, *names: str) -> pd.DataFrame:
    """Vráť prvú existujúcu neprázdnu tabuľku z uvedených názvov.

    Reálny Samsung export drží dáta v iných tabuľkách než syntetické (napr. sumár
    spánku v ``sleep_combined``, telesné zloženie vo ``weight``) — uprednostníme
    reálne názvy a spadneme na syntetické.
    """
    for name in names:
        df = _table(con, name)
        if not df.empty:
            return df
    return pd.DataFrame()


def _wake_day(ts: pd.Series) -> pd.Series:
    """Priraď nočnú časovú značku ku dňu prebudenia (posun +6 h)."""
    return (pd.to_datetime(ts, errors="coerce") + pd.Timedelta(hours=6)).dt.normalize()


def _cal_day(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts, errors="coerce").dt.normalize()


# kandidáti na časový stĺpec — reálne exporty používajú rôzne názvy
_TIME_CANDIDATES = ("start_time", "create_time", "day_time", "time", "start", "update_time")


def _pick(df: pd.DataFrame, *candidates: str) -> str | None:
    """Vráť prvý existujúci stĺpec z kandidátov (alebo None)."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _time_col(df: pd.DataFrame) -> str | None:
    return _pick(df, *_TIME_CANDIDATES)


def daily_resting_hr(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Denný pokojový HR (proxy: min bpm) a priemerný HR."""
    df = _table(con, "heart_rate")
    tcol = _time_col(df)
    vcol = _pick(df, "bpm", "heart_rate", "value")
    if df.empty or tcol is None or vcol is None:
        return pd.DataFrame(columns=["resting_hr", "hr_avg"])
    df = df.assign(day=_cal_day(df[tcol]), _v=pd.to_numeric(df[vcol], errors="coerce"))
    df = df.dropna(subset=["day", "_v"])
    return df.groupby("day").agg(resting_hr=("_v", "min"), hr_avg=("_v", "mean"))


def daily_steps(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    # reálny denný sumár je v activity_day_summary / step_daily_trend; fallback steps_daily
    df = _table_any(con, "activity_day_summary", "step_daily_trend", "steps_daily")
    tcol = _time_col(df)
    scol = _pick(df, "steps", "step_count", "count")
    if df.empty or tcol is None or scol is None:
        return pd.DataFrame(columns=["steps", "active_minutes", "calories"])
    acol = _pick(df, "active_time", "active_minutes")
    ccol = _pick(df, "calorie", "calories")
    df = df.assign(
        day=_cal_day(df[tcol]),
        _steps=pd.to_numeric(df[scol], errors="coerce"),
        _active=pd.to_numeric(df[acol], errors="coerce") if acol else 0,
        _cal=pd.to_numeric(df[ccol], errors="coerce") if ccol else 0,
    ).dropna(subset=["day"])
    # denné sumáre môžu mať viac riadkov/deň (viac zdrojov) — ber maximum, nie súčet
    return df.groupby("day").agg(
        steps=("_steps", "max"), active_minutes=("_active", "max"), calories=("_cal", "max"))


def nightly_sleep(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Denný spánok: minúty, efektivita, skóre, midpoint (pre regularitu)."""
    # reálny sumár spánku je v sleep_combined (má start_time, sleep_score, efficiency)
    df = _table_any(con, "sleep_combined", "sleep")
    tcol = _pick(df, "start_time", "create_time", "time")
    ecol = _pick(df, "end_time")
    if df.empty or tcol is None:
        return pd.DataFrame(columns=["sleep_minutes", "sleep_efficiency",
                                     "sleep_score", "sleep_midpoint"])
    start = pd.to_datetime(df[tcol], errors="coerce")
    end = pd.to_datetime(df[ecol], errors="coerce") if ecol else start
    span_min = (end - start).dt.total_seconds() / 60
    dcol = _pick(df, "sleep_duration", "duration")
    if dcol:
        dur = pd.to_numeric(df[dcol], errors="coerce")
        # duration býva v minútach; ak vyzerá ako ms, preveď
        dur = dur.where(dur < 1000, dur / 60000)
        minutes = dur.fillna(span_min)
    else:
        minutes = span_min
    mid = start + (end - start) / 2
    midpoint_h = ((mid - mid.dt.normalize()).dt.total_seconds() / 3600 - 18) % 24
    eff_col = _pick(df, "efficiency")
    score_col = _pick(df, "score", "sleep_score")
    df = df.assign(day=_wake_day(start), _min=minutes, _mid=midpoint_h,
                   _eff=pd.to_numeric(df[eff_col], errors="coerce") if eff_col else np.nan,
                   _score=pd.to_numeric(df[score_col], errors="coerce") if score_col else np.nan)
    df = df.dropna(subset=["day"])
    return df.groupby("day").agg(
        sleep_minutes=("_min", "sum"), sleep_efficiency=("_eff", "mean"),
        sleep_score=("_score", "max"), sleep_midpoint=("_mid", "mean"))


# Samsung kóduje spánkové fázy dvoma schémami — staré 1–4 aj novšie 40001–40004
_STAGE_NAMES = {
    1: "awake", 2: "light", 3: "deep", 4: "rem",
    40001: "awake", 40002: "light", 40003: "deep", 40004: "rem",
}


def nightly_stages(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Podiel spánkových fáz (%) na noc (deep/rem/light/awake)."""
    df = _table(con, "sleep_stage")
    cols = [f"{n}_pct" for n in _STAGE_NAMES.values()]
    tcol = _pick(df, "start_time", "create_time", "time")
    scol = _pick(df, "stage")
    if df.empty or tcol is None or scol is None:
        return pd.DataFrame(columns=cols)
    start = pd.to_datetime(df[tcol], errors="coerce")
    ecol = _pick(df, "end_time")
    end = pd.to_datetime(df[ecol], errors="coerce") if ecol else start
    dur = (end - start).dt.total_seconds() / 60
    df = df.assign(day=_wake_day(start), dur=dur,
                   stage_name=pd.to_numeric(df[scol], errors="coerce").map(_STAGE_NAMES).fillna("light"))
    df = df.dropna(subset=["day"])
    piv = df.pivot_table(index="day", columns="stage_name", values="dur",
                         aggfunc="sum", fill_value=0.0)
    total = piv.sum(axis=1).replace(0, np.nan)
    out = pd.DataFrame(index=piv.index)
    for name in _STAGE_NAMES.values():
        out[f"{name}_pct"] = (piv[name] / total * 100).round(1) if name in piv else 0.0
    return out


def daily_stress(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _table(con, "stress")
    tcol = _time_col(df)
    scol = _pick(df, "score", "value")
    if df.empty or tcol is None or scol is None:
        return pd.DataFrame(columns=["stress_avg"])
    df = df.assign(day=_cal_day(df[tcol]), _v=pd.to_numeric(df[scol], errors="coerce"))
    df = df.dropna(subset=["day", "_v"])
    return df.groupby("day").agg(stress_avg=("_v", "mean"))


def daily_spo2(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _table(con, "spo2")
    tcol = _time_col(df)
    scol = _pick(df, "spo2", "oxygen_saturation", "value")
    if df.empty or tcol is None or scol is None:
        return pd.DataFrame(columns=["spo2_min", "spo2_avg"])
    df = df.assign(day=_cal_day(df[tcol]), _v=pd.to_numeric(df[scol], errors="coerce"))
    df = df.dropna(subset=["day", "_v"])
    return df.groupby("day").agg(spo2_min=("_v", "min"), spo2_avg=("_v", "mean"))


def body_series(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    # reálne telesné zloženie je v tabuľke weight (body_fat, skeletal_muscle, …)
    df = _table_any(con, "weight", "body_composition")
    keep = ["weight", "body_fat", "skeletal_muscle", "muscle_mass", "bmi"]
    tcol = _time_col(df)
    if df.empty or tcol is None:
        return pd.DataFrame(columns=keep)
    df = df.assign(day=_cal_day(df[tcol]))
    for c in keep:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["day"])
    agg = {c: (c, "mean") for c in keep if c in df.columns}
    if not agg:
        return pd.DataFrame(columns=keep)
    return df.groupby("day").agg(**agg)


def raw_exercise(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Surové workouty pre výpočet training load (TRIMP)."""
    return _table(con, "exercise")
