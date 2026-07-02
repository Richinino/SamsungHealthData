"""Generický reader pre špecifický CSV formát Samsung Health exportu.

Zvláštnosť formátu: **prvý riadok sú metadáta** (id dátového typu + verzia + prípadný
počet stĺpcov), **druhý riadok je hlavička** a od tretieho riadku sú dáta. Príklad::

    com.samsung.shealth.tracker.heart_rate,1
    com.samsung.health.heart_rate.start_time,com.samsung.health.heart_rate.heart_rate,...
    2024-01-01 06:00:00.000,58,...
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class SamsungCsv:
    """Výsledok parsovania jedného CSV súboru."""

    datatype_id: str
    version: str | None
    df: pd.DataFrame
    source: Path


def _read_meta_line(path: Path) -> tuple[str, str | None]:
    """Prečítaj prvý (metadátový) riadok a vráť (datatype_id, version)."""
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        first = fh.readline().strip()
    parts = first.split(",")
    datatype_id = parts[0].strip()
    version = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return datatype_id, version


def read_samsung_csv(path: str | Path) -> SamsungCsv:
    """Prečítaj jeden Samsung Health CSV súbor do :class:`SamsungCsv`.

    Hlavička je na druhom riadku (``skiprows=1``). Stĺpce plné NaN (Samsung necháva
    v exportoch prázdne trailing stĺpce) sa odstránia. Názvy stĺpcov sa skrátia z
    plne kvalifikovaných (``com.samsung.health.heart_rate.start_time``) na krátke
    (``start_time``) pre pohodlnejšiu prácu, s ponechaním pôvodných v ``df.attrs``.
    """
    path = Path(path)
    datatype_id, version = _read_meta_line(path)

    df = pd.read_csv(
        path,
        skiprows=1,
        dtype=str,
        keep_default_na=True,
        na_values=[""],
        encoding="utf-8-sig",
        engine="python",
        on_bad_lines="warn",  # nezahadzuj potichu — signalizuj problémové riadky
    )
    # zahoď úplne prázdne stĺpce (Samsung trailing čiarky)
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]

    original_cols = list(df.columns)
    df.columns = [_short_col(c) for c in df.columns]
    df.attrs["original_columns"] = dict(zip(df.columns, original_cols))
    df.attrs["datatype_id"] = datatype_id

    return SamsungCsv(datatype_id=datatype_id, version=version, df=df, source=path)


def _short_col(col: str) -> str:
    """Skráť ``com.samsung.health.heart_rate.start_time`` -> ``start_time``.

    Ponechaj poslednú "zmysluplnú" časť; keď posledná časť koliduje s bežnými
    (napr. ``time``), vezmi posledné dva tokeny.
    """
    col = str(col).strip()
    if "." not in col:
        return col
    tokens = col.split(".")
    last = tokens[-1]
    if last in {"time", "value", "type", "id"} and len(tokens) >= 2:
        return "_".join(tokens[-2:])
    return last
