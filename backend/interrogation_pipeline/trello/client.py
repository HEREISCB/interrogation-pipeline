"""Async Trello REST client + dedup-cache loader + name-based ID auto-discovery.

Trello API docs: https://developer.atlassian.com/cloud/trello/rest/

Auth = key + token query params. We hit the public REST endpoints; no SDK.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from interrogation_pipeline.config.settings import settings as env_settings
from interrogation_pipeline.dedup.fuzzy import parse_state, parse_year

log = logging.getLogger(__name__)

TRELLO_API = "https://api.trello.com/1"
PAGE_LIMIT = 1000


class TrelloError(Exception):
    pass


class TrelloClient:
    def __init__(
        self,
        key: str | None = None,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.key = key or env_settings.trello_api_key
        self.token = token or env_settings.trello_token
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "TrelloClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()

    def _params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        p: dict[str, Any] = {"key": self.key, "token": self.token}
        if extra:
            p.update(extra)
        return p

    async def _request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any = None
    ) -> Any:
        url = f"{TRELLO_API}{path}"
        for attempt in range(3):
            resp = await self._client.request(
                method, url, params=self._params(params), json=json
            )
            if resp.status_code == 429:
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                raise TrelloError(f"{method} {path} → {resp.status_code} {resp.text[:300]}")
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise TrelloError(f"{method} {path} kept getting 429")

    # ──── lookup ────
    async def find_board_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a board the user has access to by exact name (case-insensitive)."""
        boards = await self._request(
            "GET", "/members/me/boards", params={"fields": "name,id,closed"}
        )
        for b in boards or []:
            if b.get("closed"):
                continue
            if (b.get("name") or "").strip().lower() == name.strip().lower():
                return b
        return None

    async def find_list_by_name(
        self, board_id: str, name: str
    ) -> dict[str, Any] | None:
        lists = await self._request(
            "GET", f"/boards/{board_id}/lists", params={"fields": "name,id,closed"}
        )
        for lst in lists or []:
            if lst.get("closed"):
                continue
            if (lst.get("name") or "").strip().lower() == name.strip().lower():
                return lst
        return None

    # ──── card I/O ────
    async def list_all_cards(
        self, board_id: str, *, include_archived: bool = True
    ) -> list[dict[str, Any]]:
        """Paginated fetch of every card on a board (active + closed by default)."""
        out: list[dict[str, Any]] = []
        before: str | None = None
        while True:
            params: dict[str, Any] = {
                "fields": "name,desc,closed,idList,idBoard",
                "limit": PAGE_LIMIT,
                "filter": "all" if include_archived else "open",
            }
            if before:
                params["before"] = before
            page = await self._request("GET", f"/boards/{board_id}/cards", params=params)
            if not page:
                break
            out.extend(page)
            if len(page) < PAGE_LIMIT:
                break
            before = page[-1]["id"]
        return out

    async def create_card(
        self, list_id: str, *, name: str, desc: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/cards",
            params={"idList": list_id, "name": name[:512], "desc": desc[:16384]},
        )


# ──── parsing trello card descs into our dedup shape ────
DEFENDANT_RE = re.compile(r"\*\*Defendant Name\*\*:\s*(.+)", re.I)
VICTIM_RE = re.compile(r"\*\*Victim Name\*\*:\s*(.+)", re.I)
LOCATION_RE = re.compile(r"\*\*Location of Incident\*\*:\s*(.+)", re.I)
DATE_RE = re.compile(r"\*\*Date of Incident\*\*:\s*(.+)", re.I)


def _first_line(value: str) -> str:
    return value.splitlines()[0].strip() if value else ""


def parse_card_for_dedup(card: dict[str, Any]) -> dict[str, Any]:
    """Pull defendant/victim/state/year out of a Trello card description.

    Returns a record shaped for `TrelloCardCache` upserts.
    """
    desc = card.get("desc") or ""
    defendant = _first_line(DEFENDANT_RE.search(desc).group(1)) if DEFENDANT_RE.search(desc) else None
    victim = _first_line(VICTIM_RE.search(desc).group(1)) if VICTIM_RE.search(desc) else None
    location = _first_line(LOCATION_RE.search(desc).group(1)) if LOCATION_RE.search(desc) else None
    date_str = _first_line(DATE_RE.search(desc).group(1)) if DATE_RE.search(desc) else None
    return {
        "trello_card_id": card["id"],
        "board_id": card.get("idBoard", ""),
        "list_id": card.get("idList"),
        "list_name": None,  # filled by caller if available
        "title": card.get("name"),
        "description": desc,
        "parsed_defendant": defendant or card.get("name"),
        "parsed_victim": victim,
        "parsed_state": parse_state(location),
        "parsed_year": parse_year(date_str),
        "archived": bool(card.get("closed")),
    }
