"""Orchestrácia ingestu: export -> normalizácia -> DuckDB.

Jeden export je plný snapshot, preto pri načítaní tabuľku prepíšeme. Viac CSV súborov
sa môže mapovať na tú istú tabuľku (napr. viac exportov) — frame-y sa spoja a
deduplikujú podľa časových stĺpcov.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from shealth.ingest.csv_reader import read_samsung_csv
from shealth.ingest.datatypes import TableSpec, spec_for
from shealth.ingest.json_decode import decode_binning
from shealth.ingest.unzip import locate_export

DEFAULT_DB = Path("data/health.duckdb")


@dataclass
class IngestReport:
    """Prehľad výsledku ingestu."""

    db_path: Path
    tables: dict[str, int]  # názov tabuľky -> počet riadkov

    def __str__(self) -> str:
        lines = [f"DuckDB: {self.db_path}"]
        for name, n in sorted(self.tables.items()):
            lines.append(f"  {name:24s} {n:>8d} riadkov")
        return "\n".join(lines)


#: rozsah dôveryhodných dátumov pre health export; mimo neho ide o poškodené/odpadové
#: hodnoty (napr. rok 1001) — tie by inak pri uložení do datetime64[ns] pretiekli
_MIN_TS = pd.Timestamp("1970-01-01")
_MAX_TS = pd.Timestamp("2200-01-01")


def _drop_out_of_bounds(ts: pd.Series) -> pd.Series:
    """Nahraď dátumy mimo dôveryhodného rozsahu za NaT (chráni pred pretečením ns)."""
    bad = ts.notna() & ((ts < _MIN_TS) | (ts > _MAX_TS))
    if bad.any():
        ts = ts.mask(bad)
    return ts


def _parse_timestamps(series: pd.Series) -> pd.Series:
    """Parsuj časovú značku: buď epoch v ms (int), alebo 'YYYY-MM-DD HH:MM:SS.mmm'.

    Poškodené hodnoty (mimo rozsahu roku 1970–2200) sa zahodia na NaT namiesto pádu —
    pandas 2.x vie pri ``errors="coerce"`` vrátiť dátum v inej než nanosekundovej
    presnosti, čo pri priamom priradení do ns-stĺpca spôsobí ``OutOfBoundsDatetime``.
    """
    s = series.astype("string").str.strip()
    as_num = pd.to_numeric(s, errors="coerce")
    # heuristika: hodnoty > 10^11 sú epoch v ms
    is_epoch = as_num.notna() & (as_num > 1e11)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    if is_epoch.any():
        epoch_ts = _drop_out_of_bounds(pd.to_datetime(as_num[is_epoch], unit="ms", errors="coerce"))
        out.loc[is_epoch] = epoch_ts.astype("datetime64[ns]")
    text_mask = ~is_epoch
    if text_mask.any():
        text_ts = _drop_out_of_bounds(pd.to_datetime(s[text_mask], errors="coerce"))
        out.loc[text_mask] = text_ts.astype("datetime64[ns]")
    return out


def _normalize(df: pd.DataFrame, spec: TableSpec, jsons_dir: Path | None, datatype_id: str
               ) -> pd.DataFrame:
    """Aplikuj rename, parsovanie timestampov, číselné coerce a dekódovanie binningu."""
    if spec.rename:
        df = df.rename(columns={k: v for k, v in spec.rename.items() if k in df.columns})

    for col in spec.time_cols:
        if col in df.columns:
            df[col] = _parse_timestamps(df[col])

    for col in spec.numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in spec.binning_cols:
        if col in df.columns:
            df[f"{col}_json"] = df[col].map(
                lambda v: decode_binning(v, jsons_dir, datatype_id)
            )

    return df


def _dedupe(df: pd.DataFrame, spec: TableSpec) -> pd.DataFrame:
    """Deduplikuj podľa časových stĺpcov, ak existujú."""
    keys = [c for c in spec.time_cols if c in df.columns]
    if keys:
        df = df.drop_duplicates(subset=keys, keep="last")
    return df


def ingest_export(
    source: str | Path,
    db_path: str | Path = DEFAULT_DB,
    extract_to: str | Path | None = None,
) -> IngestReport:
    """Rozbaľ export, normalizuj a načítaj do DuckDB.

    Args:
        source: cesta k ``export.zip`` alebo rozbalenému priečinku.
        db_path: cieľová DuckDB databáza.
        extract_to: kam rozbaliť ZIP (voliteľné).
    """
    layout = locate_export(source, extract_to=extract_to)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # zbieraj frame-y podľa cieľovej tabuľky (viac CSV -> tá istá tabuľka)
    by_table: dict[str, list[pd.DataFrame]] = {}
    specs: dict[str, TableSpec] = {}

    for csv_path in layout.csv_files:
        parsed = read_samsung_csv(csv_path)
        spec = spec_for(parsed.datatype_id)
        df = _normalize(parsed.df, spec, layout.jsons_dir, parsed.datatype_id)
        by_table.setdefault(spec.table, []).append(df)
        specs[spec.table] = spec

    tables: dict[str, int] = {}
    con = duckdb.connect(str(db_path))
    try:
        for table, frames in by_table.items():
            combined = pd.concat(frames, ignore_index=True)
            combined = _dedupe(combined, specs[table])
            # bin JSON stĺpce sú Python objekty — pre DuckDB serializuj na text
            for col in list(combined.columns):
                if col.endswith("_json"):
                    combined[col] = combined[col].map(
                        lambda v: None if v is None else _json_dumps(v)
                    )
            con.register("df_tmp", combined)
            try:
                con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM df_tmp')
            finally:
                con.unregister("df_tmp")
            tables[table] = len(combined)
    finally:
        con.close()

    return IngestReport(db_path=db_path, tables=tables)


def _json_dumps(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
