"""Tavily search → Haiku name corrector. Returns a typed VerificationResult."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.verify.tavily import search

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "verify.txt"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class VerificationResult(BaseModel):
    match_confidence: str = "no_match"           # high|medium|low|no_match
    match_reasoning: str = ""
    corrected_defendant: Optional[str] = None
    corrected_victim: Optional[str] = None
    additional_charges: Optional[str] = None
    verdict_update: Optional[str] = None
    best_article_urls: list[str] = Field(default_factory=list)
    articles: list[dict[str, Any]] = Field(default_factory=list)


def _format_articles(articles: list[dict[str, Any]]) -> str:
    if not articles:
        return "(no articles found)"
    out = []
    for i, a in enumerate(articles, 1):
        out.append(f"{i}. {a.get('title') or a.get('url')}\n   {a.get('snippet') or ''}")
    return "\n\n".join(out)


def _parse_json(body: str) -> dict[str, Any]:
    body = body.strip()
    if body.startswith("```"):
        body = body.strip("`")
        if body.lower().startswith("json"):
            body = body[4:].strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        s, e = body.find("{"), body.rfind("}")
        if s >= 0 and e > s:
            return json.loads(body[s : e + 1])
        raise


async def verify_case(
    defendant: str,
    victim: str | None,
    *,
    date: str | None = None,
    location: str | None = None,
    charges: str | None = None,
    year: int | None = None,
    client: AsyncAnthropic | None = None,
    model: str = DEFAULT_MODEL,
) -> VerificationResult:
    """Search Tavily, send articles + extraction to Haiku, return corrections."""
    articles = await search(defendant, victim, year)
    if not articles:
        return VerificationResult(
            match_confidence="no_match",
            match_reasoning="No articles found by Tavily",
            articles=[],
        )

    own_client = client is None
    if client is None:
        client = AsyncAnthropic(api_key=env_settings.anthropic_api_key)

    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        defendant=defendant or "unknown",
        victim=victim or "unknown",
        date=date or "unknown",
        location=location or "unknown",
        charges=charges or "unknown",
        articles_block=_format_articles(articles),
    )

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        body = "".join(
            getattr(b, "text", "") for b in (resp.content or []) if getattr(b, "type", "") == "text"
        )
        try:
            data = _parse_json(body)
        except (json.JSONDecodeError, ValueError):
            log.warning("Tavily verifier got unparseable Haiku response")
            return VerificationResult(
                match_confidence="no_match",
                match_reasoning="JSON parse failure",
                articles=articles,
            )

        return VerificationResult(
            match_confidence=str(data.get("match_confidence") or "no_match"),
            match_reasoning=str(data.get("match_reasoning") or ""),
            corrected_defendant=data.get("corrected_defendant"),
            corrected_victim=data.get("corrected_victim"),
            additional_charges=data.get("additional_charges"),
            verdict_update=data.get("verdict_update"),
            best_article_urls=data.get("best_article_urls") or [],
            articles=articles,
        )
    finally:
        if own_client:
            await client.close()
