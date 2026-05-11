"""Smart proxy pool with three modes and DB-backed state.

Modes (config: `proxy_mode`):
  - "never"  : every call goes direct (no proxy). Useful in dev or when YT
               is being friendly. Bandwidth-free.
  - "always" : every call picks a healthy proxy from `proxy_pool`. Use when
               YT is rate-limiting hard.
  - "auto"   : adaptive — try direct first. If YT rate-limits / bot-detects,
               switch to proxy. After `proxy_retry_direct_minutes`, try
               direct again. This is the default.

A proxy is "healthy" if `enabled=True AND consecutive_failures<threshold AND
not in proxy_blacklist`. After `proxy_max_failures` consecutive failures, a
proxy gets `enabled=False` (long-term disable, surfaceable in UI).

Backward compat: on first boot, if `proxy_pool` is empty AND legacy env vars
(WEBSHARE_USERNAME, WEBSHARE_PASSWORD) are set, we auto-seed the pool with
`WEBSHARE_SESSION_MIN..MAX` so the v1 single-account setup just works.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from interrogation_pipeline.config import runtime as runtime_cfg
from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.repos import (
    DirectModeRepo,
    ProxyPoolRepo,
    ProxyRepo,
)

log = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ProxySession:
    """A concrete pick from the pool. proxy_url='' means 'go direct'."""

    session_id: str          # stable identifier for blacklist tracking
    proxy_url: str           # full http://user:pass@host:port URL, or ''
    proxy_id: int | None = None    # row id in proxy_pool (None for direct)


DIRECT = ProxySession(session_id="direct", proxy_url="", proxy_id=None)


# ──────────────────────────────────────────────────────────────────────
# Bootstrap from env (backward compat)
# ──────────────────────────────────────────────────────────────────────
async def maybe_seed_from_env() -> int:
    """If the proxy pool is empty and env credentials exist, generate them."""
    async with session_scope() as session:
        repo = ProxyPoolRepo(session)
        if await repo.count() > 0:
            return 0
        if not env_settings.webshare_username or not env_settings.webshare_password:
            return 0

        rows = []
        for n in range(env_settings.webshare_session_min, env_settings.webshare_session_max + 1):
            rows.append({
                "host": env_settings.webshare_host,
                "port": env_settings.webshare_port,
                "username": f"{env_settings.webshare_username}-residential-{n}",
                "password": env_settings.webshare_password,
                "label": f"webshare-{n}",
            })
        inserted, _ = await repo.bulk_upsert(rows)
        log.info("Seeded %d proxies from WEBSHARE_* env vars.", inserted)
        return inserted


# ──────────────────────────────────────────────────────────────────────
# Smart pool
# ──────────────────────────────────────────────────────────────────────
class ProxyPool:
    """Source of fresh proxy sessions. Honors proxy_mode + tracks health."""

    async def acquire(self) -> ProxySession:
        """Return either DIRECT (proxy_url='') or a healthy proxy session.

        Logic:
          - mode='never'  → always DIRECT
          - mode='always' → always proxy (or DIRECT if pool is empty)
          - mode='auto'   → DIRECT if last direct success was within
                            proxy_retry_direct_minutes AND no recent failure;
                            else proxy
        """
        cfg = await runtime_cfg.load()
        mode = (cfg.proxy_mode or "auto").lower()

        if mode == "never":
            return DIRECT

        if mode == "auto":
            if await self._should_try_direct(cfg.proxy_retry_direct_minutes):
                return DIRECT
            # fall through to proxy pick

        # mode == 'always' or auto-after-failure → pick from pool
        return await self._pick_proxy(cfg.proxy_max_failures)

    async def _should_try_direct(self, retry_minutes: int) -> bool:
        async with session_scope() as session:
            state = await DirectModeRepo(session).get_state()
        # First-time call: try direct
        if not state.last_direct_failed_iso:
            return True
        # Successful direct call exists and is newer than the failure: try direct
        if state.last_direct_ok_iso and state.last_direct_ok_iso > (state.last_direct_failed_iso or ""):
            return True
        # Last attempt was a failure; check if cooldown has elapsed
        try:
            failed_at = datetime.fromisoformat(state.last_direct_failed_iso)
        except ValueError:
            return True
        return datetime.now(UTC) - failed_at >= timedelta(minutes=retry_minutes)

    async def _pick_proxy(self, max_failures: int) -> ProxySession:
        async with session_scope() as session:
            healthy = await ProxyPoolRepo(session).list_healthy(max_failures)
            blacklisted = await ProxyRepo(session).active_blacklist()

        live = [p for p in healthy if _session_id_of(p) not in blacklisted]
        if not live:
            # Pool exhausted — fall back to any enabled proxy (skip blacklist).
            # If even those are gone, DIRECT is better than failing.
            live = [p for p in healthy] if healthy else []
            if not live:
                return DIRECT
        choice = random.choice(live)
        return ProxySession(
            session_id=_session_id_of(choice),
            proxy_url=_url_of(choice),
            proxy_id=choice.id,
        )

    # ──── outcome reporting ────
    async def report_success(self, proxy: ProxySession) -> None:
        if proxy.proxy_id is None:
            async with session_scope() as session:
                await DirectModeRepo(session).report_success()
            return
        async with session_scope() as session:
            await ProxyPoolRepo(session).report_success(proxy.proxy_id)

    async def report_failure(self, proxy: ProxySession, reason: str = "") -> None:
        if proxy.proxy_id is None:
            async with session_scope() as session:
                await DirectModeRepo(session).report_failure()
            log.info("Direct (no-proxy) failure recorded: %s", reason[:200])
            return
        cfg = await runtime_cfg.load()
        async with session_scope() as session:
            disabled = await ProxyPoolRepo(session).report_failure(
                proxy.proxy_id, threshold=cfg.proxy_max_failures
            )
        if disabled:
            log.warning(
                "Proxy %s disabled after %d consecutive failures (%s)",
                proxy.session_id, cfg.proxy_max_failures, reason[:120],
            )

    async def blacklist(self, proxy: ProxySession, reason: str) -> None:
        """Temporary (timed) blacklist on top of the long-term enabled flag."""
        if proxy.proxy_id is None:
            return  # blacklist for DIRECT is tracked via DirectModeRepo
        cfg = await runtime_cfg.load()
        until = (
            datetime.now(UTC) + timedelta(minutes=cfg.proxy_blacklist_minutes)
        ).isoformat(timespec="seconds")
        async with session_scope() as session:
            await ProxyRepo(session).blacklist(proxy.session_id, until_iso=until, reason=reason)

    async def purge_expired(self) -> None:
        async with session_scope() as session:
            await ProxyRepo(session).purge_expired()


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _session_id_of(p) -> str:
    if p.label:
        return p.label
    return f"{p.username}@{p.host}:{p.port}"


def _url_of(p) -> str:
    if p.username and p.password:
        return f"http://{p.username}:{p.password}@{p.host}:{p.port}"
    return f"http://{p.host}:{p.port}"


# ──────────────────────────────────────────────────────────────────────
# Backward-compatible alias so existing imports keep working.
# ──────────────────────────────────────────────────────────────────────
class WebshareSessionPool(ProxyPool):
    """Deprecated alias. New code should use ProxyPool directly."""

    def __init__(self, *args, **kwargs) -> None:
        # Old API accepted username/password/etc keyword args we now ignore;
        # everything comes from config + DB.
        pass
