"""Send a cleaned transcript to Claude Haiku 4.5 with the homicide prompt.

Returns a typed pydantic model. Handles:
  - JSON parse errors (one retry, then surface raw response)
  - 'has_interrogation: false' (rejection — still recorded)
  - multi-defendant dict/list responses (coerced to strings)
  - rate-limit / credit-out (raised so the runner can stop cleanly)
"""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Any, Optional

from anthropic import AsyncAnthropic, BadRequestError
from pydantic import BaseModel, Field, ValidationError

from interrogation_pipeline.config.settings import settings as env_settings

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_PROMPT_PATH = PROMPTS_DIR / "scan.txt"

# Anthropic Haiku 4.5 — pricing $0.80 / $4 per M tokens (handoff §3.1).
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
INPUT_PRICE_PER_TOKEN = 0.80 / 1_000_000
OUTPUT_PRICE_PER_TOKEN = 4.00 / 1_000_000


class DramaBreakdown(BaseModel):
    bodycam_points: int = 0
    interrogation_points: int = 0
    additional_footage_points: int = 0
    case_intrinsics_points: int = 0


class FootageType(BaseModel):
    type: str
    description: Optional[str] = None
    approx_timestamp: Optional[str] = None


class ScanResult(BaseModel):
    """Pydantic schema mirroring what the prompt asks Haiku to return."""

    has_homicide: bool
    rejection_reason: Optional[str] = None

    category: Optional[str] = None
    drama_rating: Optional[int] = None
    drama_breakdown: Optional[DramaBreakdown] = None
    drama_summary: Optional[str] = None

    defendant_name: Optional[str] = None
    victim_name: Optional[str] = None
    charges: Optional[str] = None
    date_of_incident: Optional[str] = None
    location_of_incident: Optional[str] = None
    arresting_agency: Optional[str] = None
    verdict: Optional[str] = None
    summary: Optional[str] = None
    footage_types: list[FootageType] = Field(default_factory=list)

    raw_response: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    prompt_version: str = "v2-homicide-2026-05"


class CreditExhausted(Exception):
    """Anthropic balance ran out mid-run — runner should pause cleanly."""


