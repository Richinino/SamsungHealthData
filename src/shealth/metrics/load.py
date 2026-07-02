"""Training load — Banister TRIMP z workoutov a akútny/chronický pomer (ACWR).

TRIMP (Training Impulse) podľa Banistera::

    HRr    = (HR_ex - HR_rest) / (HR_max - HR_rest)          # frakcia rezervy, [0,1]
    faktor = 0.64 * e^(1.92 * HRr)   (muž)  |  0.86 * e^(1.67 * HRr)  (žena)
    TRIMP  = trvanie_min * HRr * faktor

ACWR (acute:chronic workload ratio) = 7-dňový priemer / 28-dňový priemer denného load.
Sladké pásmo je zhruba 0.8–1.3; hodnoty výrazne nad 1.5 signalizujú riziko prepätia.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def trimp(mean_hr: float, duration_min: float, hr_rest: float, hr_max: float,
          sex: str = "male") -> float:
    """Banister TRIMP pre jeden workout. Vracia 0 pri neúplných vstupoch."""
    if not np.isfinite(mean_hr) or not np.isfinite(duration_min) or duration_min <= 0:
        return 0.0
    denom = hr_max - hr_rest
    if denom <= 0:
        return 0.0
    hrr = float(np.clip((mean_hr - hr_rest) / denom, 0.0, 1.0))
    if sex == "female":
        factor = 0.86 * np.exp(1.67 * hrr)
    else:
        factor = 0.64 * np.exp(1.92 * hrr)
    return float(duration_min * hrr * factor)


def _pick(df: pd.DataFrame, *candidates: str) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def daily_load(exercise: pd.DataFrame, hr_rest: float, hr_max: float,
               sex: str = "male") -> pd.Series:
    """Súčet TRIMP na deň (index = deň, hodnota = load). Prázdna séria ak niet dát."""
    tcol = _pick(exercise, "start_time", "create_time", "time")
    if exercise.empty or tcol is None:
        return pd.Series(dtype="float64", name="load")
    ex = exercise.copy()
    start = pd.to_datetime(ex[tcol], errors="coerce")
    day = start.dt.normalize()
    # trvanie: exercise.duration býva v ms; fallback na (end-start)
    dcol = _pick(ex, "duration")
    ecol = _pick(ex, "end_time")
    if dcol and ex[dcol].notna().any():
        dur_min = pd.to_numeric(ex[dcol], errors="coerce") / 1000 / 60
    elif ecol:
        dur_min = (pd.to_datetime(ex[ecol], errors="coerce") - start).dt.total_seconds() / 60
    else:
        dur_min = pd.Series(0.0, index=ex.index)
    hrcol = _pick(ex, "mean_hr", "mean_heart_rate", "heart_rate")
    mean_hr = pd.to_numeric(ex[hrcol], errors="coerce") if hrcol else pd.Series(np.nan, index=ex.index)
    loads = [
        trimp(h, d, hr_rest, hr_max, sex)
        for h, d in zip(mean_hr.to_numpy(), dur_min.to_numpy())
    ]
    s = pd.Series(loads, index=day).groupby(level=0).sum()
    s.name = "load"
    return s


def acwr(daily_load_series: pd.Series, full_index: pd.DatetimeIndex,
         acute: int = 7, chronic: int = 28) -> pd.DataFrame:
    """Doplň dni bez tréningu nulami a spočítaj acute/chronic load a ACWR.

    Returns:
        DataFrame so stĺpcami ``load``, ``load_acute``, ``load_chronic``, ``acwr``.
    """
    load = daily_load_series.reindex(full_index, fill_value=0.0)
    load.name = "load"
    out = load.to_frame()
    out["load_acute"] = load.rolling(acute, min_periods=1).mean()
    out["load_chronic"] = load.rolling(chronic, min_periods=1).mean()
    out["acwr"] = (out["load_acute"] / out["load_chronic"]).replace([np.inf, -np.inf], np.nan)
    return out
