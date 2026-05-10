"""Trello card description builder.

Mirrors handoff §8.3 — same field layout your VAs are already used to
parsing, plus a footer auto-tag so a human can spot pipeline-added cards.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _line(label: str, value: Any) -> str:
    if value in (None, "", [], {}):
        value = "—"
    return f"**{label}**: {value}"


def build_card_description(
    *,
    defendant: str,
    victim: str | None,
    charges: str | None,
    date_of_incident: str | None,
    location: str | None,
    arresting_agency: str | None,
    verdict: str | None,
    video_url: str,
    drama_rating: int | None,
    category: str | None,
    channel: str | None,
    pipeline: str,
    summary: str | None,
    article_urls: list[str] | None = None,
    verification_status: str | None = None,
    banned_state: bool = False,
    banned_agency: bool = False,
) -> str:
    lines = [
        _line("Defendant Name", defendant),
        _line("Victim Name", victim),
        _line("Type of Offense", charges),
        _line("Date of Incident", date_of_incident),
        _line("Location of Incident", location),
        _line("Arresting Agency", arresting_agency),
        _line("Verdict", verdict),
        "",
        "**Links:**",
        video_url,
    ]
    if article_urls:
        for u in article_urls:
            if u:
                lines.append(u)
    lines.extend(
        [
            "",
            _line("Drama Rating", f"{drama_rating}/10" if drama_rating else "—"),
            _line("Category", category),
            _line("Channel", channel),
            _line("Pipeline", pipeline),
        ]
    )
    if banned_state or banned_agency:
        flags = []
        if banned_state:
            flags.append("banned state")
        if banned_agency:
            flags.append("banned agency")
        lines.append(_line("⚠ FOIA flag", ", ".join(flags)))
    if summary:
        lines.extend(["", "**Summary:**", summary])

    footer = (
        f"\n\n---\n*Auto-added by interrogation-pipeline on "
        f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    if verification_status:
        footer += f" | Tavily status: {verification_status}"
    footer += "*"
    lines.append(footer)

    return "\n".join(lines)
