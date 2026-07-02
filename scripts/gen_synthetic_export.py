"""Generátor syntetického Samsung Health exportu (pre vývoj/testovanie bez osobných dát).

Vyrobí priečinok s CSV súbormi v presnom formáte Samsung exportu (metadátový 1. riadok,
hlavička na 2. riadku) + ``jsons/`` priečinok s bin-ovaným HR blobom, a zazipuje ho.

Použitie::

    python scripts/gen_synthetic_export.py --days 90 --out data/synthetic_export.zip
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path


def _write_samsung_csv(path: Path, datatype_id: str, headers: list[str], rows: list[list]) -> None:
    """Zapíš CSV v Samsung formáte: metariadok, hlavička (plne kvalifikované stĺpce), dáta."""
    ns = datatype_id.replace("com.samsung.shealth.", "com.samsung.health.")
    qualified = [f"{ns}.{h}" for h in headers]
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"{datatype_id},1\n")
        fh.write(",".join(qualified) + "\n")
        for row in rows:
            fh.write(",".join("" if v is None else str(v) for v in row) + "\n")


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S.000")


def generate(out_zip: Path, days: int = 90, seed: int = 42) -> Path:
    rng = random.Random(seed)
    work = out_zip.parent / (out_zip.stem + "_dir")
    if work.exists():
        shutil.rmtree(work)
    jsons = work / "jsons" / "com.samsung.shealth.tracker.heart_rate"
    jsons.mkdir(parents=True, exist_ok=True)

    start = datetime(2024, 1, 1, 0, 0, 0)

    hr_rows, spo2_rows, stress_rows = [], [], []
    steps_rows, sleep_rows, stage_rows = [], [], []
    exercise_rows, body_rows = [], []

    weight = 82.0
    for d in range(days):
        day = start + timedelta(days=d)
        # ---- resting-ish HR + intradenné odčítania s bin JSON referenciou ----
        base_hr = 56 + int(4 * math.sin(d / 9)) + rng.randint(-2, 2)
        for hour in (7, 12, 18, 22):
            t = day + timedelta(hours=hour)
            bpm = base_hr + rng.randint(0, 40) if hour in (12, 18) else base_hr + rng.randint(-2, 6)
            # bin JSON: per-minútové hodnoty okolo bpm
            uuid = f"{d:03d}{hour:02d}"
            binning = [
                {"heart_rate": bpm + rng.randint(-4, 4), "start_time": (t + timedelta(minutes=m)).timestamp() * 1000}
                for m in range(10)
            ]
            (jsons / f"{uuid}.json").write_text(json.dumps(binning), encoding="utf-8")
            hr_rows.append([_ts(t), _ts(t + timedelta(minutes=10)), bpm,
                            bpm - 5, bpm + 8, f"{uuid}.json"])

        # ---- SpO2 (nočné) ----
        spo2_rows.append([_ts(day + timedelta(hours=3)), _ts(day + timedelta(hours=3, minutes=30)),
                          rng.randint(94, 99), base_hr])

        # ---- stress (0-100) ----
        stress_rows.append([_ts(day + timedelta(hours=14)), _ts(day + timedelta(hours=14, minutes=10)),
                            rng.randint(20, 75), 10, 90])

        # ---- kroky (denný súhrn) ----
        steps = rng.randint(4000, 15000)
        steps_rows.append([_ts(day), steps, round(steps * 0.045, 1), round(steps * 0.7, 1),
                           rng.randint(30, 120)])

        # ---- spánok + fázy ----
        sl_start = day - timedelta(hours=1)  # ~23:00 predošlého dňa
        dur_min = rng.randint(360, 500)
        sl_end = sl_start + timedelta(minutes=dur_min)
        eff = rng.randint(70, 96)
        score = rng.randint(55, 92)
        sleep_rows.append([_ts(sl_start), _ts(sl_end), eff, score, dur_min])
        # fázy: 1=awake 2=light 3=deep 4=rem
        cursor = sl_start
        for stage in _stage_sequence(dur_min, rng):
            seg = min(rng.randint(20, 90), max(1, int((sl_end - cursor).total_seconds() / 60)))
            stage_rows.append([_ts(cursor), _ts(cursor + timedelta(minutes=seg)), stage])
            cursor += timedelta(minutes=seg)
            if cursor >= sl_end:
                break

        # ---- workout (nie každý deň) ----
        if rng.random() < 0.5:
            ex_start = day + timedelta(hours=17)
            dur = rng.randint(1200, 4200)  # sekundy
            exercise_rows.append([
                _ts(ex_start), _ts(ex_start + timedelta(seconds=dur)),
                rng.choice([1002, 1001, 11007, 13001]),  # run/walk/cycle/... type kódy
                round(dur / 60 * rng.uniform(8, 12), 1),  # calorie
                round(dur / 60 * rng.uniform(150, 220), 1),  # distance m
                dur * 1000,  # duration ms
                base_hr + rng.randint(40, 70), base_hr + rng.randint(70, 100),
            ])

        # ---- body composition (raz za ~7 dní) ----
        if d % 7 == 0:
            weight += rng.uniform(-0.5, 0.3)
            body_rows.append([
                _ts(day + timedelta(hours=8)), round(weight, 1),
                round(rng.uniform(16, 22), 1), round(rng.uniform(34, 38), 1),
                rng.randint(1600, 1800), round(rng.uniform(45, 52), 1),
                round(weight / (1.83 ** 2), 1),
            ])

    _write_samsung_csv(work / "com.samsung.shealth.tracker.heart_rate.202401.csv",
                       "com.samsung.shealth.tracker.heart_rate",
                       ["start_time", "end_time", "heart_rate", "min", "max", "binning_data"], hr_rows)
    _write_samsung_csv(work / "com.samsung.shealth.tracker.oxygen_saturation.202401.csv",
                       "com.samsung.shealth.tracker.oxygen_saturation",
                       ["start_time", "end_time", "spo2", "heart_rate"], spo2_rows)
    _write_samsung_csv(work / "com.samsung.shealth.stress.202401.csv",
                       "com.samsung.shealth.stress",
                       ["start_time", "end_time", "score", "min", "max"], stress_rows)
    _write_samsung_csv(work / "com.samsung.shealth.tracker.pedometer_day_summary.202401.csv",
                       "com.samsung.shealth.tracker.pedometer_day_summary",
                       ["day_time", "step_count", "distance", "calorie", "active_time"], steps_rows)
    _write_samsung_csv(work / "com.samsung.shealth.sleep.202401.csv",
                       "com.samsung.shealth.sleep",
                       ["start_time", "end_time", "efficiency", "sleep_score", "sleep_duration"], sleep_rows)
    _write_samsung_csv(work / "com.samsung.shealth.sleep_stage.202401.csv",
                       "com.samsung.shealth.sleep_stage",
                       ["start_time", "end_time", "stage"], stage_rows)
    _write_samsung_csv(work / "com.samsung.shealth.exercise.202401.csv",
                       "com.samsung.shealth.exercise",
                       ["start_time", "end_time", "exercise_type", "calorie", "distance",
                        "duration", "mean_heart_rate", "max_heart_rate"], exercise_rows)
    _write_samsung_csv(work / "com.samsung.health.body_composition.202401.csv",
                       "com.samsung.health.body_composition",
                       ["start_time", "weight", "body_fat", "skeletal_muscle",
                        "basal_metabolic_rate", "total_body_water", "body_mass_index"], body_rows)

    # zazipuj
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in work.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(work))
    shutil.rmtree(work)
    return out_zip


def _stage_sequence(dur_min: int, rng: random.Random) -> list[int]:
    """Zjednodušená sekvencia spánkových fáz."""
    n = max(4, dur_min // 60)
    seq = []
    for i in range(n):
        if i == 0:
            seq.append(2)  # light
        elif i % 3 == 0:
            seq.append(4)  # rem
        elif i % 2 == 0:
            seq.append(3)  # deep
        else:
            seq.append(2)  # light
    if rng.random() < 0.4:
        seq.insert(rng.randint(1, len(seq) - 1), 1)  # awake segment
    return seq


def main() -> None:
    ap = argparse.ArgumentParser(description="Generuj syntetický Samsung Health export")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--out", type=Path, default=Path("data/synthetic_export.zip"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = generate(args.out, days=args.days, seed=args.seed)
    print(f"Vygenerovaný export: {out}  ({out.stat().st_size} B)")


if __name__ == "__main__":
    main()
