from pathlib import Path

from interrogation_pipeline.scan.vtt import clean_vtt, clean_vtt_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_clean_vtt_strips_headers_timecodes_and_inline_tags():
    raw = (FIXTURES / "sample_clean.vtt").read_text()
    out = clean_vtt(raw)
    assert "WEBVTT" not in out
    assert "-->" not in out
    assert "<00:" not in out
    assert "Mark David Latunski" in out
    assert "Houston Texas" in out


def test_clean_vtt_dedups_consecutive_lines():
    raw = (FIXTURES / "sample_clean.vtt").read_text()
    out = clean_vtt(raw)
    # The "welcome back to the channel today we have" line appears twice in the
    # raw VTT — should appear once in the cleaned output.
    assert out.count("welcome back to the channel today we have") == 1


def test_clean_vtt_file_round_trips():
    out = clean_vtt_file(FIXTURES / "sample_clean.vtt")
    assert "Houston" in out
