"""Testy /api endpointov cez FastAPI TestClient."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gen_synthetic_export as gen  # noqa: E402

from shealth.api.app import create_app  # noqa: E402
from shealth.ingest import ingest_export  # noqa: E402
from shealth.metrics import build_daily_metrics  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    zip_path = tmp_path_factory.mktemp("exp") / "synthetic_export.zip"
    gen.generate(zip_path, days=45, seed=3)
    db = tmp_path_factory.mktemp("db") / "health.duckdb"
    ingest_export(zip_path, db_path=db)
    build_daily_metrics(db)
    return TestClient(create_app(db))


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_summary(client: TestClient):
    r = client.get("/api/summary?range=30d").json()
    assert r["empty"] is False
    assert 0 <= r["readiness"] <= 100
    assert any(k["key"] == "resting_hr" for k in r["kpis"])


def test_timeseries(client: TestClient):
    r = client.get("/api/timeseries?range=7d").json()
    assert 1 <= len(r["days"]) <= 7
    assert "readiness" in r["days"][-1]


def test_workouts(client: TestClient):
    r = client.get("/api/workouts?range=90d").json()
    assert isinstance(r["workouts"], list)
    if r["workouts"]:
        assert "trimp" in r["workouts"][0]


def test_correlations(client: TestClient):
    r = client.get("/api/correlations?range=90d").json()
    assert "readiness" in r["labels"]
    assert len(r["matrix"]) == len(r["labels"]) ** 2


def test_goals(client: TestClient):
    r = client.get("/api/goals").json()
    assert any(g["key"] == "steps" for g in r["goals"])


def test_range_validation(client: TestClient):
    assert client.get("/api/summary?range=bogus").status_code == 422
