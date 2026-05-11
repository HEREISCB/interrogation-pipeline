"""REST endpoint routers — thin layer over the repos.

For v1 most endpoints return real DB state; the ones that depend on the
scheduler / scraper still return stubs marked TODO so the frontend can be
wired up while the worker modules are being built.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from interrogation_pipeline.config import runtime as runtime_cfg
from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.discovery.rss import rss_url_for
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.repos import (
    CaseRepo,
    ChannelRepo,
    CookieHealthRepo,
    ProxyPoolRepo,
    RunRepo,
    StatsRepo,
)


# ──────────────────────────────────────────────────────────────────────
# Today
# ──────────────────────────────────────────────────────────────────────
today_router = APIRouter(tags=["today"])


def _serialize_case(c) -> dict[str, Any]:
    return {
        "id": c.id,
        "defendant": c.defendant_name,
        "victim": c.victim_name,
        "charges": c.charges,
        "location": c.location,
        "state": c.state,
        "year": c.year,
        "verdict": c.verdict,
        "status": c.status,
        "dedup_status": c.dedup_status,
        "trello_card_id": c.trello_card_id,
        "matched_trello_card_id": c.matched_trello_card_id,
        "verification_status": c.verification_status,
        "banned_state": c.banned_state,
        "banned_agency": c.banned_agency,
        "articles": json.loads(c.articles_json) if c.articles_json else [],
        "created_at": c.created_at,
    }


@today_router.get("/today")
async def today() -> dict[str, Any]:
    async with session_scope() as session:
        run_repo = RunRepo(session)
        case_repo = CaseRepo(session)
        latest = await run_repo.latest()
        if latest is None:
            return {
                "run_id": None,
                "date_iso": None,
                "counts": {},
                "accepted": [],
                "rejected": [],
                "duplicate_old": [],
                "duplicate_new": [],
            }
        buckets = await case_repo.list_for_today(latest.id)
        return {
            "run_id": latest.id,
            "date_iso": latest.started_at,
            "counts": json.loads(latest.counts_json) if latest.counts_json else {},
            "accepted": [_serialize_case(c) for c in buckets["accepted"]],
            "rejected": [_serialize_case(c) for c in buckets["rejected"]],
            "duplicate_old": [_serialize_case(c) for c in buckets["duplicate_old"]],
            "duplicate_new": [_serialize_case(c) for c in buckets["duplicate_new"]],
        }


@today_router.get("/days")
async def days(from_: str | None = None, to: str | None = None) -> list[dict[str, Any]]:
    async with session_scope() as session:
        if not from_ or not to:
            return []
        return await StatsRepo(session).days(from_, to)


# ──────────────────────────────────────────────────────────────────────
# Cases
# ──────────────────────────────────────────────────────────────────────
cases_router = APIRouter(tags=["cases"], prefix="/cases")


@cases_router.get("/{case_id}")
async def get_case(case_id: int) -> dict[str, Any]:
    async with session_scope() as session:
        case = await CaseRepo(session).get(case_id)
        if case is None:
            raise HTTPException(404, "case not found")
        return _serialize_case(case)


class PushBody(BaseModel):
    list_id: Optional[str] = None


@cases_router.post("/{case_id}/push-to-trello")
async def push_to_trello(case_id: int, body: PushBody | None = None) -> dict[str, Any]:
    """Push a single case to the new (ULF) Trello board.

    Performs a last-mile dedup re-check against the cached new-board cards
    before creating, so a fast double-click doesn't make duplicates.
    """
    from interrogation_pipeline.config import runtime as runtime_cfg
    from interrogation_pipeline.dedup import fuzzy
    from interrogation_pipeline.store.repos import TrelloRepo
    from interrogation_pipeline.trello.card_format import build_card_description
    from interrogation_pipeline.trello.client import TrelloClient

    cfg = await runtime_cfg.load()

    async with session_scope() as session:
        case = await CaseRepo(session).get(case_id)
        if case is None:
            raise HTTPException(404, "case not found")
        if case.status == "pushed_to_trello":
            return {
                "status": "already_pushed",
                "trello_card_id": case.trello_card_id,
            }

    target_board_id = cfg.new_board_id
    target_list_id = (body.list_id if body else None) or cfg.new_list_id

    if not env_settings.trello_token:
        raise HTTPException(503, "Trello token not configured (.env: TRELLO_TOKEN)")

    async with TrelloClient() as tc:
        # Auto-discover IDs by name if env didn't set them.
        if not target_board_id and cfg.new_board_name:
            board = await tc.find_board_by_name(cfg.new_board_name)
            if board is None:
                raise HTTPException(503, f"Trello board '{cfg.new_board_name}' not found")
            target_board_id = board["id"]
            await runtime_cfg.patch({"new_board_id": target_board_id})
        if not target_list_id and target_board_id and cfg.new_list_name:
            lst = await tc.find_list_by_name(target_board_id, cfg.new_list_name)
            if lst is None:
                raise HTTPException(
                    503, f"Trello list '{cfg.new_list_name}' not found on board"
                )
            target_list_id = lst["id"]
            await runtime_cfg.patch({"new_list_id": target_list_id})

        # Last-mile dedup against cached cards on the new board only.
        async with session_scope() as session:
            cached = await TrelloRepo(session).all_cached([target_board_id])
        for tc_card in cached:
            if fuzzy.is_duplicate(
                fuzzy.CaseStub(
                    defendant_name=case.defendant_name,
                    victim_name=case.victim_name,
                    state=case.state,
                    year=case.year,
                ),
                fuzzy.CaseStub(
                    defendant_name=tc_card.parsed_defendant,
                    victim_name=tc_card.parsed_victim,
                    state=tc_card.parsed_state,
                    year=tc_card.parsed_year,
                ),
            ):
                async with session_scope() as session:
                    await CaseRepo(session).update_status(case_id, "pushed_to_trello")
                return {
                    "status": "deduped_against_existing",
                    "trello_card_id": tc_card.trello_card_id,
                }

        # Build description + create.
        from sqlalchemy import select
        from interrogation_pipeline.store.models import (
            CaseVideo,
            ScanResult as SRModel,
        )

        async with session_scope() as session:
            primary_scan = await session.get(SRModel, case.primary_scan_id)
            cv_row = (
                await session.execute(
                    select(CaseVideo.video_id).where(CaseVideo.case_id == case.id)
                )
            ).first()
            video_id = (
                cv_row[0]
                if cv_row
                else (primary_scan.video_id if primary_scan else None)
            )

        desc = build_card_description(
            defendant=case.defendant_name,
            victim=case.victim_name,
            charges=case.charges,
            date_of_incident=primary_scan.date_of_incident if primary_scan else None,
            location=case.location,
            arresting_agency=primary_scan.arresting_agency if primary_scan else None,
            verdict=case.verdict,
            video_url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            drama_rating=primary_scan.drama_rating if primary_scan else None,
            category=primary_scan.category if primary_scan else None,
            channel=None,
            pipeline="P4",
            summary=primary_scan.summary if primary_scan else None,
            article_urls=[a.get("url") for a in (json.loads(case.articles_json) if case.articles_json else [])],
            verification_status=case.verification_status,
            banned_state=case.banned_state,
            banned_agency=case.banned_agency,
        )

        created = await tc.create_card(
            list_id=target_list_id,
            name=case.defendant_name,
            desc=desc,
        )

    async with session_scope() as session:
        await CaseRepo(session).set_trello(case_id, created["id"])
        await TrelloRepo(session).log_push(
            case_id=case_id,
            board_id=target_board_id,
            list_id=target_list_id,
            trello_card_id=created["id"],
        )

    return {
        "status": "pushed",
        "trello_card_id": created["id"],
        "trello_url": created.get("shortUrl"),
    }


@cases_router.post("/{case_id}/skip")
async def skip(case_id: int) -> dict[str, str]:
    async with session_scope() as session:
        await CaseRepo(session).update_status(case_id, "skipped")
    return {"status": "skipped"}


@cases_router.post("/{case_id}/mark-reviewed")
async def mark_reviewed(case_id: int) -> dict[str, str]:
    async with session_scope() as session:
        await CaseRepo(session).update_status(case_id, "reviewed")
    return {"status": "reviewed"}


# ──────────────────────────────────────────────────────────────────────
# Channels
# ──────────────────────────────────────────────────────────────────────
channels_router = APIRouter(tags=["channels"], prefix="/channels")


class ChannelIn(BaseModel):
    id: str
    display_name: Optional[str] = None
    pipeline: str = "P4"
    since_iso: Optional[str] = None
    cookies_path: Optional[str] = None


@channels_router.get("")
async def list_channels() -> list[dict[str, Any]]:
    async with session_scope() as session:
        chans = await ChannelRepo(session).list_all()
        return [
            {
                "id": c.id,
                "display_name": c.display_name,
                "pipeline": c.pipeline,
                "rss_url": c.rss_url,
                "since_iso": c.since_iso,
                "last_seen_iso": c.last_seen_iso,
                "cookies_path": c.cookies_path,
                "youtube_total_count": c.youtube_total_count,
                "youtube_total_synced_at": c.youtube_total_synced_at,
                "active": c.active,
            }
            for c in chans
        ]


@channels_router.post("")
async def add_channel(body: ChannelIn) -> dict[str, Any]:
    cookies = body.cookies_path or str(env_settings.cookies_dir / f"cookies_{body.pipeline.lower()}.txt")
    async with session_scope() as session:
        ch = await ChannelRepo(session).upsert(
            id=body.id,
            display_name=body.display_name or body.id,
            pipeline=body.pipeline,
            rss_url=rss_url_for(body.id),
            since_iso=body.since_iso,
            cookies_path=cookies,
            active=True,
        )
    return {"id": ch.id, "ok": True}


class ChannelPatch(BaseModel):
    pipeline: Optional[str] = None
    since_iso: Optional[str] = None
    active: Optional[bool] = None
    cookies_path: Optional[str] = None
    display_name: Optional[str] = None


@channels_router.patch("/{channel_id}")
async def patch_channel(channel_id: str, body: ChannelPatch) -> dict[str, str]:
    async with session_scope() as session:
        repo = ChannelRepo(session)
        existing = await repo.get(channel_id)
        if existing is None:
            raise HTTPException(404, "channel not found")
        updates: dict[str, Any] = body.model_dump(exclude_none=True)
        await repo.upsert(id=channel_id, **updates)
    return {"ok": "true"}


@channels_router.delete("/{channel_id}")
async def delete_channel(channel_id: str) -> dict[str, str]:
    async with session_scope() as session:
        await ChannelRepo(session).delete(channel_id)
    return {"ok": "true"}


# ──────────────────────────────────────────────────────────────────────
# Runs
# ──────────────────────────────────────────────────────────────────────
runs_router = APIRouter(tags=["runs"], prefix="/runs")


@runs_router.get("")
async def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    async with session_scope() as session:
        runs = await RunRepo(session).list_recent(limit=limit)
        return [
            {
                "id": r.id,
                "trigger": r.trigger,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "status": r.status,
                "phase": r.phase,
                "counts": json.loads(r.counts_json) if r.counts_json else {},
                "error": r.error,
            }
            for r in runs
        ]


@runs_router.get("/{run_id}/events")
async def run_events(run_id: int, level: Optional[str] = None) -> list[dict[str, Any]]:
    async with session_scope() as session:
        evs = await RunRepo(session).events(run_id, level=level)
        return [
            {
                "id": e.id,
                "ts": e.ts,
                "phase": e.phase,
                "level": e.level,
                "video_id": e.video_id,
                "message": e.message,
            }
            for e in evs
        ]


@runs_router.post("/trigger")
async def trigger_run(pipeline: Optional[str] = None) -> dict[str, Any]:
    """Kick a run NOW for one pipeline (default P4) or all if pipeline=ALL.

    Runs in the background; poll /api/runs for status.
    """
    import asyncio

    from interrogation_pipeline.scheduler.scheduler import trigger_now

    target: Optional[str]
    if pipeline is None or pipeline == "":
        target = "P4"
    elif pipeline.upper() == "ALL":
        target = None
    else:
        target = pipeline.upper()

    asyncio.create_task(trigger_now(pipeline=target))
    return {
        "status": "kicked_off",
        "pipeline": target or "ALL",
        "hint": "poll /api/runs for the new run",
    }


@runs_router.get("/current/stream")
async def current_run_stream():
    """Server-Sent Events stream for the live progress of the most recent run.

    Emits one event per phase change + per Run finalization. Reconnect-safe:
    if no run is active, the stream emits the latest run state once and closes.
    """
    import asyncio
    import json as _json

    from sse_starlette.sse import EventSourceResponse

    async def gen():
        last_seen: tuple[Optional[int], Optional[str], Optional[str]] = (None, None, None)
        idle_ticks = 0
        while True:
            async with session_scope() as session:
                r = await RunRepo(session).latest()
            if r is None:
                yield {"event": "idle", "data": "no runs yet"}
                await asyncio.sleep(2)
                idle_ticks += 1
                if idle_ticks > 30:
                    return
                continue
            sig = (r.id, r.status, r.phase)
            if sig != last_seen:
                payload = {
                    "run_id": r.id,
                    "status": r.status,
                    "phase": r.phase,
                    "started_at": r.started_at,
                    "completed_at": r.completed_at,
                    "counts": _json.loads(r.counts_json) if r.counts_json else {},
                    "error": r.error,
                }
                yield {"event": "phase", "data": _json.dumps(payload)}
                last_seen = sig
            if r.status in {"success", "partial", "failed"}:
                yield {"event": "done", "data": _json.dumps({"run_id": r.id, "status": r.status})}
                return
            await asyncio.sleep(1.5)

    return EventSourceResponse(gen())


@runs_router.get("/scheduler/info")
async def scheduler_info() -> dict[str, Any]:
    """Show whether the daily-run cron job is armed and when it fires next."""
    from interrogation_pipeline.scheduler import info as sched_info

    return sched_info()


class RescheduleBody(BaseModel):
    cron: str


@runs_router.post("/scheduler/reschedule")
async def scheduler_reschedule(body: RescheduleBody) -> dict[str, Any]:
    """Update the cron expression at runtime AND persist to config.

    Validates the cron string by attempting to parse it. Returns the new
    next-fire time so the caller can confirm the change took effect.
    """
    from interrogation_pipeline.scheduler import reschedule as sched_reschedule

    try:
        return await sched_reschedule(body.cron)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"reschedule failed: {e}") from e


# ──────────────────────────────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────────────────────────────
settings_router = APIRouter(tags=["settings"], prefix="/settings")


@settings_router.get("")
async def get_settings() -> dict[str, Any]:
    cfg = await runtime_cfg.load()
    return {k: getattr(cfg, k) for k in cfg.__slots__}


@settings_router.patch("")
async def patch_settings(body: dict[str, Any]) -> dict[str, Any]:
    cfg = await runtime_cfg.patch(body)
    return {k: getattr(cfg, k) for k in cfg.__slots__}


@settings_router.get("/api-keys/status")
async def api_keys_status() -> dict[str, str]:
    """Probe each external service. Never returns the actual key values."""
    return {
        "anthropic": "configured" if env_settings.anthropic_api_key else "missing",
        "tavily": "configured" if env_settings.tavily_api_key else "missing",
        "trello": "configured" if env_settings.trello_token else "missing",
        "webshare": "configured" if env_settings.webshare_username else "missing",
    }


@settings_router.get("/health")
async def system_health() -> dict[str, Any]:
    """Aggregated health used by the dashboard banner.

    `missing_required` are services the pipeline can't function without
    (Anthropic, Tavily, Trello). `missing_optional` are nice-to-have
    integrations (Webshare) — the dashboard shouldn't red-flag those.
    """
    REQUIRED = ("anthropic", "tavily", "trello")
    statuses = await api_keys_status()
    async with session_scope() as session:
        stale = await CookieHealthRepo(session).stale_files()
    return {
        "missing_required": [k for k in REQUIRED if statuses.get(k) == "missing"],
        "missing_optional": [
            k for k, v in statuses.items() if v == "missing" and k not in REQUIRED
        ],
        # Back-compat alias for older frontends still on this key
        "missing_keys": [k for k in REQUIRED if statuses.get(k) == "missing"],
        "stale_cookies": [s.cookies_path for s in stale],
    }


# ──────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────
stats_router = APIRouter(tags=["stats"], prefix="/stats")


@stats_router.get("/p4")
async def stats_p4() -> dict[str, int]:
    async with session_scope() as session:
        return await StatsRepo(session).p4_overview()


@stats_router.get("/channels")
async def stats_channels() -> list[dict[str, Any]]:
    async with session_scope() as session:
        chans = await ChannelRepo(session).list_active(pipeline="P4")
        return [
            {
                "channel_id": c.id,
                "display_name": c.display_name,
                "youtube_total": c.youtube_total_count or 0,
                "last_seen_iso": c.last_seen_iso,
            }
            for c in chans
        ]


# ──────────────────────────────────────────────────────────────────────
# Proxies
# ──────────────────────────────────────────────────────────────────────
proxies_router = APIRouter(tags=["proxies"], prefix="/proxies")


@proxies_router.get("")
async def list_proxies(
    enabled_only: bool = False, limit: int = 200, offset: int = 0
) -> dict[str, Any]:
    async with session_scope() as session:
        repo = ProxyPoolRepo(session)
        total = await repo.count()
        enabled = await repo.count(enabled_only=True)
        rows = await repo.list(enabled_only=enabled_only, limit=limit, offset=offset)
        items = [
            {
                "id": p.id,
                "host": p.host,
                "port": p.port,
                "username": p.username,
                # Never return password
                "label": p.label,
                "enabled": p.enabled,
                "consecutive_failures": p.consecutive_failures,
                "success_count": p.success_count,
                "failure_count": p.failure_count,
                "last_ok_iso": p.last_ok_iso,
                "last_failed_iso": p.last_failed_iso,
            }
            for p in rows
        ]
    return {"total": total, "enabled": enabled, "items": items}


class ProxyImportBody(BaseModel):
    text: str
    replace: bool = False  # if true, clear pool before importing


@proxies_router.post("/import")
async def import_proxies(body: ProxyImportBody) -> dict[str, Any]:
    from interrogation_pipeline.scrape.proxy_parser import parse_bulk, to_rows

    proxies, rejected = parse_bulk(body.text)
    if not proxies and not body.replace:
        return {"inserted": 0, "duplicates": 0, "rejected": rejected[:20]}

    async with session_scope() as session:
        repo = ProxyPoolRepo(session)
        if body.replace:
            cleared = await repo.clear_all()
        else:
            cleared = 0
        inserted, duplicates = await repo.bulk_upsert(to_rows(proxies))
    return {
        "inserted": inserted,
        "duplicates": duplicates,
        "rejected": rejected[:20],  # cap so the response stays small
        "rejected_total": len(rejected),
        "cleared": cleared,
    }


class ProxyPatch(BaseModel):
    enabled: Optional[bool] = None


@proxies_router.patch("/{proxy_id}")
async def patch_proxy(proxy_id: int, body: ProxyPatch) -> dict[str, str]:
    async with session_scope() as session:
        repo = ProxyPoolRepo(session)
        if body.enabled is not None:
            await repo.set_enabled(proxy_id, body.enabled)
    return {"ok": "true"}


@proxies_router.delete("/{proxy_id}")
async def delete_proxy(proxy_id: int) -> dict[str, str]:
    async with session_scope() as session:
        await ProxyPoolRepo(session).delete(proxy_id)
    return {"ok": "true"}


# ──────────────────────────────────────────────────────────────────────
# Cookies (per-pipeline file pool)
# ──────────────────────────────────────────────────────────────────────
cookies_router = APIRouter(tags=["cookies"], prefix="/cookies")


@cookies_router.get("")
async def list_cookies() -> list[dict[str, Any]]:
    """List all cookie files across all pipelines, with health."""
    from sqlalchemy import select

    from interrogation_pipeline.scrape.cookies import list_files
    from interrogation_pipeline.store.models import CookieHealth

    paths = list_files()
    if not paths:
        return []
    async with session_scope() as session:
        rows = (await session.execute(
            select(CookieHealth).where(CookieHealth.cookies_path.in_(str(p) for p in paths))
        )).scalars().all()
    health = {r.cookies_path: r for r in rows}

    out = []
    for p in paths:
        h = health.get(str(p))
        # Pipeline label inferred from path: data/cookies/<pipeline>/X.txt or
        # data/cookies/cookies_<pipeline>.txt
        parent_name = p.parent.name.upper()
        if parent_name == "COOKIES":
            stem = p.stem.replace("cookies_", "")
            pipeline = stem.upper()
        else:
            pipeline = parent_name
        out.append({
            "path": str(p),
            "name": p.name,
            "pipeline": pipeline,
            "size_bytes": p.stat().st_size if p.exists() else 0,
            "stale": bool(h and h.stale),
            "consecutive_auth_failures": (h.consecutive_auth_failures if h else 0),
            "last_ok_at": h.last_ok_at if h else None,
            "last_failure_at": h.last_failure_at if h else None,
        })
    return out


# ──────────────────────────────────────────────────────────────────────
@stats_router.get("/cost")
async def stats_cost() -> dict[str, Any]:
    """Anthropic spend rolled up over today/week/month. Cheap aggregation
    over scan_results.cost_usd; verify costs are extra (~equal magnitude per
    accepted case, see handoff §11)."""
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import func, select

    from interrogation_pipeline.store.models import ScanResult

    now = datetime.now(UTC)
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).isoformat(timespec="seconds")
    month_ago = (now - timedelta(days=30)).isoformat(timespec="seconds")

    async with session_scope() as session:
        # Per scan_results.cost_usd
        today_q = select(func.coalesce(func.sum(ScanResult.cost_usd), 0.0)).where(
            ScanResult.scanned_at.like(f"{today}%")
        )
        week_q = select(func.coalesce(func.sum(ScanResult.cost_usd), 0.0)).where(
            ScanResult.scanned_at >= week_ago
        )
        month_q = select(func.coalesce(func.sum(ScanResult.cost_usd), 0.0)).where(
            ScanResult.scanned_at >= month_ago
        )
        all_q = select(
            func.count(ScanResult.id),
            func.coalesce(func.sum(ScanResult.cost_usd), 0.0),
            func.coalesce(func.sum(ScanResult.input_tokens), 0),
            func.coalesce(func.sum(ScanResult.output_tokens), 0),
        )

        today_total = (await session.execute(today_q)).scalar_one()
        week_total = (await session.execute(week_q)).scalar_one()
        month_total = (await session.execute(month_q)).scalar_one()
        n_scans, all_cost, in_tok, out_tok = (await session.execute(all_q)).one()

    return {
        "anthropic_today_usd": round(float(today_total), 4),
        "anthropic_week_usd": round(float(week_total), 4),
        "anthropic_month_usd": round(float(month_total), 4),
        "anthropic_lifetime_usd": round(float(all_cost), 4),
        "scans_total": int(n_scans),
        "input_tokens_total": int(in_tok),
        "output_tokens_total": int(out_tok),
    }
