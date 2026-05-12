"""The daily run orchestrator.

Executes the 6 phases in order:
  1. requeue   — failed videos (attempts < N) re-enter the queue
  2. discover  — RSS per active channel, with overflow fallback to yt-dlp flat-playlist
  3. scrape    — yt-dlp captions for each pending video, with proxy rotation
  4. scan      — Haiku scan of every captioned transcript
  5. verify    — Tavily + Haiku name-correction for every accepted scan
  6. dedup     — internal + against cached Trello cards (old + new boards)

State is written to SQLite at every step so a crash never loses more than the
in-flight video.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from interrogation_pipeline.config import runtime as runtime_cfg
from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.dedup import banned, fuzzy
from interrogation_pipeline.discovery import fetch_recent_videos
from interrogation_pipeline.scan.scanner import (
    CreditExhausted,
    scan_transcript,
)
from interrogation_pipeline.scan.vtt import clean_vtt_file
from interrogation_pipeline.scrape import errors as scrape_errors
from interrogation_pipeline.scrape.cookies import pick_cookies
from interrogation_pipeline.scrape.proxies import ProxyPool, WebshareSessionPool
from interrogation_pipeline.scrape.ytdlp import (
    count_uploads,
    fetch_one,
    list_recent_uploads,
)
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.repos import (
    CaseRepo,
    ChannelRepo,
    ConfigRepo,
    CookieHealthRepo,
    RunRepo,
    ScanResultRepo,
    TrelloRepo,
    VideoRepo,
)
from interrogation_pipeline.trello.client import TrelloClient, parse_card_for_dedup

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


async def _log(run_id: int, phase: str, msg: str, level: str = "info", video_id: str | None = None):
    async with session_scope() as session:
        await RunRepo(session).log(run_id, phase, msg, level=level, video_id=video_id)


# ──────────────────────────────────────────────────────────────────────
# Phases
# ──────────────────────────────────────────────────────────────────────
async def _phase_requeue(run_id: int, max_attempts: int) -> int:
    async with session_scope() as session:
        rows = await VideoRepo(session).list_for_requeue(max_attempts)
        for v in rows:
            v.status = "pending"  # let it run again
    await _log(run_id, "requeue", f"Re-queued {len(rows)} previously-failed videos.")
    return len(rows)


async def _phase_yt_totals(run_id: int, pipeline: str | None) -> dict[str, int]:
    """Refresh per-channel YouTube upload counts (one cheap yt-dlp call each).

    Skipped for channels whose youtube_total_synced_at is < 24h old to keep
    bandwidth low across same-day repeat runs.
    """
    pool = WebshareSessionPool()
    counts = {"checked": 0, "updated": 0, "skipped_fresh": 0, "failed": 0}
    cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat(timespec="seconds")

    async with session_scope() as session:
        chans = await ChannelRepo(session).list_active(pipeline=pipeline)

    from interrogation_pipeline.discovery.rss import resolve_channel_id

    for ch in chans:
        if ch.youtube_total_synced_at and ch.youtube_total_synced_at > cutoff:
            counts["skipped_fresh"] += 1
            continue
        target_id = ch.id
        if not target_id.startswith("UC"):
            # /channel/<id>/videos requires a UC ID; resolve @handles on demand.
            try:
                resolved = await resolve_channel_id(target_id)
            except Exception:  # noqa: BLE001
                resolved = None
            if not resolved:
                counts["failed"] += 1
                continue
            target_id = resolved
        if not Path(ch.cookies_path).exists():
            counts["failed"] += 1
            continue
        counts["checked"] += 1
        proxy = await pool.acquire()
        try:
            total = await count_uploads(
                target_id, cookies_path=Path(ch.cookies_path), proxy=proxy
            )
            async with session_scope() as session:
                await ChannelRepo(session).update_youtube_total(ch.id, total)
            counts["updated"] += 1
        except Exception as e:  # noqa: BLE001
            counts["failed"] += 1
            await _log(
                run_id,
                "yt_totals",
                f"yt_total fetch failed for {ch.id}: {str(e)[:200]}",
                level="warn",
            )
    return counts


async def _phase_discover(run_id: int, lookback_hours: int, pipeline: str | None = None) -> dict[str, int]:
    """Hit RSS for every active channel; insert new VideoStubs.

    When RSS reports an overflow (15-cap with oldest still inside lookback),
    immediately invoke yt-dlp --flat-playlist for that channel only, to backfill
    the older uploads RSS couldn't show us. Cheap (one yt-dlp call per overflow
    channel) and self-correcting.
    """
    pool = WebshareSessionPool()
    async with session_scope() as session:
        chans = await ChannelRepo(session).list_active(pipeline=pipeline)
    counts = {
        "channels_checked": 0,
        "videos_discovered": 0,
        "rss_overflow_channels": 0,
        "overflow_backfilled": 0,
    }

    cutoff_dt = datetime.now(UTC) - timedelta(hours=lookback_hours)
    cutoff = cutoff_dt.isoformat(timespec="seconds")

    for ch in chans:
        counts["channels_checked"] += 1
        # Use channel.last_seen_iso minus lookback as the floor; if no last_seen,
        # use cutoff alone (initial run).
        floor = ch.last_seen_iso or ""
        effective_since = max(cutoff, floor) if floor else cutoff
        if ch.since_iso and ch.since_iso > effective_since:
            effective_since = ch.since_iso

        try:
            result = await fetch_recent_videos(ch.id, since_iso=effective_since)
        except Exception as e:  # noqa: BLE001
            await _log(run_id, "discover", f"RSS fail for {ch.id}: {e}", level="warn")
            continue

        if result.rss_overflow:
            counts["rss_overflow_channels"] += 1
            await _log(
                run_id,
                "discover",
                f"RSS overflow on {ch.id} — backfilling via yt-dlp --flat-playlist.",
                level="warn",
            )
            async with session_scope() as session:
                ch_db = await ChannelRepo(session).get(ch.id)
                if ch_db:
                    ch_db.rss_overflow = True

            # Resolve to UC ID if needed (RSS already did this internally; if
            # we don't have it on the channel record, list_recent_uploads will
            # fail. We accept the failure and try again next run.)
            target_id = ch.id
            if not target_id.startswith("UC"):
                from interrogation_pipeline.discovery.rss import resolve_channel_id
                resolved = await resolve_channel_id(target_id)
                if resolved:
                    target_id = resolved
            if target_id.startswith("UC") and Path(ch.cookies_path).exists():
                proxy = await pool.acquire()
                try:
                    extra_ids = await list_recent_uploads(
                        target_id,
                        cookies_path=Path(ch.cookies_path),
                        proxy=proxy,
                        limit=50,
                    )
                except Exception as e:  # noqa: BLE001
                    await _log(
                        run_id,
                        "discover",
                        f"Backfill failed for {ch.id}: {str(e)[:200]}",
                        level="warn",
                    )
                    extra_ids = []
                if extra_ids:
                    rows = [
                        {
                            "id": vid,
                            "channel_id": ch.id,
                            "title": None,
                            "published_iso": _utc_now(),  # unknown publish time
                            "status": "pending",
                            "attempts": 0,
                            "discovered_at": _utc_now(),
                        }
                        for vid in extra_ids
                    ]
                    async with session_scope() as session:
                        inserted = await VideoRepo(session).insert_or_ignore_many(rows)
                        counts["overflow_backfilled"] += inserted

        if not result.videos:
            continue

        rows = [
            {
                "id": s.video_id,
                "channel_id": ch.id,
                "title": s.title,
                "published_iso": s.published_iso,
                "status": "pending",
                "attempts": 0,
                "discovered_at": _utc_now(),
            }
            for s in result.videos
        ]
        async with session_scope() as session:
            inserted = await VideoRepo(session).insert_or_ignore_many(rows)
            counts["videos_discovered"] += inserted
            latest = result.videos[-1]
            await ChannelRepo(session).update_last_seen(
                ch.id, latest.published_iso, latest.video_id
            )

    return counts


async def _phase_scrape(run_id: int, concurrency: int, max_attempts: int) -> dict[str, int]:
    """Download captions for every pending video.

    Each video gets a freshly-picked cookies file (per-pipeline pool) and a
    freshly-acquired proxy session (or direct, in auto mode). Health stats
    flow back to cookie_health + proxy_pool so the UI surfaces problems.
    """
    pool = ProxyPool()
    counts = defaultdict(int)
    sem = asyncio.Semaphore(concurrency)
    cookie_threshold = (await runtime_cfg.load()).cookie_stale_threshold

    async with session_scope() as session:
        pending = await VideoRepo(session).list_pending(limit=1000)

    async def one(video):
        async with sem:
            async with session_scope() as session:
                ch = await ChannelRepo(session).get(video.channel_id)
            pipeline = ch.pipeline if ch else "P4"
            cookies_path = await pick_cookies(pipeline)
            if cookies_path is None or not cookies_path.exists():
                async with session_scope() as session:
                    await VideoRepo(session).mark_failed(
                        video.id, f"no cookies file for pipeline {pipeline}"
                    )
                counts["failed"] += 1
                await _log(
                    run_id,
                    "scrape",
                    f"No cookies for pipeline {pipeline} — drop a .txt into "
                    f"data/cookies/{pipeline.lower()}/ or data/cookies/cookies_{pipeline.lower()}.txt",
                    level="error",
                    video_id=video.id,
                )
                return

            try:
                result = await fetch_one(
                    video.id,
                    cookies_path=cookies_path,
                    out_dir=env_settings.transcripts_dir / video.channel_id,
                    pool=pool,
                )
            except scrape_errors.ScrapeError as e:
                await _handle_scrape_error(run_id, video, e, str(cookies_path), cookie_threshold)
                counts["failed" if e.retryable else "archived"] += 1
                return

            async with session_scope() as session:
                rel = str(result.vtt_path.relative_to(env_settings.data_dir).as_posix())
                await VideoRepo(session).mark_captioned(video.id, rel)
                await CookieHealthRepo(session).record_ok(str(cookies_path))
            counts["captioned"] += 1

    await asyncio.gather(*(one(v) for v in pending))
    return dict(counts)


async def _handle_scrape_error(
    run_id: int,
    video,
    err: scrape_errors.ScrapeError,
    cookies_path: str,
    cookie_threshold: int,
) -> None:
    msg = f"{type(err).__name__}: {str(err)[:300]}"
    if err.archive_reason:
        async with session_scope() as session:
            await VideoRepo(session).mark_archived(video.id, err.archive_reason)
        await _log(run_id, "scrape", msg, level="info", video_id=video.id)
        return

    async with session_scope() as session:
        await VideoRepo(session).mark_failed(video.id, msg)
        if isinstance(err, scrape_errors.CookieAuthFailure):
            newly_stale = await CookieHealthRepo(session).record_auth_failure(
                cookies_path, cookie_threshold
            )
            if newly_stale:
                await _log(
                    run_id,
                    "scrape",
                    f"Cookies marked stale: {cookies_path} — re-export needed.",
                    level="error",
                )
    await _log(run_id, "scrape", msg, level="warn", video_id=video.id)


async def _phase_scan(run_id: int, concurrency: int) -> dict[str, int]:
    counts = defaultdict(int)
    sem = asyncio.Semaphore(concurrency)

    async with session_scope() as session:
        captioned = await VideoRepo(session).list_captioned(limit=1000)

    async def one(video):
        async with sem:
            vtt_abs = env_settings.data_dir / video.vtt_path
            try:
                transcript = clean_vtt_file(vtt_abs)
            except Exception as e:  # noqa: BLE001
                await _log(run_id, "scan", f"VTT clean fail {video.id}: {e}", level="warn", video_id=video.id)
                return
            try:
                result = await scan_transcript(transcript, title=video.title or "", duration_sec=video.duration_sec)
            except CreditExhausted as e:
                await _log(run_id, "scan", f"Anthropic credits exhausted: {e}", level="error", video_id=video.id)
                raise
            except Exception as e:  # noqa: BLE001
                await _log(run_id, "scan", f"Scan fail {video.id}: {e}", level="warn", video_id=video.id)
                return

            counts["scanned"] += 1
            if result.has_homicide:
                counts["accepted"] += 1
            else:
                counts["rejected"] += 1

            async with session_scope() as session:
                await ScanResultRepo(session).upsert(
                    video.id,
                    has_homicide=result.has_homicide,
                    rejection_reason=result.rejection_reason,
                    category=result.category,
                    drama_rating=result.drama_rating,
                    drama_breakdown_json=(
                        json.dumps(result.drama_breakdown.model_dump())
                        if result.drama_breakdown
                        else None
                    ),
                    drama_summary=result.drama_summary,
                    defendant_name=result.defendant_name,
                    victim_name=result.victim_name,
                    charges=result.charges,
                    date_of_incident=result.date_of_incident,
                    location=result.location_of_incident,
                    arresting_agency=result.arresting_agency,
                    verdict=result.verdict,
                    summary=result.summary,
                    footage_types_json=json.dumps([f.model_dump() for f in result.footage_types]),
                    raw_response_json=json.dumps(result.raw_response),
                    prompt_version=result.prompt_version,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cost_usd=result.cost_usd,
                )
                await VideoRepo(session).mark_scanned(video.id)

    try:
        await asyncio.gather(*(one(v) for v in captioned))
    except CreditExhausted:
        return dict(counts) | {"credit_exhausted": 1}
    return dict(counts)


async def _phase_verify_and_dedup(run_id: int) -> dict[str, int]:
    """Build Case rows for accepted scans, verify via Tavily+Haiku, dedup."""
    from interrogation_pipeline.verify.verifier import verify_case

    counts = defaultdict(int)
    cfg = await runtime_cfg.load()

    # Pull accepted scans that don't yet have a Case row.
    async with session_scope() as session:
        # Inline SQL is fine here — it's a 1-time bulk move. Use ORM though.
        from sqlalchemy import select  # local import OK
        from interrogation_pipeline.store.models import Case as CaseModel
        from interrogation_pipeline.store.models import ScanResult as SR

        existing_case_scan_ids = {
            row[0] for row in (
                await session.execute(select(CaseModel.primary_scan_id))
            ).all()
        }
        scans = (await session.execute(
            select(SR).where(SR.has_homicide.is_(True))
        )).scalars().all()
        new_scans = [s for s in scans if s.id not in existing_case_scan_ids]

    for sr in new_scans:
        location = sr.location
        state = fuzzy.parse_state(location)
        year = fuzzy.parse_year(sr.date_of_incident)

        # Tavily verify (free if cached).
        try:
            ver = await verify_case(
                defendant=sr.defendant_name or "",
                victim=sr.victim_name,
                date=sr.date_of_incident,
                location=location,
                charges=sr.charges,
                year=year,
            )
        except Exception as e:  # noqa: BLE001
            await _log(run_id, "verify", f"Verify fail scan_id={sr.id}: {e}", level="warn")
            ver = None

        defendant_corrected = (
            ver.corrected_defendant if ver and ver.corrected_defendant else None
        ) or sr.defendant_name or "Unknown"
        victim_corrected = (
            ver.corrected_victim if ver and ver.corrected_victim else None
        ) or sr.victim_name

        async with session_scope() as session:
            case = await CaseRepo(session).add(
                primary_scan_id=sr.id,
                defendant_name=defendant_corrected,
                defendant_original=sr.defendant_name,
                victim_name=victim_corrected,
                victim_original=sr.victim_name,
                charges=sr.charges,
                location=location,
                state=state,
                year=year,
                verdict=sr.verdict,
                status="verified" if ver else "unverified",
                verification_status=ver.match_confidence if ver else None,
                verification_reasoning=ver.match_reasoning if ver else None,
                articles_json=json.dumps(ver.articles) if ver else None,
                run_id=run_id,
                banned_state=banned.is_banned_state(state, cfg.banned_states),
                banned_agency=banned.is_banned_agency(sr.arresting_agency, cfg.banned_agencies),
            )
            # Link case → video (1-to-1 for now; multi-video merging happens on dedup pass)
            from interrogation_pipeline.store.models import CaseVideo
            session.add(CaseVideo(case_id=case.id, video_id=sr.video_id))

        counts["cases_built"] += 1

    # External dedup against cached Trello cards.
    async with session_scope() as session:
        cases = await CaseRepo(session).list_by_run(run_id)
        cached = await TrelloRepo(session).all_cached(
            [b for b in (cfg.old_board_id, cfg.new_board_id) if b]
        )

    for c in cases:
        for tc in cached:
            stub_a = fuzzy.CaseStub(
                defendant_name=c.defendant_name,
                victim_name=c.victim_name,
                state=c.state,
                year=c.year,
            )
            stub_b = fuzzy.CaseStub(
                defendant_name=tc.parsed_defendant,
                victim_name=tc.parsed_victim,
                state=tc.parsed_state,
                year=tc.parsed_year,
            )
            if fuzzy.is_duplicate(stub_a, stub_b):
                tag = "exists_new" if tc.board_id == cfg.new_board_id else "exists_old"
                async with session_scope() as session:
                    case = await CaseRepo(session).get(c.id)
                    if case:
                        case.dedup_status = tag
                        case.matched_trello_card_id = tc.trello_card_id
                        case.status = "pending_review"
                counts[tag] += 1
                break
        else:
            async with session_scope() as session:
                case = await CaseRepo(session).get(c.id)
                if case:
                    case.dedup_status = "unique"
                    case.status = "pending_review"
            counts["unique"] += 1

    return dict(counts)


async def _phase_daily_counts(run_id: int) -> dict[str, int]:
    """Aggregate today's per-channel counts into ChannelDailyCount.

    Powers the Calendar grid. Re-running on the same date is safe — we UPSERT
    (delete + insert) so cumulative counts stay correct.
    """
    from sqlalchemy import delete, func, select
    from interrogation_pipeline.store.models import (
        Case as CaseModel,
        ChannelDailyCount,
        ScanResult as SR,
        Video as VideoModel,
    )

    today_iso = datetime.now(UTC).strftime("%Y-%m-%d")
    counts = {"channels_aggregated": 0}

    async with session_scope() as session:
        # Discovered today, per channel
        discovered_q = (
            select(VideoModel.channel_id, func.count(VideoModel.id))
            .where(VideoModel.discovered_at.like(f"{today_iso}%"))
            .group_by(VideoModel.channel_id)
        )
        # Scanned-and-accepted today, per channel
        accepted_q = (
            select(VideoModel.channel_id, func.count(SR.id))
            .join(VideoModel, VideoModel.id == SR.video_id)
            .where(
                SR.scanned_at.like(f"{today_iso}%"),
                SR.has_homicide.is_(True),
            )
            .group_by(VideoModel.channel_id)
        )
        # Rejected today
        rejected_q = (
            select(VideoModel.channel_id, func.count(SR.id))
            .join(VideoModel, VideoModel.id == SR.video_id)
            .where(
                SR.scanned_at.like(f"{today_iso}%"),
                SR.has_homicide.is_(False),
            )
            .group_by(VideoModel.channel_id)
        )
        # Pushed-to-trello today
        pushed_q = (
            select(VideoModel.channel_id, func.count(CaseModel.id))
            .join(SR, SR.id == CaseModel.primary_scan_id)
            .join(VideoModel, VideoModel.id == SR.video_id)
            .where(
                CaseModel.status == "pushed_to_trello",
                CaseModel.updated_at.like(f"{today_iso}%"),
            )
            .group_by(VideoModel.channel_id)
        )
        # Failed today
        failed_q = (
            select(VideoModel.channel_id, func.count(VideoModel.id))
            .where(
                VideoModel.last_attempt_iso.like(f"{today_iso}%"),
                VideoModel.status == "failed",
            )
            .group_by(VideoModel.channel_id)
        )

        agg: dict[str, dict[str, int]] = {}
        for cid, n in (await session.execute(discovered_q)).all():
            agg.setdefault(cid, {})["discovered"] = n
        for cid, n in (await session.execute(accepted_q)).all():
            agg.setdefault(cid, {})["accepted"] = n
        for cid, n in (await session.execute(rejected_q)).all():
            agg.setdefault(cid, {})["rejected"] = n
        for cid, n in (await session.execute(pushed_q)).all():
            agg.setdefault(cid, {})["pushed"] = n
        for cid, n in (await session.execute(failed_q)).all():
            agg.setdefault(cid, {})["failed"] = n

        # Replace today's rows for these channels (idempotent on same-day re-runs)
        for cid in agg:
            await session.execute(
                delete(ChannelDailyCount).where(
                    ChannelDailyCount.channel_id == cid,
                    ChannelDailyCount.date_iso == today_iso,
                )
            )

        for cid, fields in agg.items():
            session.add(
                ChannelDailyCount(
                    channel_id=cid,
                    date_iso=today_iso,
                    discovered=fields.get("discovered", 0),
                    accepted=fields.get("accepted", 0),
                    rejected=fields.get("rejected", 0),
                    pushed=fields.get("pushed", 0),
                    failed=fields.get("failed", 0),
                )
            )
            counts["channels_aggregated"] += 1

    return counts


def _looks_like_trello_id(value: str) -> bool:
    """Trello board/list IDs are 24-char hex. Reject obvious placeholders
    (empty, '...', dots-only, anything that isn't 24 hex chars)."""
    v = (value or "").strip()
    if len(v) != 24:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in v)


