"""Multi-field fuzzy dedup logic from handoff Section 7.2.

Two cases are duplicates iff:
  - defendant similarity >= 85%   (REQUIRED)
  AND at least 2 of the following 3:
  - victim similarity >= 85%
  - state exact match
  - year exact match
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol

from rapidfuzz import fuzz

DEFENDANT_THRESHOLD = 85
VICTIM_THRESHOLD = 85
US_STATE_PATTERN = re.compile(
    r",\s*([A-Z]{2}|"
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|"
    r"Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|"
    r"Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|"
    r"Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
    r"North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|"
    r"South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
    r"West Virginia|Wisconsin|Wyoming"
    r")\b",
    flags=re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")

STATE_TO_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


class CaseLike(Protocol):
    """Anything with these attributes can be deduped — Case ORM, dict, or test stub."""

    defendant_name: Optional[str]
    victim_name: Optional[str]
    state: Optional[str]
    year: Optional[int]


@dataclass(slots=True)
class CaseStub:
    defendant_name: Optional[str] = None
    victim_name: Optional[str] = None
    state: Optional[str] = None
    year: Optional[int] = None


def parse_state(location: Optional[str]) -> Optional[str]:
    """Extract a 2-letter US state abbrev from a 'City, State' string."""
    if not location:
        return None
    m = US_STATE_PATTERN.search(location)
    if not m:
        return None
    raw = m.group(1).strip()
    if len(raw) == 2:
        return raw.upper()
    return STATE_TO_ABBREV.get(raw.lower())


def parse_year(date_str: Optional[str]) -> Optional[int]:
    """Find a 4-digit year in a free-form date string."""
    if not date_str:
        return None
    m = YEAR_PATTERN.search(date_str)
    return int(m.group(1)) if m else None


def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"[^\w\s]", " ", s).strip().lower()


def similarity(a: Optional[str], b: Optional[str]) -> float:
    """Token-set ratio so 'Mark D. Latunski' ≈ 'Mark David Latunski'."""
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(_norm(a), _norm(b))


def is_duplicate(a: CaseLike, b: CaseLike) -> bool:
    """Return True iff a and b satisfy the multi-field dedup rule."""
    defendant_score = similarity(a.defendant_name, b.defendant_name)
    if defendant_score < DEFENDANT_THRESHOLD:
        return False

    corroborating = 0
    if similarity(a.victim_name, b.victim_name) >= VICTIM_THRESHOLD:
        corroborating += 1
    if a.state and b.state and a.state == b.state:
        corroborating += 1
    if a.year and b.year and a.year == b.year:
        corroborating += 1

    return corroborating >= 2


def find_duplicates(case: CaseLike, candidates: list[CaseLike]) -> list[CaseLike]:
    """Return the subset of candidates that fuzz-match `case`."""
    return [c for c in candidates if is_duplicate(case, c)]


def first_letter_buckets(name: Optional[str]) -> set[str]:
    """Bucket key built from the first letter of every word in a name.

    Used to prune the candidate set before pairwise comparison so we don't run
    rapidfuzz against 5,000+ Trello cards per case. 'Mark David Latunski' →
    {'m','d','l'}.
    """
    if not name:
        return set()
    return {w[0].lower() for w in name.split() if w}


def share_bucket(a: Optional[str], b: Optional[str]) -> bool:
    """Two names are worth comparing if their first-letter buckets overlap."""
    return bool(first_letter_buckets(a) & first_letter_buckets(b))
