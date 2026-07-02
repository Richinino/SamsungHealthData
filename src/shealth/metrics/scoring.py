"""Odvodené skóre — sleep debt, sleep regularity a kompozitné readiness skóre.

Všetky vzorce sú **transparentné** (žiadna čierna skrinka). Readiness (0–100) je vážený
priemer čiastkových zložiek; každá zložka je normalizovaná na 0–100 (vyššie = lepšie).
Chýbajúce zložky sa vynechajú a váhy sa prenormujú.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: váhy zložiek readiness (sčítajú sa na 1.0)
READINESS_WEIGHTS = {
    "rhr_score": 0.30,     # pokojový HR vs. osobný baseline
    "sleep_score_c": 0.35, # kvalita/dĺžka spánku
    "stress_score": 0.20,  # nižší stres = lepšie
    "acwr_score": 0.15,    # tréningová záťaž v sladkom pásme
}


def _clip(x, lo=0.0, hi=100.0):
    return np.clip(x, lo, hi)


def sleep_debt(sleep_minutes: pd.Series, target_min: float = 480.0,
               window: int = 14) -> pd.Series:
    """Kumulatívny sleep debt (min) za posledných ``window`` nocí (signed).

    Kladná hodnota = nahromadený deficit oproti cieľu; záporná = prebytok.
    """
    deficit = target_min - sleep_minutes
    return deficit.rolling(window, min_periods=1).sum()


def sleep_regularity(midpoint_hours: pd.Series, window: int = 7) -> pd.Series:
    """Smerodajná odchýlka stredu spánku (h) za okno — nižšia = pravidelnejšie."""
    return midpoint_hours.rolling(window, min_periods=3).std()


def _rhr_score(rhr: pd.Series, baseline: pd.Series) -> pd.Series:
    # každý bpm pod baseline = +4 body, nad = -4 body, stred 50
    return _clip(50 + (baseline - rhr) * 4)


def _sleep_component(df: pd.DataFrame, target_min: float) -> pd.Series | None:
    if "sleep_score" in df and df["sleep_score"].notna().any():
        return _clip(df["sleep_score"])
    if "sleep_minutes" in df and df["sleep_minutes"].notna().any():
        return _clip(df["sleep_minutes"] / target_min * 100)
    return None


def _stress_component(df: pd.DataFrame) -> pd.Series | None:
    if "stress_avg" in df and df["stress_avg"].notna().any():
        return _clip(100 - df["stress_avg"])
    return None


def _acwr_component(df: pd.DataFrame) -> pd.Series | None:
    if "acwr" not in df or not df["acwr"].notna().any():
        return None
    a = df["acwr"]
    # sladké pásmo 0.8–1.3 = 100; penalizuj podtrénovanie aj prepätie
    under = np.maximum(0.0, 0.8 - a) * 250
    over = np.maximum(0.0, a - 1.3) * 120
    return _clip(100 - under - over)


def compute_readiness(df: pd.DataFrame, target_sleep_min: float = 480.0,
                      rhr_baseline_window: int = 30) -> pd.DataFrame:
    """Doplň do ``df`` zložky a stĺpec ``readiness`` (0–100).

    Očakáva denne indexovaný DataFrame so stĺpcami (podľa dostupnosti):
    ``resting_hr``, ``sleep_score``/``sleep_minutes``, ``stress_avg``, ``acwr``.
    """
    df = df.copy()

    if "resting_hr" in df and df["resting_hr"].notna().any():
        baseline = df["resting_hr"].rolling(rhr_baseline_window, min_periods=3).median()
        baseline = baseline.bfill()
        df["rhr_baseline"] = baseline
        df["rhr_score"] = _rhr_score(df["resting_hr"], baseline)

    sleep_c = _sleep_component(df, target_sleep_min)
    if sleep_c is not None:
        df["sleep_score_c"] = sleep_c
    stress_c = _stress_component(df)
    if stress_c is not None:
        df["stress_score"] = stress_c
    acwr_c = _acwr_component(df)
    if acwr_c is not None:
        df["acwr_score"] = acwr_c

    # vážený priemer dostupných zložiek (prenormované váhy)
    present = [c for c in READINESS_WEIGHTS if c in df.columns]
    if present:
        wsum = sum(READINESS_WEIGHTS[c] for c in present)
        readiness = sum(df[c] * (READINESS_WEIGHTS[c] / wsum) for c in present)
        df["readiness"] = readiness.round(1)
    return df
