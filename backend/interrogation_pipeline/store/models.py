"""SQLAlchemy ORM models — one source of truth for the schema.

Mirrors Section 4 of the design spec. All datetimes are stored as ISO-8601 UTC
strings (TEXT) for round-trip clarity and simple cross-platform behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────────────
# channels
# ──────────────────────────────────────────────────────────────────────
class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # UC… or @handle
    display_name: Mapped[Optional[str]] = mapped_column(String)
    pipeline: Mapped[str] = mapped_column(String, nullable=False)        # 'P4' for v1
    rss_url: Mapped[str] = mapped_column(String, nullable=False)
    since_iso: Mapped[Optional[str]] = mapped_column(String)
    last_seen_iso: Mapped[Optional[str]] = mapped_column(String)
    last_seen_video_id: Mapped[Optional[str]] = mapped_column(String)
    cookies_path: Mapped[str] = mapped_column(String, nullable=False)
    youtube_total_count: Mapped[Optional[int]] = mapped_column(Integer)
    youtube_total_synced_at: Mapped[Optional[str]] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # If RSS returned 15 entries AND the oldest is still within the lookback
    # window, we suspect we missed older uploads. Flag the channel so the next
    # run uses yt-dlp --flat-playlist as a backfill for THAT channel only.
    rss_overflow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)

    videos: Mapped[list["Video"]] = relationship(back_populates="channel")


# ──────────────────────────────────────────────────────────────────────
# videos
# ──────────────────────────────────────────────────────────────────────
class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # YouTube video ID
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String)
    published_iso: Mapped[str] = mapped_column(String, nullable=False)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)

    # status: 'pending' | 'captioned' | 'scanned' | 'archived' | 'failed'
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    archive_reason: Mapped[Optional[str]] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_attempt_iso: Mapped[Optional[str]] = mapped_column(String)
    vtt_path: Mapped[Optional[str]] = mapped_column(String)
    discovered_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)

    channel: Mapped[Channel] = relationship(back_populates="videos")
    scan_result: Mapped[Optional["ScanResult"]] = relationship(
        back_populates="video", uselist=False
    )

    __table_args__ = (
        Index("ix_videos_status_attempts", "status", "attempts"),
        Index("ix_videos_channel_published", "channel_id", "published_iso"),
    )


# ──────────────────────────────────────────────────────────────────────
# scan_results
# ──────────────────────────────────────────────────────────────────────
class ScanResult(Base):
    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"), nullable=False, unique=True)
    has_homicide: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    category: Mapped[Optional[str]] = mapped_column(String)
    drama_rating: Mapped[Optional[int]] = mapped_column(Integer)
    drama_breakdown_json: Mapped[Optional[str]] = mapped_column(Text)
    drama_summary: Mapped[Optional[str]] = mapped_column(Text)

    defendant_name: Mapped[Optional[str]] = mapped_column(String)
    victim_name: Mapped[Optional[str]] = mapped_column(String)
    charges: Mapped[Optional[str]] = mapped_column(Text)
    date_of_incident: Mapped[Optional[str]] = mapped_column(String)
    location: Mapped[Optional[str]] = mapped_column(String)
    arresting_agency: Mapped[Optional[str]] = mapped_column(String)
    verdict: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    footage_types_json: Mapped[Optional[str]] = mapped_column(Text)

    raw_response_json: Mapped[Optional[str]] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    scanned_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[float]] = mapped_column()

    video: Mapped[Video] = relationship(back_populates="scan_result")

    __table_args__ = (
        Index("ix_scan_homicide_scannedat", "has_homicide", "scanned_at"),
    )


# ──────────────────────────────────────────────────────────────────────
# cases (the dedup unit; one row per UNIQUE case after merge)
# ──────────────────────────────────────────────────────────────────────
class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    primary_scan_id: Mapped[int] = mapped_column(ForeignKey("scan_results.id"), nullable=False)

    defendant_name: Mapped[str] = mapped_column(String, nullable=False)
    defendant_original: Mapped[Optional[str]] = mapped_column(String)
    victim_name: Mapped[Optional[str]] = mapped_column(String)
    victim_original: Mapped[Optional[str]] = mapped_column(String)
    charges: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    verdict: Mapped[Optional[str]] = mapped_column(Text)

    # status: 'unverified' | 'verified' | 'merged_into' | 'pending_review'
    #       | 'pushed_to_trello' | 'skipped' | 'reviewed' | 'stuck'
    status: Mapped[str] = mapped_column(String, nullable=False, default="unverified")

    verification_status: Mapped[Optional[str]] = mapped_column(String)
    verification_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    articles_json: Mapped[Optional[str]] = mapped_column(Text)

    # dedup_status: 'unique' | 'exists_old' | 'exists_new'
    dedup_status: Mapped[Optional[str]] = mapped_column(String)
    matched_trello_card_id: Mapped[Optional[str]] = mapped_column(String)
    trello_card_id: Mapped[Optional[str]] = mapped_column(String)

    # Highlights (do not affect filtering — purely UI tags so user can quick-skip)
    banned_state: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    banned_agency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    merged_into_case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"))
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)

    primary_scan: Mapped[ScanResult] = relationship(foreign_keys=[primary_scan_id])
    videos: Mapped[list["CaseVideo"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cases_status_run", "status", "run_id"),
        Index("ix_cases_defendant", "defendant_name"),
        Index("ix_cases_run_dedup", "run_id", "dedup_status"),
    )


# ──────────────────────────────────────────────────────────────────────
# case_videos (many cases ↔ many videos after dedup)
# ──────────────────────────────────────────────────────────────────────
class CaseVideo(Base):
    __tablename__ = "case_videos"

    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True
    )
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"), primary_key=True)

    case: Mapped[Case] = relationship(back_populates="videos")


# ──────────────────────────────────────────────────────────────────────
# runs
# ──────────────────────────────────────────────────────────────────────
class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trigger: Mapped[str] = mapped_column(String, nullable=False)         # 'scheduled' | 'manual'
    started_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)
    completed_at: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)          # running|success|partial|failed
    phase: Mapped[Optional[str]] = mapped_column(String)
    counts_json: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)

    events: Mapped[list["RunEvent"]] = relationship(back_populates="run")

    __table_args__ = (
        Index("ix_runs_started", "started_at"),
    )


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    ts: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False)           # info|warn|error
    video_id: Mapped[Optional[str]] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[Run] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_run_events_runid_ts", "run_id", "ts"),
    )


# ──────────────────────────────────────────────────────────────────────
# trello tracking
# ──────────────────────────────────────────────────────────────────────
class TrelloPushLog(Base):
    __tablename__ = "trello_push_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    board_id: Mapped[str] = mapped_column(String, nullable=False)
    list_id: Mapped[str] = mapped_column(String, nullable=False)
    trello_card_id: Mapped[str] = mapped_column(String, nullable=False)
    pushed_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)
    pushed_by: Mapped[Optional[str]] = mapped_column(String)


class TrelloCardCache(Base):
    __tablename__ = "trello_card_cache"

    trello_card_id: Mapped[str] = mapped_column(String, primary_key=True)
    board_id: Mapped[str] = mapped_column(String, nullable=False)
    list_id: Mapped[Optional[str]] = mapped_column(String)
    list_name: Mapped[Optional[str]] = mapped_column(String)
    title: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    parsed_defendant: Mapped[Optional[str]] = mapped_column(String)
    parsed_victim: Mapped[Optional[str]] = mapped_column(String)
    parsed_state: Mapped[Optional[str]] = mapped_column(String)
    parsed_year: Mapped[Optional[int]] = mapped_column(Integer)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_synced_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)

    __table_args__ = (
        Index("ix_trello_cache_defendant", "parsed_defendant"),
    )


# ──────────────────────────────────────────────────────────────────────
# infrastructure tables
# ──────────────────────────────────────────────────────────────────────
class ProxyBlacklist(Base):
    __tablename__ = "proxy_blacklist"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    blacklisted_until: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String)


class TavilyCache(Base):
    __tablename__ = "tavily_cache"

    query_hash: Mapped[str] = mapped_column(String, primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    articles_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)


class ConfigEntry(Base):
    """Key-value table for runtime-tunable behavior settings.

    Values are JSON-encoded so we can store strings/ints/lists/dicts uniformly.
    See config.runtime for typed accessors.
    """

    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_iso)


class CookieHealth(Base):
    """Per-cookie-file health: drives the 'cookies stale' dashboard banner.

    A scrape attempt records ok/auth_failed; we tally consecutive auth_failed
    per cookies_path. ≥5 in a row → mark stale; banner appears until user
    re-exports cookies and the next attempt comes back ok.
    """

    __tablename__ = "cookie_health"

    cookies_path: Mapped[str] = mapped_column(String, primary_key=True)
    consecutive_auth_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_ok_at: Mapped[Optional[str]] = mapped_column(String)
    last_failure_at: Mapped[Optional[str]] = mapped_column(String)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ChannelDailyCount(Base):
    """Per-channel, per-day count of videos discovered. Powers the calendar grid."""

    __tablename__ = "channel_daily_counts"
    __table_args__ = (UniqueConstraint("channel_id", "date_iso", name="uq_channel_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), nullable=False)
    date_iso: Mapped[str] = mapped_column(String, nullable=False)        # 'YYYY-MM-DD' UTC
    discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pushed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
