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
