"""FastAPI app factory + lifespan + static-frontend mount."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from interrogation_pipeline import __version__
from interrogation_pipeline.api.routers import (
    cases_router,
    channels_router,
    cookies_router,
    proxies_router,
    runs_router,
    settings_router,
    stats_router,
    today_router,
)
from interrogation_pipeline.bootstrap import seed_all_channels
from interrogation_pipeline.config.runtime import seed_defaults
from interrogation_pipeline.scheduler.scheduler import start_scheduler, stop_scheduler
from interrogation_pipeline.scrape.proxies import maybe_seed_from_env
from interrogation_pipeline.store.db import init_db

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Initializing database…")
    await init_db()
    await seed_defaults()
    inserted = await seed_all_channels()
    if any(inserted.values()):
        log.info(
            "Seeded channels: P4=%d  P3=%d  P1=%d  P2=%d (P2 inactive)",
            inserted["P4"], inserted["P3"], inserted["P1"], inserted["P2"],
        )
    seeded_proxies = await maybe_seed_from_env()
    if seeded_proxies:
        log.info("Seeded %d proxies from WEBSHARE_* env vars.", seeded_proxies)
    log.info("Database ready.")
    try:
        await start_scheduler()
    except Exception as e:  # noqa: BLE001
        log.warning("Scheduler did not start: %s", e)
    yield
    await stop_scheduler()
    log.info("Shutting down.")


app = FastAPI(
    title="Interrogation Pipeline",
    version=__version__,
    lifespan=lifespan,
)

# Permissive CORS only in dev — front-end is served from same origin in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


# REST routers
app.include_router(today_router, prefix="/api")
app.include_router(cases_router, prefix="/api")
app.include_router(channels_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(proxies_router, prefix="/api")
app.include_router(cookies_router, prefix="/api")


# ──── Static frontend (built React app) + SPA fallback ────
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # API paths shouldn't reach here, but guard anyway.
        if full_path.startswith("api/"):
            return JSONResponse({"error": "Not found"}, status_code=404)
        # Real static files at the root (favicon, robots.txt, etc.) are served
        # as-is. Everything else falls through to index.html so React Router can
        # take over.
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse(
            {
                "error": "Frontend not built",
                "hint": "Run `npm install && npm run build` in the frontend/ directory",
            },
            status_code=503,
        )
else:
    @app.get("/")
    async def placeholder() -> dict[str, str]:
        return {
            "status": "backend ok",
            "frontend": "not built — run `npm install && npm run build` in frontend/",
            "api_docs": "/docs",
        }
