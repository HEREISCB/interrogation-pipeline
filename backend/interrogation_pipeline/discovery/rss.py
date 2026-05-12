"""Parse YouTube channel RSS feeds into VideoStub records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

import httpx
from lxml import etree

YT_RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YT_RSS_USER_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?user={user}"
YT_HANDLE_PAGE_TEMPLATE = "https://www.youtube.com/{handle}"

# Used to extract the canonical channel ID from a @handle page's HTML.
# Order matters: the first patterns are the most reliable (canonical/og:url
# always point at THE channel), the later ones can pick up the wrong UC ID
# from sidebar/featured-channel sections of the HTML.
_CHANNEL_ID_PATTERNS = (
    re.compile(rb'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{20,})">'),
    re.compile(rb'<meta property="og:url" content="https://www\.youtube\.com/channel/(UC[\w-]{20,})">'),
    re.compile(rb'"externalChannelId":"(UC[\w-]{20,})"'),
    re.compile(rb'"channelId":"(UC[\w-]{20,})"'),
)

# YT Atom XML namespaces
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mreq/rss/-/",
}


@dataclass(slots=True, frozen=True)
class VideoStub:
    video_id: str
    title: str
    published_iso: str           # UTC ISO-8601, second precision
    channel_id: str
    description: Optional[str] = None


def rss_url_for(channel: str) -> str:
    """Build the RSS URL.

    UC channel IDs use the modern endpoint. Legacy @handles use the deprecated
    `?user=` form here — but in practice we resolve handles to UC IDs first via
    `resolve_channel_id` and store the UC form in the DB. This helper remains as
    the single canonical builder so callers don't sprinkle string formatting.
    """
    if channel.startswith("UC"):
        return YT_RSS_TEMPLATE.format(channel_id=channel)
    return YT_RSS_USER_TEMPLATE.format(user=channel.lstrip("@"))


async def resolve_channel_id(
    handle_or_id: str, *, client: Optional[httpx.AsyncClient] = None
) -> Optional[str]:
    """Convert an @handle (or any youtube.com/<thing> URL) to a UC channel ID.

    Returns None if the page lookup fails or the ID can't be extracted.
    UC IDs are returned unchanged. Network call costs ~1 round-trip per handle;
    callers should cache the result on the Channel row.
    """
    if handle_or_id.startswith("UC") and len(handle_or_id) >= 24:
        return handle_or_id

    handle = handle_or_id if handle_or_id.startswith("@") else f"@{handle_or_id}"
    url = YT_HANDLE_PAGE_TEMPLATE.format(handle=handle)

    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    try:
        resp = await client.get(url, timeout=15.0, follow_redirects=True)
        if resp.status_code != 200:
            return None
        body = resp.content
        for pat in _CHANNEL_ID_PATTERNS:
            m = pat.search(body)
            if m:
                return m.group(1).decode("ascii")
        return None
    finally:
        if own_client:
            await client.aclose()


def parse_feed(xml_bytes: bytes) -> list[VideoStub]:
    """Parse RSS XML to a list of VideoStub. Raises ValueError on malformed input."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid RSS XML: {e}") from e

    channel_id_el = root.find("yt:channelId", NS)
    if channel_id_el is None or not channel_id_el.text:
        # Some legacy feeds expose <author><name>… instead. Fall back.
        author = root.find("atom:author/atom:name", NS)
        channel_id = author.text if author is not None and author.text else ""
    else:
        channel_id = channel_id_el.text

    out: list[VideoStub] = []
    for entry in root.findall("atom:entry", NS):
        vid_el = entry.find("yt:videoId", NS)
        title_el = entry.find("atom:title", NS)
        published_el = entry.find("atom:published", NS)
        media_desc_el = entry.find(
            "{http://search.yahoo.com/mrss/}group/{http://search.yahoo.com/mrss/}description"
        )

        if vid_el is None or not vid_el.text:
            continue
        if published_el is None or not published_el.text:
            continue

        try:
            published_iso = (
                datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))
                .astimezone(UTC)
                .isoformat(timespec="seconds")
            )
        except ValueError:
            continue

        out.append(
            VideoStub(
                video_id=vid_el.text,
                title=(title_el.text if title_el is not None else "") or "",
                published_iso=published_iso,
                channel_id=channel_id,
                description=(media_desc_el.text if media_desc_el is not None else None),
            )
        )

    return out


async def fetch_feed(client: httpx.AsyncClient, channel: str) -> bytes:
    """Fetch the raw RSS XML for a channel. Raises httpx.HTTPError on failure."""
    url = rss_url_for(channel)
    resp = await client.get(url, timeout=15.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


@dataclass(slots=True, frozen=True)
class DiscoveryResult:
    videos: list[VideoStub]
    rss_overflow: bool
    """True when RSS returned its 15-entry cap AND the oldest entry is still
    inside the lookback window. Signal to the runner that a channel may have
    uploaded more than 15 videos in the lookback period (e.g. Law & Crime
    pushes 30/day) and should be backfilled with yt-dlp --flat-playlist for
    that channel only."""


async def fetch_recent_videos(
    channel: str,
    *,
    since_iso: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> DiscoveryResult:
    """Fetch + parse + filter to entries published strictly after `since_iso`.

    Resolves @handles to UC channel IDs on demand (one extra HTTP call). Caller
    can pass a UC ID directly to skip the resolution.

    `since_iso` is the cutoff already adjusted by the caller's lookback window.
    Returned `videos` list is sorted oldest → newest so callers can advance
    `last_seen_iso` with the final element.
    """
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    try:
        target = channel
        if not channel.startswith("UC"):
            resolved = await resolve_channel_id(channel, client=client)
            if resolved:
                target = resolved
        xml = await fetch_feed(client, target)
        all_stubs = parse_feed(xml)

        # Overflow detection: YouTube RSS caps at 15 entries. If we received
        # exactly 15 AND the oldest one is still within the user's lookback
        # window, there are likely more we can't see via RSS.
        rss_overflow = False
        if len(all_stubs) >= 15 and since_iso:
            oldest_published = min(s.published_iso for s in all_stubs)
            if oldest_published > since_iso:
                rss_overflow = True

        stubs = all_stubs
        if since_iso:
            stubs = [s for s in stubs if s.published_iso > since_iso]
        stubs.sort(key=lambda s: s.published_iso)
        return DiscoveryResult(videos=stubs, rss_overflow=rss_overflow)
    finally:
        if own_client:
            await client.aclose()
