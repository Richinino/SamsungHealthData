"""FastAPI aplikácia — /api endpointy + servovanie zbuildeného frontendu."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from shealth.api.queries import DEFAULT_DB, HealthData

WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


def create_app(db_path: str | Path | None = None) -> FastAPI:
    db = Path(db_path or os.environ.get("SHEALTH_DB", DEFAULT_DB))
    data = HealthData(db)
    app = FastAPI(title="shealth dashboard", version="0.3.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    Rng = Query("30d", pattern="^(7d|30d|90d|all)$")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "db": str(db), "exists": db.exists()}

    @app.get("/api/summary")
    def summary(range: str = Rng) -> dict:
        return data.summary(range)

    @app.get("/api/timeseries")
    def timeseries(range: str = Rng) -> dict:
        return data.timeseries(range)

    @app.get("/api/workouts")
    def workouts(range: str = Query("90d", pattern="^(7d|30d|90d|all)$")) -> dict:
        return data.workouts(range)

    @app.get("/api/correlations")
    def correlations(range: str = Query("90d", pattern="^(7d|30d|90d|all)$")) -> dict:
        return data.correlations(range)

    @app.get("/api/goals")
    def goals() -> dict:
        return data.goals()

    # ---- servovanie frontendu (ak je zbuildený) ----
    if WEB_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(WEB_DIST / "index.html")
    else:
        @app.get("/", response_class=HTMLResponse)
        def not_built() -> str:
            return (
                "<html><body style='font-family:system-ui;max-width:640px;margin:60px auto;"
                "line-height:1.6;color:#111'>"
                "<h2>⚙️ Frontend ešte nie je zbuildený</h2>"
                "<p>Backend (API) beží, ale chýba <code>web/dist</code>. Zbuildi frontend:</p>"
                "<pre style='background:#f4f4f2;padding:12px;border-radius:8px'>"
                "cd web\nnpm install\nnpm run build\ncd ..</pre>"
                "<p>Potom obnov túto stránku. Dáta si zatiaľ vieš pozrieť aj priamo cez API: "
                "<a href='/api/summary?range=30d'>/api/summary</a>, "
                "<a href='/api/timeseries?range=30d'>/api/timeseries</a>.</p>"
                "</body></html>"
            )

    return app


app = create_app()
