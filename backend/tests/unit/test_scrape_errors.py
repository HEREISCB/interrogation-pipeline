"""Classify real-shape yt-dlp stderr samples drawn from the handoff doc + wild."""

import pytest

from interrogation_pipeline.scrape.errors import Classification, classify_stderr


@pytest.mark.parametrize(
    "stderr,expected",
    [
        ("ERROR: [youtube] xyz: Sign in to confirm you're not a bot",
         Classification.BOT_DETECTION),
        ("ERROR: [youtube] xyz: HTTP Error 429: Too Many Requests",
         Classification.RATE_LIMITED),
        ("ERROR: [youtube] xyz: HTTP Error 499: Antivirus Blocked",
         Classification.RATE_LIMITED),
        ("ERROR: [youtube] xyz: This video is private",
         Classification.PRIVATE_OR_DELETED),
        ("ERROR: [youtube] xyz: Video unavailable",
         Classification.PRIVATE_OR_DELETED),
        ("ERROR: [youtube] xyz: Join this channel to get access to members-only content.",
         Classification.MEMBERS_ONLY),
        ("ERROR: [youtube] xyz: This video is drm protected and only images are available",
         Classification.DRM),
        ("ERROR: [youtube] xyz: Requested format is not available",
         Classification.DRM),
        ("ERROR: [youtube] xyz: Sign in to confirm your age. This video may be inappropriate.",
         Classification.AGE_RESTRICTED),
        ("ERROR: [youtube] xyz: HTTP Error 403: Forbidden",
         Classification.COOKIE_AUTH),
        ("WARNING: [youtube] xyz: There are no subtitles available for this video",
         Classification.NO_CAPTIONS),
        ("",
         Classification.OK),
        ("Some message we've never seen",
         Classification.UNKNOWN),
    ],
)
def test_classify(stderr, expected):
    assert classify_stderr(stderr) == expected
