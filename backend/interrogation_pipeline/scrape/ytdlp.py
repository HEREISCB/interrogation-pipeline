"""yt-dlp subprocess wrapper.

Two responsibilities:
  - download_captions(video_id, …)  → .vtt file or typed ScrapeError
  - list_recent_uploads(channel_id, …)  → list[str]  (used as RSS overflow fallback)

Uses the proven flag set from handoff §5.2:
  --extractor-args 'youtube:player_client=tv'    bypass bot detection
  --no-check-certificates                         Webshare uses self-signed cert
  --cookies <file>                                throwaway YT account
  --write-auto-sub --sub-lang en --skip-download  English auto-captions only
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from interrogation_pipeline.scrape.errors import (
    Classification,
    ScrapeError,
    classify_stderr,
)
from interrogation_pipeline.scrape.proxies import ProxySession, WebshareSessionPool

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # seconds; matches handoff §5.2

YT_DLP_BIN = shutil.which("yt-dlp") or "yt-dlp"


@dataclass(slots=True)
class CaptionDownload:
    video_id: str
    vtt_path: Path
    proxy_session_id: str


async def _run(
    cmd: list[str], *, timeout: int
) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr) — all as text."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "TIMEOUT"
    return (
        proc.returncode or 0,
        stdout_b.decode("utf-8", errors="replace"),
        stderr_b.decode("utf-8", errors="replace"),
    )


async def download_captions(
    video_id: str,
    *,
    cookies_path: Path,
    proxy: ProxySession,
    out_dir: Path,
    timeout: int = DEFAULT_TIMEOUT,
) -> CaptionDownload:
    """Download English auto-captions for one video.

    Raises a typed ScrapeError on failure. On success returns the .vtt path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "%(id)s.%(ext)s")
    url = f"https://www.youtube.com/watch?v={video_id}"

    cmd = [
        YT_DLP_BIN,
        url,
        "--write-auto-sub",
        "--sub-lang", "en",
        "--skip-download",
        "--no-check-certificates",
        "--extractor-args", "youtube:player_client=tv",
        # YouTube's SABR experiment + n-challenge requires a JS runtime to
        # decrypt URLs. yt-dlp ≥ 2026.5 only enables Deno by default; we ship
        # with `yt-dlp-ejs` and tell it to use Node, which is widely available.
        "--js-runtimes", "node",
        # Allow yt-dlp to fetch the EJS solver script from npm if not bundled.
        # Required as of yt-dlp 2026.5 for SABR / n-challenge handling.
        "--remote-components", "ejs:github",
        "--cookies", str(cookies_path),
        "--output", output_template,
        "--no-progress",
        "--quiet",
    ]
    # Webshare proxy is optional in dev — if no password is configured, the
    # pool produces a sentinel session with proxy_url="" and we skip --proxy.
    # Production should always set WEBSHARE_PASSWORD or YouTube will rate-limit
    # the unproxied IP fast.
    if proxy.proxy_url:
        cmd.extend(["--proxy", proxy.proxy_url])

    rc, stdout, stderr = await _run(cmd, timeout=timeout)

    if stderr == "TIMEOUT":
        from interrogation_pipeline.scrape.errors import ScrapeTimeout
        raise ScrapeTimeout(f"yt-dlp timeout >{timeout}s for {video_id}")

    if rc != 0 or "ERROR" in stderr:
        cls = classify_stderr(stderr)
        if cls == Classification.OK:
            cls = Classification.UNKNOWN
        err_cls = _outcome_error_class(cls)
        raise err_cls(stderr.strip()[:1500] or f"yt-dlp rc={rc}")

    # yt-dlp writes <id>.en.vtt by default. Fall back to any .vtt produced.
    en_vtt = out_dir / f"{video_id}.en.vtt"
    if en_vtt.exists():
        vtt = en_vtt
    else:
        candidates = list(out_dir.glob(f"{video_id}*.vtt"))
        if not candidates:
            from interrogation_pipeline.scrape.errors import CaptionsMissing
            raise CaptionsMissing(f"yt-dlp succeeded but no .vtt for {video_id}")
        vtt = candidates[0]

    return CaptionDownload(
        video_id=video_id, vtt_path=vtt, proxy_session_id=proxy.session_id
    )


async def count_uploads(
    channel_id: str,
    *,
    cookies_path: Path,
    proxy: ProxySession,
    timeout: int = 90,
) -> int:
    """Return the channel's lifetime upload count (cheap — single playlist call).

    Uses `--print '%(playlist_count)s'` with `-O playlist` to get the count
    once per playlist (not per video). Falls back to None on parse failure.
    """
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    cmd = [
        YT_DLP_BIN,
        url,
        "--flat-playlist",
        "--simulate",
        "--no-warnings",
        "--no-check-certificates",
        "--extractor-args", "youtube:player_client=tv",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies", str(cookies_path),
        "--print", "playlist:%(playlist_count)s",
        "--quiet",
    ]
    if proxy.proxy_url:
        cmd.extend(["--proxy", proxy.proxy_url])
    rc, stdout, stderr = await _run(cmd, timeout=timeout)
    if rc != 0:
        cls = classify_stderr(stderr)
        err_cls = _outcome_error_class(cls)
        raise err_cls(stderr.strip()[:1500] or f"yt-dlp rc={rc}")
    for line in stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return 0


async def list_recent_uploads(
    channel_id: str,
    *,
    cookies_path: Path,
    proxy: ProxySession,
    limit: int = 50,
    timeout: int = 60,
) -> list[str]:
    """Enumerate the N most recent video IDs. Convenience wrapper that drops
    everything except the IDs — for callers that don't need dates/titles."""
    records = await enumerate_uploads(
        channel_id,
        cookies_path=cookies_path,
        proxy=proxy,
        limit=limit,
        timeout=timeout,
    )
    return [r["id"] for r in records if r.get("id")]


