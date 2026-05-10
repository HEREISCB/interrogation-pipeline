"""Webshare residential session pool with DB-backed blacklist.

Mirrors handoff §5.2: each yt-dlp call uses a fresh sticky session, and any
session that returns rate-limited goes on a 30-minute blacklist (configurable).
The pool draws session IDs from the configured range and skips blacklisted
ones.

Why DB-backed: the scheduler can crash and restart, but we shouldn't lose the
blacklist (the offending session is still hot at YouTube). Persisting also
lets the dashboard show the user what's burned.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.repos import ProxyRepo


@dataclass(slots=True, frozen=True)
class ProxySession:
    session_id: str           # 'mryzxzjm-residential-37'
    proxy_url: str            # 'http://mryzxzjm-residential-37:pass@p.webshare.io:80'


class WebshareSessionPool:
    """Thread-safe-enough source of fresh proxy sessions.

    Not actually thread-safe under concurrency stress — we rely on async
    serialization at the runner level (concurrency cap = scrape_concurrency).
    Multiple concurrent calls within that cap may pick the same session
    occasionally; that's fine because Webshare sessions accept many concurrent
    connections.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        host: str | None = None,
        port: int | None = None,
        session_min: int | None = None,
        session_max: int | None = None,
        blacklist_minutes: int = 30,
    ) -> None:
        self.username = username or env_settings.webshare_username
        self.password = password or env_settings.webshare_password
        self.host = host or env_settings.webshare_host
        self.port = port or env_settings.webshare_port
        self.session_min = session_min or env_settings.webshare_session_min
        self.session_max = session_max or env_settings.webshare_session_max
        self.blacklist_minutes = blacklist_minutes

    def _build(self, n: int) -> ProxySession:
        sid = f"{self.username}-residential-{n}"
        url = f"http://{sid}:{self.password}@{self.host}:{self.port}"
        return ProxySession(session_id=sid, proxy_url=url)

    def _direct(self) -> ProxySession:
        """Sentinel session = no proxy. Used when WEBSHARE_PASSWORD is unset
        so we can still smoke-test without a Webshare account."""
        return ProxySession(session_id="direct", proxy_url="")

    async def acquire(self) -> ProxySession:
        """Return a non-blacklisted session.

        Picks at random from the live pool. Falls back to any session if the
        whole pool happens to be blacklisted (extreme case — at that point
        retries will fail too and the runner will surface the issue).
        """
        if not self.password or not self.username:
            return self._direct()
        async with session_scope() as session:
            blacklisted = await ProxyRepo(session).active_blacklist()

        all_ids = {f"{self.username}-residential-{n}" for n in range(self.session_min, self.session_max + 1)}
        live = list(all_ids - blacklisted)
        if not live:
            live = list(all_ids)
        chosen_id = random.choice(live)
        n = int(chosen_id.rsplit("-", 1)[-1])
        return self._build(n)

    async def blacklist(self, session_id: str, reason: str) -> None:
        until = (datetime.now(UTC) + timedelta(minutes=self.blacklist_minutes)).isoformat(
            timespec="seconds"
        )
        async with session_scope() as session:
            await ProxyRepo(session).blacklist(session_id, until_iso=until, reason=reason)

    async def purge_expired(self) -> None:
        async with session_scope() as session:
            await ProxyRepo(session).purge_expired()
