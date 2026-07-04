"""Dátové dopyty pre dashboard — číta ``metrics_daily`` a surové tabuľky z DuckDB.

Ak ``metrics_daily`` neexistuje, dopočíta sa za behu cez :func:`build_daily_metrics`.
Všetky výstupy sú JSON-safe (NaN/NaT → None).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from shealth.metrics import DEFAULT_PARAMS, build_daily_metrics
from shealth.metrics.load import trimp

DEFAULT_DB = Path("data/health.duckdb")

# kódy cvičení Samsung → čitateľný názov (rozšíriteľné)
EXERCISE_NAMES = {
    1001: "Chôdza", 1002: "Beh", 11007: "Bicykel", 13001: "Túra",
    14001: "Plávanie", 15006: "Posilňovňa", 0: "Tréning",
}

# poradie a metadáta KPI dlaždíc
KPI_SPEC = [
    ("resting_hr", "Pokojový HR", "bpm", "lower"),
    ("sleep_minutes", "Spánok", "h", "higher"),
    ("steps", "Kroky", "", "higher"),
    ("load", "Tréning. záťaž", "TRIMP", "neutral"),
    ("stress_avg", "Stres", "", "lower"),
    ("readiness", "Readiness", "", "higher"),
]


def _clean(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if v is pd.NaT:
        return None
    return v


def _records(df: pd.DataFrame) -> list[dict]:
    out = df.where(pd.notna(df), None)
    return [{k: _clean(v) for k, v in row.items()} for row in out.to_dict("records")]


class HealthData:
    """Tenká vrstva nad DuckDB s cache-ovaným ``metrics_daily``."""

    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = Path(db_path)
        self._metrics: pd.DataFrame | None = None

    def metrics(self) -> pd.DataFrame:
        if self._metrics is None:
            self._metrics = self._load_metrics()
        return self._metrics

    def _load_metrics(self) -> pd.DataFrame:
        con = duckdb.connect(str(self.db_path))
        try:
            has = con.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name='metrics_daily'"
            ).fetchone()
            if has:
                df = con.execute("SELECT * FROM metrics_daily ORDER BY day").df()
                df["day"] = pd.to_datetime(df["day"])
                return df.set_index("day")
        finally:
            con.close()
        # dopočítaj, ak chýba
        return build_daily_metrics(self.db_path, DEFAULT_PARAMS, write=True)

    def _range(self, df: pd.DataFrame, rng: str) -> pd.DataFrame:
        if df.empty or rng == "all":
            return df
        days = {"7d": 7, "30d": 30, "90d": 90}.get(rng, 30)
        cutoff = df.index.max() - pd.Timedelta(days=days - 1)
        return df[df.index >= cutoff]

    # ---- endpoints ----
    def summary(self, rng: str = "30d") -> dict:
        m = self.metrics()
        if m.empty:
            return {"empty": True}
        win = self._range(m, rng)
        last = m.iloc[-1]
        kpis = []
        for col, label, unit, better in KPI_SPEC:
            if col not in m.columns:
                continue
            series = win[col].dropna()
            spark = [round(float(x), 2) for x in series.tail(14).tolist()]
            val = _clean(float(last[col])) if pd.notna(last.get(col)) else None
            prev = series.iloc[-8] if len(series) >= 8 else (series.iloc[0] if len(series) else None)
            delta = _clean(float(last[col] - prev)) if (val is not None and prev is not None) else None
            kpis.append({"key": col, "label": label, "unit": unit, "better": better,
                         "value": val, "delta": delta, "spark": spark})
        comps = {k: _clean(float(last[k])) for k in
                 ["rhr_score", "sleep_score_c", "stress_score", "acwr_score"]
                 if k in m.columns and pd.notna(last.get(k))}
        return {
            "empty": False,
            "as_of": str(m.index.max().date()),
            "readiness": _clean(float(last["readiness"])) if "readiness" in m else None,
            "components": comps,
            "kpis": kpis,
        }

    def timeseries(self, rng: str = "30d") -> dict:
        m = self._range(self.metrics(), rng).copy()
        if m.empty:
            return {"days": []}
        # spánkové fázy v hodinách
        for stage in ["deep", "rem", "light", "awake"]:
            pc = f"{stage}_pct"
            if pc in m.columns and "sleep_minutes" in m.columns:
                m[f"{stage}_h"] = m[pc] / 100 * m["sleep_minutes"] / 60
        m = m.reset_index()
        m["day"] = m["day"].dt.strftime("%Y-%m-%d")
        cols = [c for c in [
            "day", "readiness", "resting_hr", "rhr_baseline", "hr_avg",
            "sleep_minutes", "sleep_debt", "sleep_score", "sleep_regularity",
            "deep_h", "rem_h", "light_h", "awake_h",
            "stress_avg", "spo2_min", "steps",
            "load", "load_acute", "load_chronic", "acwr",
            "weight_ffill", "body_fat",
        ] if c in m.columns]
        return {"days": _records(m[cols])}

    def workouts(self, rng: str = "90d") -> dict:
        con = duckdb.connect(str(self.db_path))
        try:
            has = con.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name='exercise'"
            ).fetchone()
            if not has:
                return {"workouts": []}
            df = con.execute('SELECT * FROM exercise').df()
        finally:
            con.close()
        if df.empty:
            return {"workouts": []}

        def pick(*names):
            for n in names:
                if n in df.columns:
                    return n
            return None

        tcol = pick("start_time", "create_time", "time")
        if tcol is None:
            return {"workouts": []}
        df[tcol] = pd.to_datetime(df[tcol], errors="coerce")
        df = df.dropna(subset=[tcol]).sort_values(tcol, ascending=False)
        if rng != "all":
            days = {"7d": 7, "30d": 30, "90d": 90}.get(rng, 90)
            cutoff = df[tcol].max() - pd.Timedelta(days=days - 1)
            df = df[df[tcol] >= cutoff]

        c_dur = pick("duration")
        c_dist = pick("distance")
        c_type = pick("exercise_type")
        c_cal = pick("calorie", "calories")
        c_mhr = pick("mean_hr", "mean_heart_rate")
        c_xhr = pick("max_hr", "max_heart_rate")
        m = self.metrics()
        hr_rest = float(m["resting_hr"].median()) if "resting_hr" in m and not m.empty else 60.0
        rows = []
        for _, x in df.iterrows():
            dur_min = (x[c_dur] / 1000 / 60) if c_dur and pd.notna(x.get(c_dur)) else None
            dist_m = x.get(c_dist) if c_dist else None
            dist_m = dist_m if pd.notna(dist_m) else None
            pace = dur_min / (dist_m / 1000) if (dur_min and dist_m and dist_m > 0) else None
            mhr = x.get(c_mhr) if c_mhr else None
            load = trimp(float(mhr) if pd.notna(mhr) else float("nan"), dur_min or 0,
                         hr_rest, DEFAULT_PARAMS.hr_max, DEFAULT_PARAMS.sex)
            tval = x.get(c_type) if c_type else None
            rows.append({
                "date": str(x[tcol].date()),
                "type": EXERCISE_NAMES.get(int(tval) if pd.notna(tval) else 0, "Tréning"),
                "duration_min": _clean(round(dur_min, 1)) if dur_min else None,
                "distance_km": _clean(round(dist_m / 1000, 2)) if dist_m else None,
                "pace_min_km": _clean(round(pace, 2)) if pace else None,
                "calorie": _clean(round(float(x[c_cal]), 0)) if c_cal and pd.notna(x.get(c_cal)) else None,
                "mean_hr": _clean(int(mhr)) if pd.notna(mhr) else None,
                "max_hr": _clean(int(x[c_xhr])) if c_xhr and pd.notna(x.get(c_xhr)) else None,
                "trimp": _clean(round(load, 1)),
            })
        return {"workouts": rows}

    def correlations(self, rng: str = "90d") -> dict:
        m = self._range(self.metrics(), rng)
        cols = [c for c in ["readiness", "resting_hr", "sleep_minutes", "sleep_debt",
                            "stress_avg", "load", "steps", "acwr"] if c in m.columns]
        sub = m[cols].dropna(how="all")
        corr = sub.corr(numeric_only=True).round(2)
        matrix = [{"x": a, "y": b, "v": _clean(float(corr.loc[b, a]))}
                  for a in corr.columns for b in corr.index]
        # sleep(deň) → readiness(nasledujúci deň)
        scatter = []
        if "sleep_minutes" in m and "readiness" in m:
            s = m["sleep_minutes"].reset_index(drop=True)
            r = m["readiness"].shift(-1).reset_index(drop=True)
            for a, b in zip(s, r):
                if pd.notna(a) and pd.notna(b):
                    scatter.append({"sleep_h": round(float(a) / 60, 2), "next_readiness": round(float(b), 1)})
        return {"labels": cols, "matrix": matrix, "scatter": scatter}

    def goals(self) -> dict:
        m = self.metrics()
        if m.empty:
            return {"goals": []}
        recent = m.tail(7)
        defs = [
            ("steps", "Kroky / deň", 10000, "", lambda s: s.mean()),
            ("sleep_minutes", "Spánok / noc", 480, "min", lambda s: s.mean()),
            ("readiness", "Readiness", 80, "", lambda s: s.mean()),
            ("acwr", "ACWR v pásme", 1.0, "", lambda s: s.mean()),
        ]
        goals = []
        for col, label, target, unit, agg in defs:
            if col not in m.columns:
                continue
            cur = float(agg(recent[col].dropna())) if recent[col].notna().any() else None
            prog = None
            if cur is not None:
                prog = min(1.5, cur / target) if col != "acwr" else max(0, 1 - abs(cur - 1.0))
            goals.append({"key": col, "label": label, "unit": unit,
                          "current": _clean(round(cur, 1)) if cur is not None else None,
                          "target": target, "progress": _clean(round(prog, 2)) if prog is not None else None})
        # streak: dni po sebe s krokmi >= cieľ
        streak = 0
        if "steps" in m.columns:
            for v in m["steps"].iloc[::-1]:
                if pd.notna(v) and v >= 10000:
                    streak += 1
                else:
                    break
        return {"goals": goals, "steps_streak": streak}
