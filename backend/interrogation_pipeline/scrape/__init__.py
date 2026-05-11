"""yt-dlp + Webshare proxy + typed-error scrape layer."""

from interrogation_pipeline.scrape.errors import (
    AgeRestricted,
    BotDetection,
    CaptionsMissing,
    DRMProtected,
    MembersOnly,
    PrivateOrDeleted,
    RateLimited,
    ScrapeError,
    ScrapeOutcome,
    ScrapeTimeout,
    classify_stderr,
)

__all__ = [
    "AgeRestricted",
    "BotDetection",
    "CaptionsMissing",
    "DRMProtected",
    "MembersOnly",
    "PrivateOrDeleted",
    "RateLimited",
    "ScrapeError",
    "ScrapeOutcome",
    "ScrapeTimeout",
    "classify_stderr",
]