_TRELLO_CACHE_TTL_HOURS = 6
# Per-board cap. Newest cards matter most for dedup; if a board has more than
# this, we cache the newest N and rely on push-time Trello queries for the
# rest. Prevents the pipeline from spending hours paginating huge boards.
_TRELLO_CACHE_MAX_CARDS_PER_BOARD = 10_000
# Hard deadline across the whole phase (across both boards). Anything not
# fetched in time is left out; push-time dedup still queries Trello directly.
_TRELLO_CACHE_DEADLINE_SECONDS = 120


async def _phase_refresh_trello_cache(run_id: int) -> int:
    """Pull all cards from old + new boards into trello_card_cache for dedup.

    Fail-soft: a single bad board ID, transient network error, or 404 should
    NOT kill the whole daily run. The dedup cache is an optimization — without
    it, push-time dedup still works (it queries Trello directly).

    Auto-discovers board IDs by name when only the name is configured.

    Skips the (slow, multi-minute) full pagination if the cache was last
    refreshed within the last TTL window. Boards with 5k+ cards make this
    refresh expensive; once a day is plenty for dedup purposes.
    """
    cfg = await runtime_cfg.load()
    if not env_settings.trello_token:
        return 0

    # Freshness check — skip the pagination entirely if last refresh is recent.
    async with session_scope() as session:
        last_synced_iso = await ConfigRepo(session).get("trello_cache_synced_at", "")
    if last_synced_iso:
        try:
            last_dt = datetime.fromisoformat(last_synced_iso)
            if datetime.now(UTC) - last_dt < timedelta(hours=_TRELLO_CACHE_TTL_HOURS):
                await _log(
                    run_id,
                    "trello_cache",
                    f"cache refreshed {last_synced_iso} (< {_TRELLO_CACHE_TTL_HOURS}h ago) — skipping. "
                    f"Push-time dedup still queries Trello directly.",
                    level="info",
                )
                return 0
        except ValueError:
            pass  # malformed timestamp — fall through and refresh

    total = 0
    async with TrelloClient() as tc:
        boards: list[tuple[str, str]] = []
        for label, bid, bname in (
            ("old", cfg.old_board_id, cfg.old_board_name),
            ("new", cfg.new_board_id, cfg.new_board_name),
        ):
            if _looks_like_trello_id(bid):
                boards.append((label, bid))
                continue
            if bid:  # user typed something that doesn't look like an ID
                await _log(
                    run_id,
                    "trello_cache",
                    f"skipping {label} board: '{bid}' is not a valid Trello board ID "
                    f"(expected 24-char hex). Edit backend/.env or leave blank to "
                    f"auto-discover by name.",
                    level="warn",
                )
                continue
            # No ID set — try to resolve by name.
            if not bname:
                continue
            try:
                board = await tc.find_board_by_name(bname)
            except Exception as e:  # noqa: BLE001
                await _log(
                    run_id,
                    "trello_cache",
                    f"lookup for {label} board '{bname}' failed: {str(e)[:200]}",
                    level="warn",
                )
                continue
            if not board:
                await _log(
                    run_id,
                    "trello_cache",
                    f"{label} board '{bname}' not found on this Trello account — "
                    f"skipping dedup against it. (Open the board and copy the 24-char "
                    f"ID from trello.com/b/<shortcode>.json if auto-discover keeps failing.)",
                    level="warn",
                )
                continue
            resolved_id = board["id"]
            await runtime_cfg.patch({f"{label}_board_id": resolved_id})
            boards.append((label, resolved_id))

        succeeded = False
        deadline = datetime.now(UTC) + timedelta(seconds=_TRELLO_CACHE_DEADLINE_SECONDS)
        for label, bid in boards:
            if datetime.now(UTC) >= deadline:
                await _log(
                    run_id,
                    "trello_cache",
                    f"hit {_TRELLO_CACHE_DEADLINE_SECONDS}s phase deadline before "
                    f"reaching {label} board {bid}. Push-time dedup will still "
                    f"query Trello directly for any case sent to it.",
                    level="warn",
                )
                break
            try:
                cards = await asyncio.wait_for(
                    tc.list_all_cards(
                        bid,
                        include_archived=True,
                        max_cards=_TRELLO_CACHE_MAX_CARDS_PER_BOARD,
                    ),
                    timeout=(deadline - datetime.now(UTC)).total_seconds(),
                )
                parsed = [parse_card_for_dedup(c) for c in cards]
                async with session_scope() as session:
                    await TrelloRepo(session).replace_cache_for_board(bid, parsed)
                total += len(cards)
                succeeded = True
                if len(cards) >= _TRELLO_CACHE_MAX_CARDS_PER_BOARD:
                    await _log(
                        run_id,
                        "trello_cache",
                        f"{label} board {bid}: cached newest {len(cards)} cards "
                        f"(per-board cap). Older cards aren't in the pre-cache; "
                        f"push-time dedup still queries Trello directly.",
                        level="info",
                    )
            except asyncio.TimeoutError:
                await _log(
                    run_id,
                    "trello_cache",
                    f"timed out fetching {label} board {bid} within the phase "
                    f"deadline. Partial cache (if any) was discarded.",
                    level="warn",
                )
            except Exception as e:  # noqa: BLE001
                await _log(
                    run_id,
                    "trello_cache",
                    f"could not refresh {label} board {bid}: {str(e)[:200]}. "
                    f"Continuing without pre-cached dedup for this board.",
                    level="warn",
                )

    if succeeded:
        async with session_scope() as session:
            await ConfigRepo(session).set(
                "trello_cache_synced_at", datetime.now(UTC).isoformat(timespec="seconds")
            )
    return total


