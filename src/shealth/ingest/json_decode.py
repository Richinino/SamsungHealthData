"""Dekódovanie bin-ovaných JSON blobov referencovaných z CSV.

Niektoré CSV stĺpce (napr. ``binning_data`` pri heart rate / SpO2 / stress) obsahujú buď
inline JSON, alebo názov súboru v priečinku ``jsons/<datatype_id>/<uuid>.json``. Súbory
môžu byť plain JSON alebo GZIP-komprimované.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any


def _maybe_gunzip(raw: bytes) -> bytes:
    """Ak sú dáta GZIP (magic 0x1f 0x8b), rozbaľ ich."""
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        return gzip.decompress(raw)
    return raw


def decode_binning(value: str | None, jsons_dir: Path | None, datatype_id: str) -> Any | None:
    """Dekóduj hodnotu bin-ovaného stĺpca na Python objekt.

    Args:
        value: obsah bunky — buď inline JSON, alebo relatívny/samotný názov súboru.
        jsons_dir: priečinok ``jsons/`` z exportu (alebo None).
        datatype_id: id dátového typu, používa sa na zostavenie cesty k súboru.

    Returns:
        Naparsovaný JSON (list/dict), alebo None ak sa nedá dekódovať.
    """
    if value is None or (isinstance(value, float)):
        return None
    text = str(value).strip()
    if not text:
        return None

    # inline JSON
    if text[0] in "[{":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # inak to je odkaz na súbor v jsons/
    if jsons_dir is None:
        return None
    candidates = [
        jsons_dir / datatype_id / text,
        jsons_dir / text,
    ]
    if not text.endswith(".json"):
        candidates.insert(0, jsons_dir / datatype_id / f"{text}.json")
    for path in candidates:
        if path.is_file():
            raw = _maybe_gunzip(path.read_bytes())
            try:
                return json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                return None
    return None
