"""Rozbalenie a lokalizácia Samsung Health exportu.

Export z appky (Settings → Download personal data) je ZIP alebo priečinok obsahujúci
množstvo CSV súborov (``com.samsung.shealth.*.csv``, ``com.samsung.health.*.csv``) a
priečinok ``jsons/`` s bin-ovanými JSON blobmi vyššieho rozlíšenia.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path


def _safe_extractall(zf: zipfile.ZipFile, target: Path) -> None:
    """Rozbaľ ZIP s ochranou proti path traversal (Zip Slip).

    Overí, že každý člen archívu po rozvinutí zostáva vnútri ``target``; inak abortuje.
    """
    target = target.resolve()
    for member in zf.namelist():
        dest = (target / member).resolve()
        if dest != target and target not in dest.parents:
            raise ValueError(f"Nebezpečná cesta v archíve (Zip Slip): {member!r}")
    zf.extractall(target)


@dataclass
class ExportLayout:
    """Umiestnenie rozbaleného exportu."""

    root: Path
    csv_files: list[Path] = field(default_factory=list)
    jsons_dir: Path | None = None


def _find_root(base: Path) -> Path:
    """Nájdi skutočný koreň exportu.

    Samsung občas vnára všetko do ``samsunghealth_<user>_<timestamp>/``. Zostúpime cez
    jednoprvkové priečinky, kým nenarazíme na CSV súbory.
    """
    current = base
    for _ in range(5):
        csvs = list(current.glob("*.csv"))
        if csvs:
            return current
        subdirs = [p for p in current.iterdir() if p.is_dir() and p.name != "jsons"]
        if len(subdirs) == 1:
            current = subdirs[0]
            continue
        # viac podpriečinkov — skús nájsť ten, čo obsahuje CSV
        for sub in subdirs:
            if list(sub.glob("*.csv")):
                return sub
        break
    return current


def locate_export(source: str | Path, extract_to: str | Path | None = None) -> ExportLayout:
    """Rozbaľ (ak treba) a lokalizuj CSV súbory + ``jsons/`` priečinok.

    Args:
        source: cesta k ``.zip`` exportu alebo k už rozbalenému priečinku.
        extract_to: kam rozbaliť ZIP (default: vedľa zipu, priečinok ``export/``).
    """
    source = Path(source)
    if source.is_file() and source.suffix.lower() == ".zip":
        target = Path(extract_to) if extract_to else source.parent / "export"
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as zf:
            _safe_extractall(zf, target)
        base = target
    elif source.is_dir():
        base = source
    else:
        raise FileNotFoundError(f"Export sa nenašiel: {source}")

    root = _find_root(base)
    csv_files = sorted(root.glob("*.csv"))
    jsons_dir = root / "jsons"
    return ExportLayout(
        root=root,
        csv_files=csv_files,
        jsons_dir=jsons_dir if jsons_dir.is_dir() else None,
    )
