"""Banned-state / banned-agency detection — used to badge cases on the dashboard.

Per Ayush's spec (May 2026): cases from FOIA-banned jurisdictions are NOT
skipped or rejected — they're highlighted so the human can decide quickly.
"""

from __future__ import annotations


def is_banned_state(state: str | None, banned_states: list[str]) -> bool:
    if not state:
        return False
    return state.upper() in {s.upper() for s in banned_states}


def is_banned_agency(agency: str | None, banned_agencies: list[str]) -> bool:
    if not agency:
        return False
    norm = agency.lower()
    return any(b.lower() in norm for b in banned_agencies)