async def enumerate_uploads(
    channel_id: str,
    *,
    cookies_path: Path,
    proxy: ProxySession,
    limit: int = 50,
    hours_back: int | None = None,
    timeout: int = 120,
) -> list[dict[str, str]]:
    """List the N most recent uploads with id + title + upload_date.

    Returns a list of dicts shaped like:
        {"id": "abc123", "title": "Cop interrogates suspect…",
         "upload_date": "20260510", "upload_date_iso": "2026-05-10T00:00:00+00:00"}

    When `hours_back` is set, asks yt-dlp to extract full per-video metadata
    (drops --flat-playlist so upload_date populates) and use
    --break-match-filters to STOP walking the channel as soon as it hits a
    video older than the cutoff. Per-video extraction is slower (~1-2s each
    instead of ~50ms with flat-playlist) but lets us honour the client's
    "scrape past 24h only" expectation. The break-on-reject relies on
    YouTube's /videos tab being newest-first, which holds for every channel
    we've tested. Lazy mode keeps the playlist iterator from prefetching.

    When `hours_back` is None, falls back to --flat-playlist (cheap, no
    dates) for callers that don't need date filtering (e.g. count_uploads
    or one-off bulk listings).

    Used as the primary discovery method (RSS feeds are blocked by YouTube
    on many residential/datacenter IPs).
    """
    import json as _json
    from datetime import UTC, datetime, timedelta

    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    cmd = [
        YT_DLP_BIN,
        url,
        "--simulate",
        "--no-warnings",
        "--no-check-certificates",
        "--extractor-args", "youtube:player_client=tv",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies", str(cookies_path),
        "--playlist-end", str(limit),
        "--print", "%(.{id,title,upload_date,timestamp})j",
        "--quiet",
    ]
    if hours_back is not None:
        # yt-dlp's --match-filters compares fields with simple operators.
        # YYYYMMDD granularity (day, not second) is intentionally loose —
        # better to over-capture by a few hours than miss a midnight upload.
        # The runner does a precise post-hoc ISO comparison anyway.
        cutoff_date = (
            datetime.now(UTC) - timedelta(hours=hours_back)
        ).strftime("%Y%m%d")
        cmd.extend([
            "--lazy-playlist",
            "--break-match-filters", f"upload_date >= {cutoff_date}",
        ])
    else:
        cmd.append("--flat-playlist")
    if proxy.proxy_url:
        cmd.extend(["--proxy", proxy.proxy_url])
    rc, stdout, stderr = await _run(cmd, timeout=timeout)
    if rc != 0:
        cls = classify_stderr(stderr)
        err_cls = _outcome_error_class(cls)
        raise err_cls(stderr.strip()[:1500] or f"yt-dlp rc={rc}")

    out: list[dict[str, str]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        if not rec.get("id"):
            continue
        # Normalize upload_date (YYYYMMDD from yt-dlp) into an ISO timestamp.
        # Prefer timestamp (epoch seconds) when present — that's authoritative.
        from datetime import UTC, datetime

        iso = ""
        ts = rec.get("timestamp")
        if isinstance(ts, (int, float)):
            iso = datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")
        else:
            ud = rec.get("upload_date") or ""
            if len(ud) == 8 and ud.isdigit():
                try:
                    iso = datetime(int(ud[0:4]), int(ud[4:6]), int(ud[6:8]), tzinfo=UTC).isoformat(timespec="seconds")
                except ValueError:
                    iso = ""
        rec["upload_date_iso"] = iso
        out.append(rec)
    return out


def _outcome_error_class(cls: Classification) -> type[ScrapeError]:
    from interrogation_pipeline.scrape.errors import (
        AgeRestricted,
        BotDetection,
        CaptionsMissing,
        CookieAuthFailure,
        DRMProtected,
        MembersOnly,
        PrivateOrDeleted,
        RateLimited,
        ScrapeTimeout,
    )

    return {
        Classification.RATE_LIMITED: RateLimited,
        Classification.BOT_DETECTION: BotDetection,
        Classification.COOKIE_AUTH: CookieAuthFailure,
        Classification.MEMBERS_ONLY: MembersOnly,
        Classification.NO_CAPTIONS: CaptionsMissing,
        Classification.DRM: DRMProtected,
        Classification.AGE_RESTRICTED: AgeRestricted,
        Classification.PRIVATE_OR_DELETED: PrivateOrDeleted,
        Classification.TIMEOUT: ScrapeTimeout,
    }.get(cls, ScrapeError)


# Convenience: a single high-level call that uses the ProxyPool +
# blacklists on rate-limit. Not auto-retrying — that's the runner's job so we
# can update DB state per attempt.
async def fetch_one(
    video_id: str,
    *,
    cookies_path: Path,
    out_dir: Path,
    pool: WebshareSessionPool,
    timeout: int = DEFAULT_TIMEOUT,
) -> CaptionDownload:
    proxy = await pool.acquire()
    try:
        result = await download_captions(
            video_id,
            cookies_path=cookies_path,
            proxy=proxy,
            out_dir=out_dir,
            timeout=timeout,
        )
        # success → tell the pool so adaptive mode + per-proxy stats update
        await pool.report_success(proxy)
        return result
    except ScrapeError as e:
        from interrogation_pipeline.scrape.errors import BotDetection, RateLimited
        await pool.report_failure(proxy, reason=str(e)[:200])
        # Short-term blacklist on rate-limit / bot-detection.
        if isinstance(e, (RateLimited, BotDetection)):
            await pool.blacklist(proxy, str(e)[:200])
        raise
