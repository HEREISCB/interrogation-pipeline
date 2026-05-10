"""APScheduler thread that fires `run_daily` on the configured cron schedule.

We use AsyncIOScheduler because the rest of the app is async; APScheduler will
schedule the coroutine onto the FastAPI/uvicorn event loop.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from interrogation_pipeline.config import runtime as runtime_cfg
from interrogation_pipeline.scheduler.runner import run_daily

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


async def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    cfg = await runtime_cfg.load()
    _scheduler = AsyncIOScheduler()
    trigger = CronTrigger.from_crontab(cfg.schedule_cron)
    _scheduler.add_job(
        run_daily,
        trigger=trigger,
        id="run_daily",
        replace_existing=True,
        kwargs={"trigger": "scheduled", "pipeline": "P4"},
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    log.info("Scheduler started; cron=%s", cfg.schedule_cron)


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


async def trigger_now(*, pipeline: str | None = "P4") -> dict:
    """Kick a run immediately (out-of-band from the cron). Returns final result."""
    return await run_daily(trigger="manual", pipeline=pipeline)


def info() -> dict:
    """Snapshot of scheduler state for the dashboard / API."""
    if _scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    for j in _scheduler.get_jobs():
        nft = j.next_run_time
        jobs.append({
            "id": j.id,
            "next_fire": nft.isoformat() if nft else None,
            "trigger": str(j.trigger),
        })
    return {"running": _scheduler.running, "jobs": jobs}


async def reschedule(cron: str) -> dict:
    """Update the daily-run cron at runtime AND persist it to the config table.

    Used both by the Settings page (when the user edits schedule_cron) and by
    the test endpoint to fire the cron job soon for verification.
    """
    if _scheduler is None:
        raise RuntimeError("Scheduler is not running")
    trigger = CronTrigger.from_crontab(cron)
    _scheduler.reschedule_job("run_daily", trigger=trigger)
    await runtime_cfg.patch({"schedule_cron": cron})
    return info()


async def trigger_now_in_background() -> int:
    """Fire-and-forget variant returning a placeholder run_id ASAP for the API."""
    task = asyncio.create_task(run_daily(trigger="manual", pipeline="P4"))
    # Run starts inserting the Run row immediately, but we don't have its id
    # synchronously. Caller should poll /api/runs to find the latest.
    return 0  # sentinel: caller treats this as "kicked off"