# ──────────────────────────────────────────────────────────────────────
# The orchestrator
# ──────────────────────────────────────────────────────────────────────
async def run_daily(*, trigger: str = "scheduled", pipeline: str | None = "P4") -> dict[str, Any]:
    """End-to-end daily run. Returns the final counts."""
    cfg = await runtime_cfg.load()
    log.info("Starting daily run (trigger=%s)", trigger)

    async with session_scope() as session:
        run = await RunRepo(session).start(trigger=trigger)
        run_id = run.id

    counts: dict[str, Any] = {}
    final_status = "success"
    error: str | None = None

    try:
        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "requeue")
        counts["requeued"] = await _phase_requeue(run_id, cfg.video_max_attempts)

        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "yt_totals")
        counts.update({"yt_totals_" + k: v for k, v in (await _phase_yt_totals(run_id, pipeline)).items()})

        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "trello_cache")
        counts["trello_cards_cached"] = await _phase_refresh_trello_cache(run_id)

        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "discover")
        counts.update(await _phase_discover(run_id, cfg.lookback_hours, pipeline=pipeline))

        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "scrape")
        counts.update(await _phase_scrape(run_id, cfg.scrape_concurrency, cfg.video_max_attempts))

        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "scan")
        scan_counts = await _phase_scan(run_id, cfg.scan_concurrency)
        counts.update(scan_counts)
        if scan_counts.get("credit_exhausted"):
            final_status = "partial"
            error = "Anthropic credits exhausted mid-scan"

        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "verify_dedup")
        counts.update(await _phase_verify_and_dedup(run_id))

        async with session_scope() as session:
            await RunRepo(session).set_phase(run_id, "daily_counts")
        counts.update(await _phase_daily_counts(run_id))

    except Exception as e:  # noqa: BLE001
        log.exception("Run failed")
        final_status = "failed"
        error = f"{type(e).__name__}: {e}"

    async with session_scope() as session:
        await RunRepo(session).finalize(run_id, final_status, counts, error=error)

    log.info("Run %d finished status=%s counts=%s", run_id, final_status, counts)
    return {"run_id": run_id, "status": final_status, "counts": counts, "error": error}
