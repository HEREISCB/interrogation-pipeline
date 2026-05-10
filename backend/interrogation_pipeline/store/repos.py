"""Repository classes — every read/write to the DB goes through one of these.

Keeps SQL knowledge bounded to this module so the rest of the codebase only
needs to think in terms of domain operations.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from interrogation_pipeline.store.models import (
    Case,
    Channel,
    ChannelDailyCount,
    ConfigEntry,
    CookieHealth,
    ProxyBlacklist,
    Run,
    RunEvent,
    ScanResult,
    TavilyCache,
    TrelloCardCache,
    TrelloPushLog,
    Video,
    utc_now_iso,
)


# ──────────────────────────────────────────────────────────────────────
class ChannelRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def list_active(self, pipeline: Optional[str] = None) -> list[Channel]:
        q = select(Channel).where(Channel.active.is_(True))
        if pipeline:
            q = q.where(Channel.pipeline == pipeline)
        return list((await self.s.execute(q)).scalars())

    async def list_all(self) -> list[Channel]:
        return list((await self.s.execute(select(Channel))).scalars())

    async def get(self, channel_id: str) -> Optional[Channel]:
        return await self.s.get(Channel, channel_id)

    async def upsert(self, **fields: Any) -> Channel:
        ch = await self.s.get(Channel, fields["id"])
        if ch is None:
            ch = Channel(**fields)
            self.s.add(ch)
        else:
            for k, v in fields.items():
                if k != "id":
                    setattr(ch, k, v)
        return ch

    async def set_active(self, channel_id: str, active: bool) -> None:
        await self.s.execute(
            update(Channel).where(Channel.id == channel_id).values(active=active)
        )

    async def update_last_seen(
        self, channel_id: str, last_seen_iso: str, last_seen_video_id: str
    ) -> None:
        await self.s.execute(
            update(Channel)
            .where(Channel.id == channel_id)
            .values(last_seen_iso=last_seen_iso, last_seen_video_id=last_seen_video_id)
        )

    async def update_youtube_total(self, channel_id: str, total: int) -> None:
        await self.s.execute(
            update(Channel)
            .where(Channel.id == channel_id)
            .values(youtube_total_count=total, youtube_total_synced_at=utc_now_iso())
        )

    async def delete(self, channel_id: str) -> None:
        await self.set_active(channel_id, False)


# ──────────────────────────────────────────────────────────────────────
class VideoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def insert_or_ignore_many(self, rows: Iterable[dict[str, Any]]) -> int:
        """Bulk INSERT OR IGNORE; returns count actually inserted (best effort)."""
        rows_list = list(rows)
        if not rows_list:
            return 0
        stmt = sqlite_insert(Video).values(rows_list)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        result = await self.s.execute(stmt)
        return result.rowcount or 0

    async def get(self, video_id: str) -> Optional[Video]:
        return await self.s.get(Video, video_id)

    async def list_pending(self, limit: int = 200) -> list[Video]:
        q = select(Video).where(Video.status == "pending").limit(limit)
        return list((await self.s.execute(q)).scalars())

    async def list_for_requeue(self, max_attempts: int) -> list[Video]:
        q = select(Video).where(
            and_(Video.status == "failed", Video.attempts < max_attempts)
        )
        return list((await self.s.execute(q)).scalars())

    async def list_captioned(self, limit: int = 500) -> list[Video]:
        q = select(Video).where(Video.status == "captioned").limit(limit)
        return list((await self.s.execute(q)).scalars())

    async def mark_captioned(self, video_id: str, vtt_path: str) -> None:
        await self.s.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(status="captioned", vtt_path=vtt_path, last_attempt_iso=utc_now_iso())
        )

    async def mark_scanned(self, video_id: str) -> None:
        await self.s.execute(
            update(Video).where(Video.id == video_id).values(status="scanned")
        )

    async def mark_archived(self, video_id: str, reason: str) -> None:
        await self.s.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(status="archived", archive_reason=reason, last_attempt_iso=utc_now_iso())
        )

    async def mark_failed(self, video_id: str, error: str) -> None:
        v = await self.s.get(Video, video_id)
        if v is None:
            return
        v.status = "failed"
        v.attempts = (v.attempts or 0) + 1
        v.last_error = error
        v.last_attempt_iso = utc_now_iso()


# ──────────────────────────────────────────────────────────────────────
class ScanResultRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def upsert(self, video_id: str, **fields: Any) -> ScanResult:
        existing = await self.s.execute(
            select(ScanResult).where(ScanResult.video_id == video_id)
        )
        sr = existing.scalar_one_or_none()
        if sr is None:
            sr = ScanResult(video_id=video_id, **fields)
            self.s.add(sr)
        else:
            for k, v in fields.items():
                setattr(sr, k, v)
        return sr

    async def get_for_video(self, video_id: str) -> Optional[ScanResult]:
        result = await self.s.execute(
            select(ScanResult).where(ScanResult.video_id == video_id)
        )
        return result.scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────────
class CaseRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def add(self, **fields: Any) -> Case:
        c = Case(**fields)
        self.s.add(c)
        await self.s.flush()
        return c

    async def get(self, case_id: int) -> Optional[Case]:
        return await self.s.get(Case, case_id)

    async def list_by_run(
        self, run_id: int, status: Optional[str] = None
    ) -> list[Case]:
        q = select(Case).where(Case.run_id == run_id)
        if status:
            q = q.where(Case.status == status)
        return list((await self.s.execute(q)).scalars())

    async def list_for_today(self, run_id: int) -> dict[str, list[Case]]:
        """Bucket cases by their dashboard category for the Today page."""
        rows = await self.list_by_run(run_id)
        result: dict[str, list[Case]] = {
            "accepted": [],
            "rejected": [],
            "duplicate_old": [],
            "duplicate_new": [],
        }
        for c in rows:
            if c.status in {"merged_into"}:
                continue
            if c.dedup_status == "exists_old":
                result["duplicate_old"].append(c)
            elif c.dedup_status == "exists_new":
                result["duplicate_new"].append(c)
            else:
                result["accepted"].append(c)
        return result

    async def update_status(self, case_id: int, status: str) -> None:
        await self.s.execute(
            update(Case)
            .where(Case.id == case_id)
            .values(status=status, updated_at=utc_now_iso())
        )

    async def set_trello(self, case_id: int, trello_card_id: str) -> None:
        await self.s.execute(
            update(Case)
            .where(Case.id == case_id)
            .values(
                trello_card_id=trello_card_id,
                status="pushed_to_trello",
                updated_at=utc_now_iso(),
            )
        )


# ──────────────────────────────────────────────────────────────────────
class RunRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def start(self, trigger: str = "scheduled") -> Run:
        r = Run(trigger=trigger, status="running", phase="init")
        self.s.add(r)
        await self.s.flush()
        return r

    async def finalize(
        self, run_id: int, status: str, counts: dict[str, int], error: Optional[str] = None
    ) -> None:
        await self.s.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status=status,
                completed_at=utc_now_iso(),
                counts_json=json.dumps(counts),
                error=error,
            )
        )

    async def set_phase(self, run_id: int, phase: str) -> None:
        await self.s.execute(update(Run).where(Run.id == run_id).values(phase=phase))

    async def list_recent(self, limit: int = 50) -> list[Run]:
        q = select(Run).order_by(Run.started_at.desc()).limit(limit)
        return list((await self.s.execute(q)).scalars())

    async def get(self, run_id: int) -> Optional[Run]:
        return await self.s.get(Run, run_id)

    async def latest(self) -> Optional[Run]:
        q = select(Run).order_by(Run.started_at.desc()).limit(1)
        return (await self.s.execute(q)).scalar_one_or_none()

    async def log(
        self,
        run_id: int,
        phase: str,
        message: str,
        level: str = "info",
        video_id: Optional[str] = None,
    ) -> None:
        self.s.add(
            RunEvent(
                run_id=run_id, phase=phase, level=level, message=message, video_id=video_id
            )
        )

    async def events(
        self, run_id: int, level: Optional[str] = None, limit: int = 200
    ) -> list[RunEvent]:
        q = select(RunEvent).where(RunEvent.run_id == run_id)
        if level:
            q = q.where(RunEvent.level == level)
        q = q.order_by(RunEvent.ts.desc()).limit(limit)
        return list((await self.s.execute(q)).scalars())


# ──────────────────────────────────────────────────────────────────────
class ConfigRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, key: str, default: Any = None) -> Any:
        row = await self.s.get(ConfigEntry, key)
        if row is None:
            return default
        return json.loads(row.value_json)

    async def set(self, key: str, value: Any) -> None:
        row = await self.s.get(ConfigEntry, key)
        if row is None:
            self.s.add(ConfigEntry(key=key, value_json=json.dumps(value)))
        else:
            row.value_json = json.dumps(value)
            row.updated_at = utc_now_iso()

    async def all(self) -> dict[str, Any]:
        rows = (await self.s.execute(select(ConfigEntry))).scalars()
        return {r.key: json.loads(r.value_json) for r in rows}


# ──────────────────────────────────────────────────────────────────────
class TrelloRepo:
    """Local cache of Trello cards (for dedup) + push log."""

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def replace_cache_for_board(
        self, board_id: str, cards: list[dict[str, Any]]
    ) -> None:
        await self.s.execute(
            delete(TrelloCardCache).where(TrelloCardCache.board_id == board_id)
        )
        for c in cards:
            self.s.add(TrelloCardCache(**c))

    async def all_cached(self, board_ids: list[str]) -> list[TrelloCardCache]:
        if not board_ids:
            return []
        q = select(TrelloCardCache).where(TrelloCardCache.board_id.in_(board_ids))
        return list((await self.s.execute(q)).scalars())

    async def log_push(
        self,
        case_id: int,
        board_id: str,
        list_id: str,
        trello_card_id: str,
        pushed_by: str = "user",
    ) -> None:
        self.s.add(
            TrelloPushLog(
                case_id=case_id,
                board_id=board_id,
                list_id=list_id,
                trello_card_id=trello_card_id,
                pushed_by=pushed_by,
            )
        )


# ──────────────────────────────────────────────────────────────────────
class ProxyRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def blacklist(self, session_id: str, until_iso: str, reason: str) -> None:
        existing = await self.s.get(ProxyBlacklist, session_id)
        if existing:
            existing.blacklisted_until = until_iso
            existing.reason = reason
        else:
            self.s.add(
                ProxyBlacklist(
                    session_id=session_id, blacklisted_until=until_iso, reason=reason
                )
            )

    async def active_blacklist(self) -> set[str]:
        now = utc_now_iso()
        q = select(ProxyBlacklist).where(ProxyBlacklist.blacklisted_until > now)
        rows = (await self.s.execute(q)).scalars()
        return {r.session_id for r in rows}

    async def purge_expired(self) -> None:
        now = utc_now_iso()
        await self.s.execute(
            delete(ProxyBlacklist).where(ProxyBlacklist.blacklisted_until <= now)
        )


# ──────────────────────────────────────────────────────────────────────
class CookieHealthRepo:
    """Tracks per-cookie-file auth health to drive the 'cookies stale' banner."""

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def record_ok(self, cookies_path: str) -> None:
        ch = await self.s.get(CookieHealth, cookies_path)
        if ch is None:
            ch = CookieHealth(cookies_path=cookies_path)
            self.s.add(ch)
        ch.consecutive_auth_failures = 0
        ch.last_ok_at = utc_now_iso()
        ch.stale = False

    async def record_auth_failure(self, cookies_path: str, threshold: int) -> bool:
        """Returns True iff this failure pushed the file across the stale threshold."""
        ch = await self.s.get(CookieHealth, cookies_path)
        if ch is None:
            ch = CookieHealth(cookies_path=cookies_path)
            self.s.add(ch)
        ch.consecutive_auth_failures = (ch.consecutive_auth_failures or 0) + 1
        ch.last_failure_at = utc_now_iso()
        newly_stale = (
            not ch.stale and ch.consecutive_auth_failures >= threshold
        )
        if ch.consecutive_auth_failures >= threshold:
            ch.stale = True
        return newly_stale

    async def stale_files(self) -> list[CookieHealth]:
        q = select(CookieHealth).where(CookieHealth.stale.is_(True))
        return list((await self.s.execute(q)).scalars())


class TavilyRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, query_hash: str) -> Optional[TavilyCache]:
        return await self.s.get(TavilyCache, query_hash)

    async def put(self, query_hash: str, query: str, articles: list[dict[str, Any]]) -> None:
        existing = await self.s.get(TavilyCache, query_hash)
        if existing:
            existing.articles_json = json.dumps(articles)
            existing.fetched_at = utc_now_iso()
        else:
            self.s.add(
                TavilyCache(
                    query_hash=query_hash, query=query, articles_json=json.dumps(articles)
                )
            )


# ──────────────────────────────────────────────────────────────────────
class StatsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def p4_overview(self) -> dict[str, int]:
        chans = await self.s.execute(
            select(func.coalesce(func.sum(Channel.youtube_total_count), 0)).where(
                and_(Channel.pipeline == "P4", Channel.active.is_(True))
            )
        )
        yt_total = chans.scalar_one() or 0

        in_system = (
            await self.s.execute(
                select(func.count(Video.id))
                .join(Channel, Channel.id == Video.channel_id)
                .where(Channel.pipeline == "P4")
            )
        ).scalar_one()

        captioned = (
            await self.s.execute(
                select(func.count(Video.id))
                .join(Channel, Channel.id == Video.channel_id)
                .where(and_(Channel.pipeline == "P4", Video.status.in_(["captioned", "scanned"])))
            )
        ).scalar_one()

        scanned = (
            await self.s.execute(
                select(func.count(Video.id))
                .join(Channel, Channel.id == Video.channel_id)
                .where(and_(Channel.pipeline == "P4", Video.status == "scanned"))
            )
        ).scalar_one()

        accepted = (
            await self.s.execute(
                select(func.count(ScanResult.id))
                .join(Video, Video.id == ScanResult.video_id)
                .join(Channel, Channel.id == Video.channel_id)
                .where(and_(Channel.pipeline == "P4", ScanResult.has_homicide.is_(True)))
            )
        ).scalar_one()

        pushed = (
            await self.s.execute(
                select(func.count(Case.id)).where(Case.status == "pushed_to_trello")
            )
        ).scalar_one()

        failed = (
            await self.s.execute(
                select(func.count(Video.id))
                .join(Channel, Channel.id == Video.channel_id)
                .where(and_(Channel.pipeline == "P4", Video.status == "failed"))
            )
        ).scalar_one()

        return {
            "youtube_total": int(yt_total),
            "in_system": int(in_system),
            "captioned": int(captioned),
            "scanned": int(scanned),
            "accepted": int(accepted),
            "pushed_to_trello": int(pushed),
            "failed_stuck": int(failed),
        }

    async def days(self, from_iso: str, to_iso: str) -> list[dict[str, Any]]:
        """Per-day counts powering the calendar grid."""
        q = (
            select(
                ChannelDailyCount.date_iso,
                func.sum(ChannelDailyCount.discovered).label("discovered"),
                func.sum(ChannelDailyCount.accepted).label("accepted"),
                func.sum(ChannelDailyCount.rejected).label("rejected"),
                func.sum(ChannelDailyCount.pushed).label("pushed"),
                func.sum(ChannelDailyCount.failed).label("failed"),
            )
            .where(
                and_(
                    ChannelDailyCount.date_iso >= from_iso,
                    ChannelDailyCount.date_iso <= to_iso,
                )
            )
            .group_by(ChannelDailyCount.date_iso)
            .order_by(ChannelDailyCount.date_iso)
        )
        rows = (await self.s.execute(q)).all()
        return [
            {
                "date_iso": r.date_iso,
                "counts": {
                    "discovered": int(r.discovered or 0),
                    "accepted": int(r.accepted or 0),
                    "rejected": int(r.rejected or 0),
                    "pushed": int(r.pushed or 0),
                    "failed": int(r.failed or 0),
                },
            }
            for r in rows
        ]
