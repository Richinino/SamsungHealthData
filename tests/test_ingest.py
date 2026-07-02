"""Testy ingestu proti syntetickému exportu."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gen_synthetic_export as gen  # noqa: E402

from shealth.ingest import ingest_export  # noqa: E402
from shealth.ingest.csv_reader import read_samsung_csv  # noqa: E402
from shealth.ingest.load import _parse_timestamps  # noqa: E402


@pytest.fixture(scope="module")
def export_zip(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("exp") / "synthetic_export.zip"
    return gen.generate(out, days=30, seed=7)


def test_generate_creates_zip(export_zip: Path):
    assert export_zip.exists()
    assert export_zip.stat().st_size > 0


def test_ingest_populates_expected_tables(export_zip: Path, tmp_path: Path):
    db = tmp_path / "health.duckdb"
    report = ingest_export(export_zip, db_path=db)
    expected = {
        "heart_rate", "spo2", "stress", "steps_daily",
        "sleep", "sleep_stage", "exercise", "body_composition",
    }
    assert expected.issubset(set(report.tables))
    # 30 dní krokov
    assert report.tables["steps_daily"] == 30
    # HR: 4 odčítania/deň
    assert report.tables["heart_rate"] == 30 * 4


def test_timestamps_are_parsed(export_zip: Path, tmp_path: Path):
    db = tmp_path / "health.duckdb"
    ingest_export(export_zip, db_path=db)
    con = duckdb.connect(str(db))
    try:
        dtype = con.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='heart_rate' AND column_name='start_time'"
        ).fetchone()[0]
    finally:
        con.close()
    assert "TIMESTAMP" in dtype.upper()


def test_binning_json_decoded(export_zip: Path, tmp_path: Path):
    db = tmp_path / "health.duckdb"
    ingest_export(export_zip, db_path=db)
    con = duckdb.connect(str(db))
    try:
        val = con.execute(
            "SELECT binning_data_json FROM heart_rate "
            "WHERE binning_data_json IS NOT NULL LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    assert val is not None and val[0] is not None
    assert "heart_rate" in val[0]


def test_csv_reader_short_columns(export_zip: Path, tmp_path: Path):
    # rozbaľ a over skrátené názvy stĺpcov
    import zipfile

    dest = tmp_path / "raw"
    with zipfile.ZipFile(export_zip) as zf:
        zf.extractall(dest)
    csv = next(dest.glob("*heart_rate*.csv"))
    parsed = read_samsung_csv(csv)
    assert parsed.datatype_id == "com.samsung.shealth.tracker.heart_rate"
    assert "start_time" in parsed.df.columns


def test_reader_handles_binning_with_commas_and_newlines(tmp_path: Path):
    """Regresia: širokým súborom (heart_rate/sleep/stress) sa bin pole s čiarkami
    a novým riadkom v úvodzovkách nesmie zlepiť do jedného riadku (python engine to
    robil; C engine to zvláda)."""
    csv = tmp_path / "com.samsung.shealth.tracker.heart_rate.wide.csv"
    csv.write_text(
        "com.samsung.shealth.tracker.heart_rate,7\n"
        "com.samsung.health.heart_rate.start_time,com.samsung.health.heart_rate.heart_rate,"
        "com.samsung.health.heart_rate.binning_data,com.samsung.health.heart_rate.end_time\n"
        '2024-01-01 06:00:00.000,58,"[{a:1,b:2},\n{c:3}]",2024-01-01 06:10:00.000\n'
        '2024-01-01 07:00:00.000,61,"[{a:5}]",2024-01-01 07:10:00.000\n'
        '2024-01-01 08:00:00.000,64,"[{a:7}]",2024-01-01 08:10:00.000\n',
        encoding="utf-8",
    )
    parsed = read_samsung_csv(csv)
    assert len(parsed.df) == 3
    assert "start_time" in parsed.df.columns
    assert "heart_rate" in parsed.df.columns


def test_parse_timestamps_drops_out_of_bounds_dates():
    """Regresia: reálne exporty občas obsahujú poškodené dátumy (napr. rok 1001),
    ktoré pretekajú nanosekundovú presnosť pandas datetime64[ns] a v staršej
    implementácii spôsobovali pád (pandas.errors.OutOfBoundsDatetime)."""
    import pandas as pd

    s = pd.Series([
        "2024-01-01 06:00:00.000",
        "1001-01-01 00:00:00",   # poškodený text — mimo dôveryhodného rozsahu
        None,
        "2024-06-15 12:30:00.000",
        "99999999999999",        # epoch v ms, ktorý po prevode pretečie
    ])
    out = _parse_timestamps(s)
    assert str(out.dtype) == "datetime64[ns]"
    assert out.iloc[0] == pd.Timestamp("2024-01-01 06:00:00")
    assert pd.isna(out.iloc[1])
    assert pd.isna(out.iloc[2])
    assert out.iloc[3] == pd.Timestamp("2024-06-15 12:30:00")
    assert pd.isna(out.iloc[4])


def test_ingest_survives_corrupted_timestamp_row(tmp_path: Path):
    """Riadok s poškodeným dátumom v reálnom CSV nesmie zhodiť celý ingest."""
    csv = tmp_path / "com.samsung.shealth.stress.corrupt.csv"
    csv.write_text(
        "com.samsung.shealth.stress,1\n"
        "com.samsung.health.stress.start_time,com.samsung.health.stress.end_time,"
        "com.samsung.health.stress.score\n"
        "2024-01-01 06:00:00.000,2024-01-01 06:10:00.000,40\n"
        "1001-01-01 00:00:00,1001-01-01 00:10:00,99\n",
        encoding="utf-8",
    )
    db = tmp_path / "corrupt.duckdb"
    report = ingest_export(tmp_path, db_path=db)
    assert report.tables["stress"] == 2
    con = duckdb.connect(str(db))
    try:
        n_null = con.execute(
            "SELECT count(*) FROM stress WHERE start_time IS NULL"
        ).fetchone()[0]
    finally:
        con.close()
    assert n_null == 1
