"""Parse bulk-pasted proxy lists into structured rows.

Supports the common formats we see in the wild:
  host:port:user:pass             ← Webshare, default
  host:port@user:pass             ← rare
  user:pass@host:port             ← curl-style
  http://user:pass@host:port      ← full URL
  host:port                       ← unauthenticated

Ignores blank lines and lines starting with '#'.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class ParsedProxy:
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"


URL_RE = re.compile(
    r"^https?://(?P<user>[^:/@]+):(?P<pw>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/?$"
)
USER_AT_HOST_RE = re.compile(
    r"^(?P<user>[^:/@\s]+):(?P<pw>[^@\s]+)@(?P<host>[^:/\s]+):(?P<port>\d+)$"
)
HOST_PORT_USER_PASS_RE = re.compile(
    r"^(?P<host>[^:/\s]+):(?P<port>\d+):(?P<user>[^:/\s]+):(?P<pw>[^:\s]+)$"
)
HOST_PORT_RE = re.compile(r"^(?P<host>[^:/\s]+):(?P<port>\d+)$")


def parse_line(line: str) -> ParsedProxy | None:
    """Return a ParsedProxy or None if the line isn't a recognized proxy."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if m := URL_RE.match(s):
        return ParsedProxy(
            host=m["host"], port=int(m["port"]), username=m["user"], password=m["pw"]
        )
    if m := USER_AT_HOST_RE.match(s):
        return ParsedProxy(
            host=m["host"], port=int(m["port"]), username=m["user"], password=m["pw"]
        )
    if m := HOST_PORT_USER_PASS_RE.match(s):
        return ParsedProxy(
            host=m["host"], port=int(m["port"]), username=m["user"], password=m["pw"]
        )
    if m := HOST_PORT_RE.match(s):
        return ParsedProxy(host=m["host"], port=int(m["port"]))
    return None


def parse_bulk(text: str) -> tuple[list[ParsedProxy], list[str]]:
    """Parse a multi-line blob. Returns (proxies, rejected_lines)."""
    proxies: list[ParsedProxy] = []
    rejected: list[str] = []
    seen: set[tuple[str, int, str]] = set()
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        p = parse_line(s)
        if p is None:
            rejected.append(s[:120])
            continue
        key = (p.host, p.port, p.username)
        if key in seen:
            continue
        seen.add(key)
        proxies.append(p)
    return proxies, rejected


def to_rows(proxies: Iterable[ParsedProxy]) -> list[dict]:
    return [
        {
            "host": p.host,
            "port": p.port,
            "username": p.username,
            "password": p.password,
        }
        for p in proxies
    ]
