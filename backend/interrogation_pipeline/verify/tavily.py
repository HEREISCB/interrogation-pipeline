"""Tavily web search wrapper, with DB-backed cache.

Repeats are FREE — `tavily_cache` keys queries by sha1(defendant|victim|year),
so re-runs after the runner crashes don't re-pay for searches we already did.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import httpx

from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.store.db import session_scope
from interrogation_pipeline.store.repos import TavilyRepo

log = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


def cache_key(defendant: str, victim: str | None, year: int | None) -> str:
    raw = f"{defendant.strip().lower()}|{(victim or '').strip().lower()}|{year or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_query(defendant: str, victim: str | None, year: int | None) -> str:
    parts = [defendant, "murder"]
    if victim:
        parts.append(victim)
    if year:
        parts.append(str(year))
    return " ".join(parts)


async def search(
    defendant: str,
    victim: str | None,
    year: int | None,
    *,
    max_results: int = 2,
    api_key: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict[str, Any]]:
    """Return up to N article snippets for fact-checking. Cached on disk."""
    key = cache_key(defendant, victim, year)
    async with session_scope() as session:
        cached = await TavilyRepo(session).get(key)
        if cached:
            return json.loads(cached.articles_json)

    api_key = api_key or env_settings.tavily_api_key
    if not api_key:
        log.warning("TAVILY_API_KEY missing — returning empty articles")
        return []

    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=20.0)

    query = build_query(defendant, victim, year)
    try:
        resp = await client.post(
            TAVILY_URL,
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        results = body.get("results", []) or []
        articles = [
            {
                "url": r.get("url"),
                "title": r.get("title"),
                "snippet": r.get("content") or r.get("snippet"),
            }
            for r in results
        ]
    finally:
        if own_client:
            await client.aclose()

    async with session_scope() as session:
        await TavilyRepo(session).put(key, query, articles)
    return articles
