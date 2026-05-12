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
from interrogation_pipeline.store.db import init_db, session_scope
from interrogation_pipeline.store.repos import RunRepo

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
    async with session_scope() as session:
        orphans = await RunRepo(session).mark_orphans_failed()
    if orphans:
        log.warning(
            "Marked %d orphaned 'running' run(s) as failed (server didn't shut "
            "down cleanly last time).", orphans
        )
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
# The check is dynamic on every request so the server picks up a fresh build
# without needing a restart. /assets/* is served manually for the same reason
# (StaticFiles mount must point at a dir that exists at mount time).
@app.get("/assets/{file_path:path}")
async def serve_asset(file_path: str):
    f = STATIC_DIR / "assets" / file_path
    if f.is_file():
        return FileResponse(f)
    return JSONResponse({"error": "asset not found"}, status_code=404)


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # /api/* routes are registered above this catch-all, but guard anyway.
    if full_path.startswith("api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Real files at the static root (favicon.svg, robots.txt, etc.) served as-is.
    if full_path:
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)

    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)

    return JSONResponse(
        {
            "status": "backend ok",
            "frontend": "not built yet — run `npm run build` in frontend/ "
                        "(or use start.bat / start.command which does it for you)",
            "api_docs": "/docs",
            "static_dir": str(STATIC_DIR),
        },
        status_code=503,
    )
