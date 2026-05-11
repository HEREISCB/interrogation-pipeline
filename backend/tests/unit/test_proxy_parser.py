"""Cover every input shape the bulk-import endpoint might see."""

import pytest

from interrogation_pipeline.scrape.proxy_parser import (
    ParsedProxy,
    parse_bulk,
    parse_line,
)


@pytest.mark.parametrize(
    "line,expected",
    [
        (
            "p.webshare.io:80:testuser-residential-1:FAKEPASSWORD",
            ParsedProxy("p.webshare.io", 80, "testuser-residential-1", "FAKEPASSWORD"),
        ),
        (
            "user:pass@1.2.3.4:8080",
            ParsedProxy("1.2.3.4", 8080, "user", "pass"),
        ),
        (
            "http://user:pass@host.example:1080",
            ParsedProxy("host.example", 1080, "user", "pass"),
        ),
        (
            "https://user:pass@host.example:443/",
            ParsedProxy("host.example", 443, "user", "pass"),
        ),
        (
            "1.2.3.4:8888",
            ParsedProxy("1.2.3.4", 8888),
        ),
        ("", None),
        ("# this is a comment", None),
        ("garbage data", None),
    ],
)
def test_parse_line_shapes(line, expected):
    assert parse_line(line) == expected


def test_parse_bulk_dedups_and_collects_rejects():
    text = """
# webshare style
p.webshare.io:80:testuser-residential-1:FAKEPASSWORD
p.webshare.io:80:testuser-residential-2:FAKEPASSWORD
p.webshare.io:80:testuser-residential-1:FAKEPASSWORD
not a proxy
http://u:p@h.com:1080
""".strip()
    proxies, rejected = parse_bulk(text)
    assert len(proxies) == 3
    assert len(rejected) == 1
    assert rejected[0] == "not a proxy"
    # Order preserved
    assert proxies[0].username == "testuser-residential-1"
    assert proxies[1].username == "testuser-residential-2"
    assert proxies[2].host == "h.com"


def test_parsed_proxy_url_format():
    p = ParsedProxy("h", 8080, "u", "p")
    assert p.url == "http://u:p@h:8080"

    p = ParsedProxy("h", 8080)
    assert p.url == "http://h:8080"
