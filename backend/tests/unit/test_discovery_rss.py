"""RSS parsing tests using a real-shaped sample feed."""

from __future__ import annotations

from pathlib import Path

import pytest

from interrogation_pipeline.discovery.rss import parse_feed, rss_url_for

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_xml() -> bytes:
    return (FIXTURES / "rss_midwestsafety_sample.xml").read_bytes()


def test_parse_feed_extracts_three_entries(sample_xml):
    stubs = parse_feed(sample_xml)
    assert len(stubs) == 3
    ids = [s.video_id for s in stubs]
    assert "abc123XYZab" in ids
    assert "def456PQRcd" in ids
    assert "ghi789LMNef" in ids


def test_parse_feed_assigns_channel_id(sample_xml):
    stubs = parse_feed(sample_xml)
    assert all(s.channel_id == "UCnopQE7N9wvuwqK7TNCB48Q" for s in stubs)


def test_parse_feed_published_iso_is_utc(sample_xml):
    stubs = parse_feed(sample_xml)
    by_id = {s.video_id: s for s in stubs}
    assert by_id["abc123XYZab"].published_iso.startswith("2026-05-09T22:30:00")


def test_parse_feed_titles_preserved(sample_xml):
    stubs = parse_feed(sample_xml)
    titles = [s.title for s in stubs]
    assert any("Confession in Murder" in t for t in titles)


def test_parse_feed_invalid_xml_raises():
    with pytest.raises(ValueError):
        parse_feed(b"<not valid xml")


def test_rss_url_uc_channel():
    url = rss_url_for("UCnopQE7N9wvuwqK7TNCB48Q")
    assert "channel_id=UCnopQE7N9wvuwqK7TNCB48Q" in url


def test_rss_url_handle_uses_user_param():
    url = rss_url_for("@MidwestSafety")
    assert "user=MidwestSafety" in url
