from interrogation_pipeline.dedup.banned import is_banned_agency, is_banned_state

BANNED_STATES = ["AR", "CA", "AL", "OK", "PA", "KY", "IL"]
BANNED_AGENCIES = ["LAPD", "Los Angeles Police", "NYPD", "New York Police"]


def test_state_match_uppercase():
    assert is_banned_state("CA", BANNED_STATES)


def test_state_match_lowercase():
    assert is_banned_state("ca", BANNED_STATES)


def test_state_not_banned():
    assert not is_banned_state("TX", BANNED_STATES)
    assert not is_banned_state(None, BANNED_STATES)
    assert not is_banned_state("", BANNED_STATES)


def test_agency_match_acronym():
    assert is_banned_agency("LAPD", BANNED_AGENCIES)
    assert is_banned_agency("L.A.P.D.", BANNED_AGENCIES) is False  # punctuation mismatch is fine — we want exact tokens


def test_agency_match_substring_case_insensitive():
    assert is_banned_agency("Los Angeles Police Department", BANNED_AGENCIES)
    assert is_banned_agency("nypd 14th precinct", BANNED_AGENCIES)


def test_agency_other():
    assert not is_banned_agency("Houston PD", BANNED_AGENCIES)
    assert not is_banned_agency(None, BANNED_AGENCIES)
