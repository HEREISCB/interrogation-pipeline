"""YouTube RSS-based new-video discovery.

Each YouTube channel exposes:
  https://www.youtube.com/feeds/videos.xml?channel_id=UC...

Returns the latest 15 uploads with publish timestamps. Unauthenticated, not
rate-limited, no proxy needed. Section 14.3 of the handoff explicitly calls
this out as the right approach for the daily snipe job.
"""

from interrogation_pipeline.discovery.rss import (
    DiscoveryResult,
    VideoStub,
    fetch_recent_videos,
)

__all__ = ["DiscoveryResult", "VideoStub", "fetch_recent_videos"]
