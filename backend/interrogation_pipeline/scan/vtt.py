"""WebVTT → clean text.

YouTube auto-captions are noisy: stacked redundant lines, position attributes,
karaoke-style timing tags. We strip everything but the spoken content while
preserving rough order. Output is the body Haiku scans.
"""

from __future__ import annotations

import re
from pathlib import Path

# Strips inline timing tags like "<00:00:01.000>" and karaoke spans.
_INLINE_TAG = re.compile(r"<[^>]+>")
# WebVTT position/setting attributes appended to timestamp lines.
_TIME_LINE = re.compile(
    r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}.*$"
)


def clean_vtt(text: str) -> str:
    out: list[str] = []
    last_added: str = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "WEBVTT":
            continue
        if line.startswith(("Kind:", "Language:", "STYLE")):
            continue
        if _TIME_LINE.match(line):
            continue
        # Cue identifier numbers.
        if line.isdigit():
            continue
        cleaned = _INLINE_TAG.sub("", line).strip()
        if not cleaned:
            continue
        if cleaned == last_added:
            continue
        out.append(cleaned)
        last_added = cleaned
    return " ".join(out)


def clean_vtt_file(path: Path) -> str:
    return clean_vtt(path.read_text(encoding="utf-8", errors="replace"))
