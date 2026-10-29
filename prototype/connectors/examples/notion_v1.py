"""Notion connector, version 1.

Generated from the connector spec by templates. Do not edit: change the spec and regenerate.

Host: api.notion.com (read-only GET calls; the transport blocks every other host).
Tier T3: Public API lists users but has no activity data
Usage: none in the API.

The six assignment items are marked in the code: 1. API client, 2. Auth setup, 3. Users and
usage, 4. Error handling, 5. Pagination, 6. Logging.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from runtime import helpers as h
from runtime.errors import ConnectorError
from runtime.logs import RunLogger
from runtime.transport import HostBlockedError

APP = "Notion"
SLUG = "notion"
VERSION = 1
HOST_PATTERN = "api.notion.com"
BASE_URL = "https://api.notion.com/v1"
VARIABLE_PATTERNS: dict[str, str] = {}
AUTH_FIELDS: list[str] = ["token"]
DEFAULT_HEADERS: dict[str, str] = {"Accept": "application/json", "Notion-Version": "2026-03-11"}
META: dict[str, Any] = {
    "tier": "T3",
    "usage_definition": {"metric_label": None, "active_rule": None, "proxy": False, "fallback": "sso_last_login"},
    "has_usage_stream": False,
    "has_last_active": False,
    "join_on": None,
    "window_days": None,
}

REQUESTS_PER_MINUTE = 180
RETRY_AFTER_HEADER: str | None = "Retry-After"
RESET_SECONDS_HEADER: str | None = None
MAX_RATE_LIMIT_TRIES = 5
MAX_SERVER_ERROR_TRIES = 3
MAX_WAIT_SECONDS = 60.0


# 1. API client
class Client:
    def __init__(
        self,
        secrets: dict[str, str],
        variables: dict[str, str],
        transport: httpx.BaseTransport,
        log: RunLogger,
        limits: dict[str, int | None],
        now: datetime,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.secrets = secrets
        self.vars: dict[str, str] = dict(variables)
        self.log = log
        self.limits = limits
        self.now = now
        self.sleep = sleep
        self.pages: dict[str, int] = {"users": 0, "usage": 0}
        self.warnings: list[str] = []
        self.last_shape: Any = None  # keys and types of the last response, for repair; never values
        self._last_request = 0.0
        timeout_s = limits.get("timeout_s")
        self._deadline = time.monotonic() + timeout_s if timeout_s else None
        self.http = httpx.Client(
            base_url=h.fill(BASE_URL, self.vars, now),
            transport=transport,
            headers=DEFAULT_HEADERS,
            timeout=30.0,
            follow_redirects=False,
        )

    # 2. Auth setup: bearer_token (scopes: User information with email addresses)
    def login(self) -> None:
        self.http.headers["Authorization"] = "Bearer " + h.fill("{secrets.token}", self.vars, self.now, self.secrets)

    def _extract(self, name: str, expression: str, body: Any) -> None:
        value = h.search(expression, body)
        if not isinstance(value, str | int) or isinstance(value, bool) or value == "":
            raise ConnectorError("MAPPING_FAILED", detail=f"login value {name!r} not found")
        self.vars[name] = str(value)

    # 4. Error handling: retry, backoff and plain error codes. 6. Logging: one line per request.
    def request(self, step: str, path_or_url: str, params: list[tuple[str, str]] | None = None) -> httpx.Response:
        rate_limited = 0
        server_errors = 0
        attempt = 0
        while True:
            self._pace()
            start = time.monotonic()
            try:
                query = httpx.QueryParams(tuple(params)) if params is not None else None
                response = self.http.get(path_or_url, params=query)
            except HostBlockedError:
                self.log.request(step, "GET", httpx.URL(path_or_url).path, None, 0, None, attempt)
                raise ConnectorError("HOST_BLOCKED") from None
            except httpx.ProxyError as error:
                # The sandbox's egress proxy refused the call: only the spec's host is allowed out.
                blocked = "403" in str(error)
                raise ConnectorError("HOST_BLOCKED" if blocked else "UNREACHABLE", detail="egress proxy") from None
            except httpx.TimeoutException:
                server_errors += 1
                self.log.request(step, "GET", httpx.URL(path_or_url).path, None, 0, None, attempt)
                if server_errors >= MAX_SERVER_ERROR_TRIES:
                    raise ConnectorError("TIMEOUT") from None
                attempt += 1
                self._wait(h.backoff(server_errors))
                continue
            except httpx.ConnectError:
                raise ConnectorError("UNREACHABLE", detail="could not connect") from None
            except httpx.HTTPError:
                raise ConnectorError("SERVER_ERROR", detail="connection failed") from None
            ms = int((time.monotonic() - start) * 1000)
            status = response.status_code
            self.log.request(step, "GET", response.request.url.path, status, ms, None, attempt)
            attempt += 1
            if status == 429:
                rate_limited += 1
                if rate_limited >= MAX_RATE_LIMIT_TRIES:
                    raise ConnectorError("RATE_LIMITED_OUT", 429)
                self._wait(self._rate_limit_wait(response, rate_limited))
                continue
            if status >= 500:
                server_errors += 1
                if server_errors >= MAX_SERVER_ERROR_TRIES:
                    raise ConnectorError("SERVER_ERROR", status)
                self._wait(h.backoff(server_errors))
                continue
            if status == 401:
                raise ConnectorError("AUTH_REJECTED", status)
            if status == 402:
                raise ConnectorError("PAID_ONLY", status)
            if status == 403:
                raise ConnectorError("PERMISSION_OR_SCOPE", status)
            if status >= 300:
                raise ConnectorError("WRONG_REQUEST", status)
            return response

    def get_json(self, step: str, path_or_url: str, query: dict[str, str | list[str]] | None = None) -> Any:
        params = h.fill_query(query, self.vars, self.now) if query else None
        return self._json(self.request(step, path_or_url, params))

    def _json(self, response: httpx.Response) -> Any:
        try:
            body = response.json()
        except json.JSONDecodeError:
            raise ConnectorError("WRONG_REQUEST", response.status_code, "response is not JSON") from None
        self.last_shape = h.shape(body)
        return body

    def _rate_limit_wait(self, response: httpx.Response, tries: int) -> float:
        for header in (RETRY_AFTER_HEADER, "Retry-After", RESET_SECONDS_HEADER):
            if header and header in response.headers:
                try:
                    return float(response.headers[header])
                except ValueError:
                    continue
        return h.backoff(tries)

    def _pace(self) -> None:
        """Stay below the documented rate limit; stop at the run's time limit."""
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise ConnectorError("TIMEOUT")
        gap = 60.0 / REQUESTS_PER_MINUTE - (time.monotonic() - self._last_request)
        if gap > 0:
            self.sleep(gap)
        self._last_request = time.monotonic()

    def _wait(self, seconds: float) -> None:
        self.sleep(min(max(seconds, 0.0), MAX_WAIT_SECONDS))

    # 5. Pagination for users: cursor
    def fetch_users(self) -> list[Any]:
        path = h.fill("/users", self.vars, self.now, encode=True)
        params = h.fill_query({"page_size": "100"}, self.vars, self.now)
        cap = self.limits.get("users_pages")
        restarted = False
        while True:
            try:
                return self._pages_users(path, params, cap)
            except ConnectorError as error:
                # A cursor that stopped working mid-way (expired): start over once, then give up.
                if error.code != "CURSOR_EXPIRED" or restarted:
                    raise
                restarted = True
                self.pages["users"] = 0

    def _pages_users(self, path: str, params: list[tuple[str, str]], cap: int | None) -> list[Any]:
        rows: list[Any] = []
        previous: str | None = None
        seen: set[str] = set()
        cursor: str | None = None
        while True:
            if cap is not None and self.pages["users"] >= cap:
                self.warnings.append("users_capped")
                return rows
            page_params = params + ([("start_cursor", cursor)] if cursor else [])
            response = self._page("users", path, page_params, cursor is not None)
            body = self._json(response)
            page_rows = h.records("results[?type=='person']", body)
            self.pages["users"] += 1
            # Paging guard: the same page twice means the paging parameter is being ignored.
            fingerprint = json.dumps(page_rows, sort_keys=True, default=str)
            if page_rows and fingerprint == previous:
                raise ConnectorError("PAGINATION_LOOP")
            previous = fingerprint
            rows.extend(page_rows)
            if h.search("has_more", body) is not True:
                return rows
            next_cursor = h.search("next_cursor", body)
            if next_cursor is None or next_cursor == "":
                return rows
            cursor = str(next_cursor)
            if cursor in seen:
                raise ConnectorError("PAGINATION_LOOP")
            seen.add(cursor)

    def _page(
        self, step: str, path_or_url: str, params: list[tuple[str, str]] | None, follow_up: bool
    ) -> httpx.Response:
        try:
            return self.request(step, path_or_url, params)
        except ConnectorError as error:
            # A follow-up page that suddenly fails as a bad request means the cursor stopped working.
            if follow_up and error.code == "WRONG_REQUEST":
                raise ConnectorError("CURSOR_EXPIRED", error.status) from None
            raise


# 3. Users: map each record to the platform's canonical user fields.
def map_user(record: Any) -> dict[str, Any]:
    return {
        "external_id": h.search("id", record),
        "email": h.search("person.email", record),
        "name": h.search("name", record),
        "status": "active",
    }


def get_users(client: Client) -> list[dict[str, Any]]:
    return [map_user(record) for record in client.fetch_users()]


# 3. Usage: not in this app's API; the platform falls back to SSO last login, labelled as such.
def get_usage(client: Client, users: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {}
