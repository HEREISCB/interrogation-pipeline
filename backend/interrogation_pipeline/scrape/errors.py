"""Typed scrape errors + a yt-dlp stderr classifier.

The classifier maps the messy free-text stderr that yt-dlp emits onto a small
set of typed outcomes so the runner can decide retry/archive/fail without
parsing strings itself. Patterns drawn from handoff §12 plus what we've seen
in the wild.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ScrapeError(Exception):
    """Base for typed scrape errors. retryable controls the runner's loop."""

    retryable: bool = False
    archive_reason: str | None = None  # if set, video is moved to archived state


class RateLimited(ScrapeError):
    """YouTube returned 429 / 'Too Many Requests' or 'Sign in to confirm you're not a bot'."""
    retryable = True


class BotDetection(ScrapeError):
    """Generic bot-detection trip. Treated like rate-limit at the proxy layer."""
    retryable = True


class ScrapeTimeout(ScrapeError):
    """yt-dlp didn't finish within the per-video timeout."""
    retryable = True


class MembersOnly(ScrapeError):
    """'Join this channel to get access' — paywalled."""
    retryable = False
    archive_reason = "members_only"


class CaptionsMissing(ScrapeError):
    """No English auto-captions available."""
    retryable = False
    archive_reason = "no_captions"


class DRMProtected(ScrapeError):
    """Captions DRM-locked (e.g. @LawAndCrimeInvestigates)."""
    retryable = False
    archive_reason = "drm_protected"


class AgeRestricted(ScrapeError):
    """'Sign in to confirm your age' — needs an age-verified Google account."""
    retryable = False
    archive_reason = "age_restricted"


class PrivateOrDeleted(ScrapeError):
    """Video is private, deleted, or the channel is terminated."""
    retryable = False
    archive_reason = "private_or_deleted"


class CookieAuthFailure(ScrapeError):
    """Indicates the cookies file may be expired/invalid (HTTP 403, consent prompts).

    Distinct from BotDetection because it implies user action (re-export
    cookies) rather than rotating proxies.
    """
    retryable = True


class Classification(str, Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    BOT_DETECTION = "bot_detection"
    COOKIE_AUTH = "cookie_auth"
    MEMBERS_ONLY = "members_only"
    NO_CAPTIONS = "no_captions"
    DRM = "drm"
    AGE_RESTRICTED = "age_restricted"
    PRIVATE_OR_DELETED = "private_or_deleted"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class ScrapeOutcome:
    classification: Classification
    raw_stderr: str = ""

    def to_error(self) -> ScrapeError | None:
        return _CLASS_TO_ERROR.get(self.classification, lambda s: ScrapeError(s))(
            self.raw_stderr
        )


# Order matters: more-specific patterns first.
_PATTERNS: tuple[tuple[Classification, re.Pattern[str]], ...] = (
    (Classification.MEMBERS_ONLY, re.compile(r"join this channel to get access", re.I)),
    (Classification.MEMBERS_ONLY, re.compile(r"members[- ]only", re.I)),
    (Classification.DRM, re.compile(r"drm[- ]protected|drm protected", re.I)),
    (Classification.DRM, re.compile(r"requested format is not available", re.I)),
    (Classification.AGE_RESTRICTED, re.compile(r"sign in to confirm your age", re.I)),
    (Classification.AGE_RESTRICTED, re.compile(r"age[- ]restricted", re.I)),
    (Classification.PRIVATE_OR_DELETED, re.compile(r"video unavailable", re.I)),
    (Classification.PRIVATE_OR_DELETED, re.compile(r"this video is private", re.I)),
    (Classification.PRIVATE_OR_DELETED, re.compile(r"video has been removed", re.I)),
    (Classification.PRIVATE_OR_DELETED, re.compile(r"channel.*terminated", re.I)),
    (Classification.NO_CAPTIONS, re.compile(r"no.*subtitle.*available", re.I)),
    (Classification.NO_CAPTIONS, re.compile(r"no automatic captions", re.I)),
    (Classification.NO_CAPTIONS, re.compile(r"no English subtitles", re.I)),
    (Classification.RATE_LIMITED, re.compile(r"http error 429", re.I)),
    (Classification.RATE_LIMITED, re.compile(r"too many requests", re.I)),
    (Classification.RATE_LIMITED, re.compile(r"http error 499", re.I)),
    # Cookie-auth specifically (more specific than generic bot-detection).
    (Classification.COOKIE_AUTH, re.compile(r"http error 403", re.I)),
    (Classification.COOKIE_AUTH, re.compile(r"consent.*required", re.I)),
    (Classification.COOKIE_AUTH, re.compile(r"please sign in", re.I)),
    (Classification.BOT_DETECTION, re.compile(r"sign in to confirm.*not a bot", re.I)),
    (Classification.BOT_DETECTION, re.compile(r"unable to extract.*initial data", re.I)),
)


def classify_stderr(stderr: str) -> Classification:
    if not stderr:
        return Classification.OK
    for cls, pat in _PATTERNS:
        if pat.search(stderr):
            return cls
    # Heuristic fallback: any 4xx/5xx + retryable cause is bot-detection-ish.
    if re.search(r"http error 5\d\d", stderr, re.I):
        return Classification.RATE_LIMITED
    return Classification.UNKNOWN


_CLASS_TO_ERROR: dict[Classification, type] = {
    Classification.OK: lambda s: None,  # type: ignore[assignment]
    Classification.RATE_LIMITED: RateLimited,
    Classification.BOT_DETECTION: BotDetection,
    Classification.COOKIE_AUTH: CookieAuthFailure,
    Classification.MEMBERS_ONLY: MembersOnly,
    Classification.NO_CAPTIONS: CaptionsMissing,
    Classification.DRM: DRMProtected,
    Classification.AGE_RESTRICTED: AgeRestricted,
    Classification.PRIVATE_OR_DELETED: PrivateOrDeleted,
    Classification.TIMEOUT: ScrapeTimeout,
    Classification.UNKNOWN: ScrapeError,
}
