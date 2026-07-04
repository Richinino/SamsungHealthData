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


def _read_header_names(path: Path) -> list[str]:
    """Prečítaj druhý riadok (hlavičku) a vráť názvy stĺpcov (bez trailing prázdnych)."""
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        fh.readline()  # metadáta
        header = fh.readline().rstrip("\r\n")
    names = [h.strip() for h in header.split(",")]
    while names and names[-1] == "":
        names.pop()
    return names


def read_samsung_csv(path: str | Path) -> SamsungCsv:
    """Prečítaj jeden Samsung Health CSV súbor do :class:`SamsungCsv`.

    Samsung dáva na koniec dátových riadkov **čiarku navyše**, takže riadky majú o
    pole viac než hlavička; pandas by inak vzal prvý stĺpec ako index a **posunul**
    všetky stĺpce (hlavičky by nesedeli s dátami). Preto čítame hlavičku ručne a
    dáta **pozične** (``header=None``) a názvy priradíme na správne stĺpce. Názvy sa
    skracujú z plne kvalifikovaných (``com.samsung.health.heart_rate.start_time``) na
    krátke (``start_time``); originály sú v ``df.attrs``.
    """
    path = Path(path)
    datatype_id, version = _read_meta_line(path)
    header_names = _read_header_names(path)

    read_kwargs = dict(
        skiprows=2,           # preskoč metadáta + hlavičku, čítaj pozične
        header=None,
        dtype=str,
        na_values=[""],
        encoding="utf-8-sig",
        on_bad_lines="warn",
    )
    try:
        df = pd.read_csv(path, engine="c", **read_kwargs)
    except Exception:
        df = pd.read_csv(path, engine="python", **read_kwargs)

    # zarovnaj názvy hlavičky na dátové stĺpce (prebytočné trailing polia zahoď)
    n = min(len(header_names), df.shape[1])
    df = df.iloc[:, :n]
    original_cols = header_names[:n]
    df.columns = _dedupe(_short_col(c) for c in original_cols)
    # zahoď úplne prázdne stĺpce (napr. trailing)
    df = df.dropna(axis=1, how="all")

    df.attrs["original_columns"] = dict(zip(df.columns, original_cols))
    df.attrs["datatype_id"] = datatype_id

    return SamsungCsv(datatype_id=datatype_id, version=version, df=df, source=path)


def _dedupe(names) -> list[str]:
    """Zabezpeč jedinečné názvy stĺpcov (kolízie po skrátení dostanú príponu _2, _3…)."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for name in names:
        if name in seen:
            seen[name] += 1
            out.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 1
            out.append(name)
    return out


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
