"""Per-pipeline cookie pool.

Layout (auto-discovered, both work):
  data/cookies/cookies_p4.txt              ← legacy single-file (v1)
  data/cookies/p4/*.txt                    ← pooled mode (any number of files)

A file marked `stale` in cookie_health is skipped. If no healthy file exists,
falls back to the most-recently-failed one (so we at least try and report).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from interrogation_pipeline.config.settings import settings
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.models import CookieHealth


def _candidates(pipeline: str) -> list[Path]:
    p = pipeline.lower()
    out: list[Path] = []
    pool_dir = settings.cookies_dir / p
    if pool_dir.is_dir():
        out.extend(sorted(pool_dir.glob("*.txt")))
    legacy = settings.cookies_dir / f"cookies_{p}.txt"
    if legacy.exists():
        out.append(legacy)
    return out


async def pick_cookies(pipeline: str) -> Optional[Path]:
    """Return a healthy cookies file path for the pipeline, or None."""
    candidates = _candidates(pipeline)
    if not candidates:
        return None

    paths = [str(c) for c in candidates]
    async with session_scope() as session:
        from sqlalchemy import select
        rows = (await session.execute(
            select(CookieHealth).where(CookieHealth.cookies_path.in_(paths))
        )).scalars().all()
    health = {r.cookies_path: r for r in rows}

    healthy = [c for c in candidates if not (health.get(str(c)) and health[str(c)].stale)]
    if healthy:
        return random.choice(healthy)

    # Everything's stale — return the one that was healthy most recently,
    # so the user at least sees a fresh failure message (rather than no scrape).
    return max(
        candidates,
        key=lambda c: (health.get(str(c)).last_ok_at or "") if health.get(str(c)) else "",
    )


def list_files(pipeline: str | None = None) -> list[Path]:
    """For the UI: list all cookies files, optionally filtered by pipeline."""
    if pipeline:
        return _candidates(pipeline)
    out: list[Path] = []
    cd = settings.cookies_dir
    if cd.is_dir():
        out.extend(sorted(cd.glob("cookies_*.txt")))
        for sub in sorted(cd.iterdir()):
            if sub.is_dir():
                out.extend(sorted(sub.glob("*.txt")))
    return out
