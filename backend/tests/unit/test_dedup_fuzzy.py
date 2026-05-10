"""Golden-file dedup tests using real examples from handoff Section 7.2."""

from __future__ import annotations

import pytest

from interrogation_pipeline.dedup.fuzzy import (
    CaseStub,
    is_duplicate,
    parse_state,
    parse_year,
    similarity,
)


# ────────  parsers  ────────
@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Los Angeles, CA", "CA"),
        ("Los Angeles, California", "CA"),
        ("Houston, Texas", "TX"),
        ("Houston, TX", "TX"),
        ("Miami, FL 33130", "FL"),
        ("Brooklyn, New York", "NY"),
        ("", None),
        (None, None),
        ("Unknown location", None),
    ],
)
def test_parse_state(location, expected):
    assert parse_state(location) == expected


@pytest.mark.parametrize(
    ("date_str", "expected"),
    [
        ("2019-04-12", 2019),
        ("April 12, 2019", 2019),
        ("12/04/2019", 2019),
        ("Sometime in 2018", 2018),
        ("", None),
        (None, None),
        ("recently", None),
    ],
)
def test_parse_year(date_str, expected):
    assert parse_year(date_str) == expected


# ────────  similarity sanity ────────
def test_similarity_handles_initials_vs_full():
    assert similarity("Mark D. Latunski", "Mark David Latunski") >= 85


def test_similarity_handles_titles():
    assert similarity("Tracey Grist", "Mrs. Grist") >= 50  # not enough alone


# ────────  the real dedup rule ────────
@pytest.mark.parametrize(
    "a,b",
    [
        # All from handoff Section 7.2 — these MUST dedup.
        (
            CaseStub("Mark David Latunski", "Kevin Bacon", "MI", 2019),
            CaseStub("Mark D. Latunski", "Kevin Bacon", "MI", 2019),
        ),
        (
            CaseStub("Michael Shane Bargo Jr.", "Seath Jackson", "FL", 2011),
            CaseStub("Michael Shane Bargo", "Seath Jackson", "FL", 2011),
        ),
        (
            CaseStub("Heather Fernandez Hoer", "John Doe", "TX", 2020),
            CaseStub("Heather Fernandez-Hoefer", "John Doe", "TX", 2020),
        ),
        # Same defendant + same victim + same state, year missing — still dedups (2 of 3).
        (
            CaseStub("Sean Lannon", "Michael Dabkowski", "NJ", None),
            CaseStub("Shawn Lannon", "Michael Dabkowski", "NJ", 2021),
        ),
    ],
)
def test_known_duplicates(a, b):
    assert is_duplicate(a, b), f"Expected duplicate: {a} vs {b}"


@pytest.mark.parametrize(
    "a,b",
    [
        # Same name, totally unrelated cases — must NOT dedup.
        (
            CaseStub("John Smith", "Alice Brown", "TX", 2020),
            CaseStub("John Smith", "Bob Carter", "FL", 2018),
        ),
        # Defendant differs significantly — must NOT dedup even if everything else matches.
        (
            CaseStub("Alondra Hobbs", "Tony Jackson", "GA", 2022),
            CaseStub("Carol Williams", "Tony Jackson", "GA", 2022),
        ),
        # Defendant matches but only ONE corroborating field — must NOT dedup.
        (
            CaseStub("Mark David Latunski", "Kevin Bacon", "MI", 2019),
            CaseStub("Mark D. Latunski", "Different Victim", "OH", 2019),
        ),
    ],
)
def test_known_non_duplicates(a, b):
    assert not is_duplicate(a, b), f"Expected NOT duplicate: {a} vs {b}"


def test_defendant_below_threshold_short_circuits():
    a = CaseStub("Adam Adams", "X", "TX", 2020)
    b = CaseStub("Bob Bobson", "X", "TX", 2020)
    assert not is_duplicate(a, b)


def test_empty_fields_safe():
    assert not is_duplicate(CaseStub(), CaseStub())
    assert not is_duplicate(CaseStub("A"), CaseStub("A"))   # no corroboration → no dup
