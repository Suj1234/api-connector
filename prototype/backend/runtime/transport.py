"""HTTP transports for generated connectors (TRD §2).

AllowOnlyHost wraps every connection: anything that isn't https to the spec's exact host is
refused before a byte is sent. ReplayTransport serves recorded responses for demo and tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

WILDCARD = "*"


class HostBlockedError(Exception):
    """The connector tried to reach a server other than its own host (exit code 8)."""

    def __init__(self, host: str) -> None:
        super().__init__(f"blocked call to {host!r}")
        self.host = host


class AllowOnlyHost(httpx.BaseTransport):
    def __init__(self, host: str, inner: httpx.BaseTransport | None = None) -> None:
        self.host = host.lower()
        self.inner = inner if inner is not None else httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.scheme != "https" or url.host.lower() != self.host or url.port not in (None, 443) or url.userinfo:
            raise HostBlockedError(url.host)
        return self.inner.handle_request(request)

    def close(self) -> None:
        self.inner.close()


class ReplayTransport(httpx.BaseTransport):
    """Serves a recording. A request that isn't in it gets a 404, just like a wrong path on the real API."""

    def __init__(self, recording: dict[str, Any]) -> None:
        self.interactions: list[dict[str, Any]] = list(recording.get("interactions", []))
        self.calls: list[str] = []

    @classmethod
    def from_file(cls, path: str | Path) -> ReplayTransport:
        return cls(load_recording(path))

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        best: tuple[int, dict[str, Any]] | None = None
        for item in self.interactions:
            matched = _match_score(item, request)
            if matched is not None and (best is None or matched > best[0]):
                best = (matched, item)
        if best is None:
            return httpx.Response(404, json={"error": "not_found", "detail": "Not in the recording"})
        item = best[1]
        headers = {str(k): str(v) for k, v in item.get("headers", {}).items()}
        return httpx.Response(item.get("status", 200), headers=headers, json=item.get("body"))


def load_recording(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        recording: dict[str, Any] = json.load(f)
    return recording


def _match_score(item: dict[str, Any], request: httpx.Request) -> int | None:
    """None if the interaction can't answer this request; else how many recorded params it matched.

    Every recorded param must be in the request with the same value ("*" matches any value).
    Extra request params are ignored, as most APIs ignore unknown params; the most specific
    recording wins (page 2, with its cursor, beats page 1).
    """
    if item.get("method", "GET") != request.method:
        return None
    url = httpx.URL(item["url"])
    if url.host != request.url.host or url.path != request.url.path:
        return None
    actual: dict[str, list[str]] = {}
    for key, value in request.url.params.multi_items():
        actual.setdefault(key, []).append(value)
    expected: dict[str, Any] = item.get("query", {})
    for key, value in expected.items():
        if key not in actual:
            return None
        if value == WILDCARD:
            continue
        wanted = value if isinstance(value, list) else [value]
        if sorted(wanted) != sorted(actual[key]):
            return None
    return len(expected)