def _coerce_to_str(value: Any) -> Optional[str]:
    """Multi-defendant cases sometimes come back as dicts/lists — flatten them."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # {'name': 'Mark Latunski'} or similar
        for k in ("name", "full_name", "value"):
            if k in value and isinstance(value[k], str):
                return value[k]
        return json.dumps(value)
    if isinstance(value, list):
        return ", ".join(_coerce_to_str(v) or "" for v in value if v)
    return str(value)


def _load_prompt(path: Path | None = None) -> str:
    p = path or DEFAULT_PROMPT_PATH
    return p.read_text(encoding="utf-8")


_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL | re.IGNORECASE)


def _unwrap_array(data: Any) -> dict[str, Any]:
    """If Haiku ignored the 'one object per response' instruction and returned
    an array, unwrap to the first dict element so the caller still works."""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                return item
        raise json.JSONDecodeError("response is a list with no dict items", "", 0)
    if not isinstance(data, dict):
        raise json.JSONDecodeError(f"expected dict, got {type(data).__name__}", "", 0)
    return data


def _parse_response(body: str) -> dict[str, Any]:
    """Extract the JSON object Haiku returns, tolerating markdown fences and prose.

    Handles three observed failure modes:
      1. Response wrapped in ```json ... ``` markdown fence
      2. Closing fence missing (response truncated)
      3. JSON preceded or followed by prose
    """
    body = body.strip()

    # 1. If wrapped in a complete markdown fence, lift the content out.
    m = _FENCE_RE.search(body)
    if m:
        body = m.group(1).strip()
    elif body.startswith("```"):
        # 2. Incomplete fence (opening but no closing — usually a truncated reply).
        body = body[3:]
        if body.lower().startswith("json"):
            body = body[4:]
        body = body.lstrip("\n").rstrip()
        # Strip a stray trailing ``` if it slipped in
        if body.endswith("```"):
            body = body[:-3].rstrip()

    try:
        return _unwrap_array(json.loads(body))
    except json.JSONDecodeError:
        pass

    # 3. Walk forward from the first `{`, balancing braces (respecting strings)
    # so we can pull out a clean JSON object embedded in prose.
    start = body.find("{")
    if start < 0:
        raise json.JSONDecodeError("no '{' found", body, 0)
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(body)):
        c = body[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return _unwrap_array(json.loads(body[start : i + 1]))

    # Fall back to old behaviour (first '{' to last '}') for the truncated case.
    end = body.rfind("}")
    if end > start:
        return _unwrap_array(json.loads(body[start : end + 1]))
    raise json.JSONDecodeError("unbalanced braces", body, start)


async def scan_transcript(
    transcript: str,
    title: str,
    *,
    duration_sec: int | None = None,
    client: AsyncAnthropic | None = None,
    model: str = DEFAULT_MODEL,
    prompt_path: Path | None = None,
) -> ScanResult:
    """Run the prompt + transcript through Haiku and return a typed ScanResult."""
    own_client = client is None
    if client is None:
        client = AsyncAnthropic(api_key=env_settings.anthropic_api_key)

    prompt = _load_prompt(prompt_path)
    user_block = (
        f"VIDEO TITLE: {title}\n"
        f"DURATION_SEC: {duration_sec or 'unknown'}\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )
    try:
        try:
            resp = await client.messages.create(
                model=model,
                # Bumped from 2048 — the full schema (footage_types, drama_breakdown,
                # 200-word summary) sometimes ran over and got truncated mid-JSON,
                # which the parser couldn't recover from.
                max_tokens=4096,
                system=prompt,
                messages=[{"role": "user", "content": user_block}],
            )
        except BadRequestError as e:
            if "credit" in str(e).lower():
                raise CreditExhausted(str(e)) from e
            raise

        content_blocks = resp.content or []
        body = "".join(
            getattr(b, "text", "") for b in content_blocks if getattr(b, "type", "") == "text"
        )
        try:
            data = _parse_response(body)
        except (json.JSONDecodeError, ValueError):
            log.warning("Unparseable Haiku response — %s…", body[:200])
            return ScanResult(
                has_homicide=False,
                rejection_reason="json parse failure",
                raw_response={"raw_text": body},
                input_tokens=getattr(resp.usage, "input_tokens", 0),
                output_tokens=getattr(resp.usage, "output_tokens", 0),
            )

        accepted = bool(data.get("has_interrogation"))
        norm = {
            "has_homicide": accepted,
            "rejection_reason": data.get("rejection_reason"),
            "category": data.get("category"),
            "drama_rating": data.get("drama_rating"),
            "drama_breakdown": data.get("drama_breakdown"),
            "drama_summary": data.get("drama_summary"),
            "defendant_name": _coerce_to_str(data.get("defendant_name")),
            "victim_name": _coerce_to_str(data.get("victim_name")),
            "charges": _coerce_to_str(data.get("charges")),
            "date_of_incident": _coerce_to_str(data.get("date_of_incident")),
            "location_of_incident": _coerce_to_str(data.get("location_of_incident")),
            "arresting_agency": _coerce_to_str(data.get("arresting_agency")),
            "verdict": _coerce_to_str(data.get("verdict")),
            "summary": _coerce_to_str(data.get("summary")),
            "footage_types": data.get("footage_types") or [],
            "raw_response": data,
        }

        try:
            result = ScanResult.model_validate(norm)
        except ValidationError as e:
            log.warning("Haiku response failed schema: %s", e)
            return ScanResult(
                has_homicide=accepted,
                rejection_reason="schema validation failed",
                raw_response=data,
            )

        result.input_tokens = getattr(resp.usage, "input_tokens", 0)
        result.output_tokens = getattr(resp.usage, "output_tokens", 0)
        result.cost_usd = (
            result.input_tokens * INPUT_PRICE_PER_TOKEN
            + result.output_tokens * OUTPUT_PRICE_PER_TOKEN
        )
        return result
    finally:
        if own_client:
            await client.close()
