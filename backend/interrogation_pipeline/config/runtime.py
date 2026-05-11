"""Runtime-tunable settings stored in the SQLite `config` table.

These can be edited from the Settings page in the dashboard without restarting
the process. First-time defaults are seeded from env vars at startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.repos import ConfigRepo


DEFAULTS: dict[str, Any] = {
    "schedule_cron": None,            # filled at first start from env
    "lookback_hours": None,           # filled at first start from env
    "scrape_concurrency": 3,
    "scan_concurrency": 5,
    "verify_concurrency": 3,
    "video_max_attempts": 5,
    "proxy_blacklist_minutes": 30,
    # Adaptive proxy mode:
    #   "auto"    — try direct (no proxy) first; fall back to proxy if YouTube
    #               rate-limits or detects us. Periodically retry direct.
    #   "always"  — every yt-dlp call goes through a proxy from the pool.
    #   "never"   — direct connection only (no proxy ever).
    "proxy_mode": "auto",
    # In auto mode, how often we retry going direct after a failure.
    "proxy_retry_direct_minutes": 60,
    # Disable a proxy after this many consecutive failures.
    "proxy_max_failures": 5,
    "cookie_stale_threshold": 5,      # consecutive auth_failed before banner
    # Trello — display labels are stored in config so they can be edited from
    # Settings without touching code. Actual board/list IDs come from .env or
    # are auto-discovered by name on first push.
    "old_board_name": "FOIA Trials",
    "new_board_name": "ULF",
    "new_list_name": "Ayush Snipe List",
    "old_board_id": "",
    "new_board_id": "",
    "new_list_id": "",
    "prompt_version": "v2-homicide-2026-05",
    "weekly_reconcile_dow": 0,        # 0=Mon
    "display_timezone": "Asia/Kolkata",
    # Banned for FOIA — not skipped, just badge'd on the dashboard so the user
    # can quick-skip them. Match against parsed `state` (2-letter) and the
    # `arresting_agency` text (case-insensitive).
    "banned_states": ["AR", "CA", "AL", "OK", "PA", "KY", "IL"],
    "banned_agencies": ["LAPD", "Los Angeles Police", "NYPD", "New York Police"],
}


@dataclass(slots=True)
class RuntimeConfig:
    schedule_cron: str
    lookback_hours: int
    scrape_concurrency: int
    scan_concurrency: int
    verify_concurrency: int
    video_max_attempts: int
    proxy_blacklist_minutes: int
    proxy_mode: str
    proxy_retry_direct_minutes: int
    proxy_max_failures: int
    cookie_stale_threshold: int
    old_board_name: str
    new_board_name: str
    new_list_name: str
    old_board_id: str
    new_board_id: str
    new_list_id: str
    prompt_version: str
    weekly_reconcile_dow: int
    display_timezone: str
    banned_states: list[str]
    banned_agencies: list[str]


async def seed_defaults() -> None:
    """Insert any DEFAULTS that aren't yet present in the config table."""
    DEFAULTS["schedule_cron"] = (
        DEFAULTS["schedule_cron"] or env_settings.initial_schedule_cron
    )
    DEFAULTS["lookback_hours"] = (
        DEFAULTS["lookback_hours"] or env_settings.initial_lookback_hours
    )
    DEFAULTS["old_board_id"] = (
        DEFAULTS["old_board_id"] or env_settings.trello_old_board_id
    )
    DEFAULTS["new_board_id"] = (
        DEFAULTS["new_board_id"] or env_settings.trello_new_board_id
    )
    DEFAULTS["new_list_id"] = (
        DEFAULTS["new_list_id"] or env_settings.trello_new_list_id
    )

    async with session_scope() as session:
        repo = ConfigRepo(session)
        existing = await repo.all()
        for k, v in DEFAULTS.items():
            if k not in existing:
                await repo.set(k, v)


async def load() -> RuntimeConfig:
    async with session_scope() as session:
        repo = ConfigRepo(session)
        d = {**DEFAULTS, **(await repo.all())}
    return RuntimeConfig(**d)


async def patch(updates: dict[str, Any]) -> RuntimeConfig:
    async with session_scope() as session:
        repo = ConfigRepo(session)
        for k, v in updates.items():
            if k not in DEFAULTS:
                raise KeyError(f"Unknown config key: {k}")
            await repo.set(k, v)
    return await load()
