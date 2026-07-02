"""Registry dátových typov: mapovanie Samsung ``datatype_id`` -> normalizovaná tabuľka.

Pre známe typy definujeme cieľový názov tabuľky, premenovanie stĺpcov a ktoré stĺpce sú
časové značky / číselné. Neznáme typy sa načítajú "as-is" do tabuľky odvodenej z id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableSpec:
    """Špecifikácia normalizácie jedného dátového typu."""

    table: str
    #: mapovanie krátky_názov_stĺpca -> kanonický názov
    rename: dict[str, str] = field(default_factory=dict)
    #: stĺpce (kanonické názvy), ktoré sú časové značky
    time_cols: tuple[str, ...] = ()
    #: stĺpce (kanonické názvy), ktoré sú číselné
    numeric_cols: tuple[str, ...] = ()
    #: stĺpce, ktoré referencujú bin-ované JSON (dekódujú sa do <col>_json)
    binning_cols: tuple[str, ...] = ()


# Kľúč = datatype_id z prvého riadku CSV (bez trailing verzie).
REGISTRY: dict[str, TableSpec] = {
    "com.samsung.shealth.tracker.heart_rate": TableSpec(
        table="heart_rate",
        rename={"heart_rate": "bpm", "heart_beat_count": "beat_count"},
        time_cols=("start_time", "end_time"),
        numeric_cols=("bpm", "min", "max", "beat_count"),
        binning_cols=("binning_data",),
    ),
    "com.samsung.shealth.tracker.oxygen_saturation": TableSpec(
        table="spo2",
        rename={"spo2": "spo2", "oxygen_saturation": "spo2"},
        time_cols=("start_time", "end_time"),
        numeric_cols=("spo2", "heart_rate"),
        binning_cols=("binning_data",),
    ),
    "com.samsung.shealth.stress": TableSpec(
        table="stress",
        rename={"score": "score"},
        time_cols=("start_time", "end_time"),
        numeric_cols=("score", "min", "max"),
        binning_cols=("binning_data",),
    ),
    "com.samsung.shealth.sleep": TableSpec(
        table="sleep",
        rename={"efficiency": "efficiency", "sleep_score": "score"},
        time_cols=("start_time", "end_time"),
        numeric_cols=("efficiency", "score", "sleep_duration"),
    ),
    "com.samsung.shealth.sleep_stage": TableSpec(
        table="sleep_stage",
        rename={"stage": "stage"},
        time_cols=("start_time", "end_time"),
        numeric_cols=("stage",),
    ),
    "com.samsung.shealth.exercise": TableSpec(
        table="exercise",
        rename={
            "exercise_type": "exercise_type",
            "calorie": "calorie",
            "distance": "distance",
            "duration": "duration",
            "mean_heart_rate": "mean_hr",
            "max_heart_rate": "max_hr",
        },
        time_cols=("start_time", "end_time"),
        numeric_cols=(
            "exercise_type",
            "calorie",
            "distance",
            "duration",
            "mean_hr",
            "max_hr",
        ),
    ),
    "com.samsung.shealth.tracker.pedometer_day_summary": TableSpec(
        table="steps_daily",
        rename={"step_count": "steps", "calorie": "calorie", "distance": "distance"},
        time_cols=("day_time",),
        numeric_cols=("steps", "calorie", "distance", "active_time"),
    ),
    "com.samsung.health.body_composition": TableSpec(
        table="body_composition",
        rename={
            "weight": "weight",
            "body_fat": "body_fat",
            "skeletal_muscle": "skeletal_muscle",
            "basal_metabolic_rate": "bmr",
            "total_body_water": "body_water",
            "body_mass_index": "bmi",
        },
        time_cols=("start_time",),
        numeric_cols=(
            "weight",
            "body_fat",
            "skeletal_muscle",
            "bmr",
            "body_water",
            "bmi",
        ),
    ),
}


def sanitize_table_name(datatype_id: str) -> str:
    """Odvoď bezpečný názov tabuľky z neznámeho datatype_id."""
    name = datatype_id.replace("com.samsung.shealth.", "").replace("com.samsung.health.", "")
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return name or "unknown"


def spec_for(datatype_id: str) -> TableSpec:
    """Vráť :class:`TableSpec` pre daný datatype_id (fallback pre neznáme typy)."""
    if datatype_id in REGISTRY:
        return REGISTRY[datatype_id]
    return TableSpec(table=sanitize_table_name(datatype_id))
