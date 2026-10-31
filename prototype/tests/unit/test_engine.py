"""Generated-connector behaviour against a fake server (TRD §3, §6, §7).

Every test renders a spec with the real templates and runs it through the real runner; only the
network is replaced by httpx.MockTransport (still behind AllowOnlyHost).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.conftest import base_spec, mock, run_module

Build = Callable[[dict[str, Any]], Path]
LIVE = {"run_mode": "live", "secrets": {"token": "tok-secret-123"}}
USERS = [{"id": i, "email": f"user{i}@acme.example", "last_seen": "2026-10-01T00:00:00Z"} for i in range(1, 8)]


def ids(run: Any) -> list[str]:
    return sorted(r["external_id"] for r in run.records)


ALL_IDS = sorted(str(u["id"]) for u in USERS)


# --- the six paginators -------------------------------------------------------------


def test_pagination_none(build_module: Build) -> None:
    module = build_module(base_spec())
    run = run_module(module, LIVE, mock(lambda r: httpx.Response(200, json={"data": USERS})))
    assert run.exit_code == 0 and ids(run) == ALL_IDS


def test_pagination_cursor_with_has_more(build_module: Build) -> None:
    spec = base_spec(
        pagination={"type": "cursor", "request_param": "after", "next_cursor_path": "next", "has_more_path": "more"}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        after = request.url.params.get("after")
        if after is None:
            return httpx.Response(200, json={"data": USERS[:3], "next": "c1", "more": True})
        if after == "c1":
            return httpx.Response(200, json={"data": USERS[3:], "next": "c2", "more": False})
        return httpx.Response(400)

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 0 and ids(run) == ALL_IDS
    assert run.result["summary"]["pages"]["users"] == 2


def test_pagination_next_url(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "next_url", "next_url_path": "links.next"})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json={"data": USERS[4:], "links": {"next": None}})
        return httpx.Response(
            200, json={"data": USERS[:4], "links": {"next": "https://api.example.com/v1/users?page=2"}}
        )

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 0 and ids(run) == ALL_IDS


def test_pagination_link_header(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "link_header"})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json={"data": USERS[4:]})
        link = '<https://api.example.com/v1/users?page=2>; rel="next"'
        return httpx.Response(200, json={"data": USERS[:4]}, headers={"Link": link})

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 0 and ids(run) == ALL_IDS


def test_pagination_offset_limit(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "offset_limit", "offset_param": "offset", "limit_param": "limit", "limit": 3})

    def handler(request: httpx.Request) -> httpx.Response:
        offset, limit = int(request.url.params["offset"]), int(request.url.params["limit"])
        return httpx.Response(200, json={"data": USERS[offset : offset + limit]})

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 0 and ids(run) == ALL_IDS
    assert run.result["summary"]["pages"]["users"] == 3


def test_pagination_page_number(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "page_number", "page_param": "page", "start": 1})

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(200, json={"data": USERS[(page - 1) * 3 : page * 3]})

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 0 and ids(run) == ALL_IDS


# --- paging guards ---------------------------------------------------------------------


def test_repeated_cursor_is_a_pagination_loop(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "cursor", "request_param": "after", "next_cursor_path": "next"})
    pages = {None: (USERS[:2], "c1"), "c1": (USERS[2:4], "c2"), "c2": (USERS[4:6], "c1")}

    def handler(request: httpx.Request) -> httpx.Response:
        rows, nxt = pages[request.url.params.get("after")]
        return httpx.Response(200, json={"data": rows, "next": nxt})

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 6 and run.result["error_code"] == "PAGINATION_LOOP"


def test_ignored_page_parameter_is_a_pagination_loop(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "page_number", "page_param": "page", "start": 1})
    run = run_module(build_module(spec), LIVE, mock(lambda r: httpx.Response(200, json={"data": USERS[:3]})))
    assert run.exit_code == 6 and run.result["error_code"] == "PAGINATION_LOOP"


def test_expired_cursor_restarts_once_then_fails(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "cursor", "request_param": "after", "next_cursor_path": "next"})
    calls = {"first": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("after") is None:
            calls["first"] += 1
            return httpx.Response(200, json={"data": USERS[:3], "next": "c1"})
        return httpx.Response(400, json={"error": "cursor expired"})

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert calls["first"] == 2
    assert run.exit_code == 6 and run.result["error_code"] == "CURSOR_EXPIRED"


def test_expired_cursor_recovers_after_restart(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "cursor", "request_param": "after", "next_cursor_path": "next"})
    state = {"expired_once": False}

    def handler(request: httpx.Request) -> httpx.Response:
        after = request.url.params.get("after")
        if after is None:
            return httpx.Response(200, json={"data": USERS[:3], "next": "c1"})
        if not state["expired_once"]:
            state["expired_once"] = True
            return httpx.Response(400)
        return httpx.Response(200, json={"data": USERS[3:], "next": None})

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 0 and ids(run) == ALL_IDS


def test_test_mode_caps_pages(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "offset_limit", "offset_param": "o", "limit_param": "l", "limit": 1})

    def handler(request: httpx.Request) -> httpx.Response:
        o = int(request.url.params["o"])
        return httpx.Response(200, json={"data": USERS[o : o + 1]})

    payload = {**LIVE, "limits": {"users_pages": 2}}
    run = run_module(build_module(spec), payload, mock(handler))
    assert run.exit_code == 0 and len(run.records) == 2
    assert "users_capped" in run.result["summary"]["warnings"]


# --- retry and backoff -------------------------------------------------------------------


def flaky(statuses: list[int], headers: dict[str, str] | None = None) -> httpx.MockTransport:
    queue = list(statuses)

    def handler(_: httpx.Request) -> httpx.Response:
        status = queue.pop(0) if queue else 200
        if status == 200:
            return httpx.Response(200, json={"data": USERS})
        return httpx.Response(status, headers=headers or {})

    return mock(handler)


def test_429_uses_retry_after(build_module: Build, no_real_sleep: list[float]) -> None:
    run = run_module(build_module(base_spec()), LIVE, flaky([429], {"Retry-After": "7"}))
    assert run.exit_code == 0
    assert 7.0 in no_real_sleep


def test_429_uses_rate_limit_reset_when_no_retry_after(build_module: Build, no_real_sleep: list[float]) -> None:
    spec = base_spec()
    spec["rate_limit"] = {
        "requests_per_minute": 6000,
        "headers": {"reset_seconds": "X-RateLimit-Reset"},
        "retry_after_header": None,
    }
    run = run_module(build_module(spec), LIVE, flaky([429], {"X-RateLimit-Reset": "11"}))
    assert run.exit_code == 0
    assert 11.0 in no_real_sleep


def test_429_backs_off_then_gives_up_after_5_tries(build_module: Build, no_real_sleep: list[float]) -> None:
    run = run_module(build_module(base_spec()), LIVE, flaky([429] * 5))
    assert run.exit_code == 5 and run.result["error_code"] == "RATE_LIMITED_OUT"
    backoffs = [w for w in no_real_sleep if w >= 1]
    assert [int(w) for w in backoffs] == [1, 2, 4, 8]
    assert len([log for log in run.logs if log["status"] == 429]) == 5


def test_5xx_retries_then_succeeds(build_module: Build) -> None:
    run = run_module(build_module(base_spec()), LIVE, flaky([503, 502]))
    assert run.exit_code == 0 and ids(run) == ALL_IDS


def test_5xx_gives_up_after_3_tries(build_module: Build) -> None:
    run = run_module(build_module(base_spec()), LIVE, flaky([500, 500, 500]))
    assert run.exit_code == 1 and run.result["error_code"] == "SERVER_ERROR"


def test_timeouts_give_up_after_3_tries(build_module: Build) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    run = run_module(build_module(base_spec()), LIVE, mock(handler))
    assert run.exit_code == 7 and run.result["error_code"] == "TIMEOUT"


# --- plain error codes -> exit codes (TRD §6) ------------------------------------------------


@pytest.mark.parametrize(
    ("status", "exit_code", "code"),
    [
        (401, 2, "AUTH_REJECTED"),
        (403, 3, "PERMISSION_OR_SCOPE"),
        (402, 3, "PAID_ONLY"),
        (400, 4, "WRONG_REQUEST"),
        (404, 4, "WRONG_REQUEST"),
        (410, 4, "WRONG_REQUEST"),
    ],
)
def test_status_codes_stop_without_retry(build_module: Build, status: int, exit_code: int, code: str) -> None:
    calls: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status)

    run = run_module(build_module(base_spec()), LIVE, mock(handler))
    assert (run.exit_code, run.result["error_code"]) == (exit_code, code)
    assert len(calls) == 1


def test_wrong_records_path_is_mapping_failed(build_module: Build) -> None:
    run = run_module(build_module(base_spec(records_path="members")), LIVE, flaky([]))
    assert run.exit_code == 4 and run.result["error_code"] == "MAPPING_FAILED"


def test_wrong_id_field_is_mapping_failed(build_module: Build) -> None:
    spec = base_spec()
    spec["streams"]["users"]["field_map"]["external_id"] = "uuid"
    run = run_module(build_module(spec), LIVE, flaky([]))
    assert run.exit_code == 4 and run.result["error_code"] == "MAPPING_FAILED"


def test_duplicate_users_across_pages_are_dropped(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "page_number", "page_param": "page", "start": 1})

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(
            200, json={"data": [USERS[0], USERS[1]] if page == 1 else [USERS[1], USERS[2]] if page == 2 else []}
        )

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 0 and ids(run) == ["1", "2", "3"]


# --- host lock (exit code 8) -------------------------------------------------------------------


def test_next_url_to_another_host_is_blocked(build_module: Build) -> None:
    spec = base_spec(pagination={"type": "next_url", "next_url_path": "next"})
    reached: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        reached.append(request.url.host)
        return httpx.Response(200, json={"data": USERS[:2], "next": "https://evil.example.net/steal"})

    run = run_module(build_module(spec), LIVE, mock(handler))
    assert run.exit_code == 8 and run.result["error_code"] == "HOST_BLOCKED"
    assert reached == ["api.example.com"]  # nothing ever left for the other host


# --- auth ----------------------------------------------------------------------------------


def test_bearer_token_is_sent_and_never_logged(build_module: Build) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Authorization"])
        return httpx.Response(200, json={"data": USERS})

    run = run_module(build_module(base_spec()), LIVE, mock(handler))
    assert seen == ["Bearer tok-secret-123"]
    assert "tok-secret-123" not in run.text()


def test_missing_credentials_are_bad_input(build_module: Build) -> None:
    run = run_module(build_module(base_spec()), {"run_mode": "live", "secrets": {}}, flaky([]))
    assert run.exit_code == 1 and run.result["error_code"] == "BAD_INPUT"


def oauth_spec(client_auth: str, body_format: str) -> dict[str, Any]:
    spec = base_spec()
    spec["app"]["api_host_pattern"] = "{sub}.example.com"
    spec["variables"] = [
        {"name": "sub", "label": "Subdomain", "example": "acme", "required": True, "pattern": "^[a-z0-9-]{1,30}$"}
    ]
    spec["base_url"] = "https://{sub}.example.com/v1"
    spec["auth"] = {
        "type": "oauth_client_credentials",
        "fields": [
            {"name": "client_id", "label": "Client ID", "secret": False},
            {"name": "client_secret", "label": "Client secret", "secret": True},
        ],
        "token_url": "https://{sub}.example.com/oauth/token",
        "grant_type": "client_credentials",
        "client_auth": client_auth,
        "body_format": body_format,
        "scope": "read",
        "extra_params": {},
        "token_path": "access_token",
        "scopes": ["read"],
        "role_required": None,
        "setup_steps": [],
    }
    return spec


@pytest.mark.parametrize(("client_auth", "body_format"), [("body", "json"), ("basic", "form")])
def test_oauth_client_credentials(build_module: Build, client_auth: str, body_format: str) -> None:
    token_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            token_requests.append(request)
            return httpx.Response(200, json={"access_token": "fresh-access-token-9"})
        assert request.headers["Authorization"] == "Bearer fresh-access-token-9"
        return httpx.Response(200, json={"data": USERS})

    payload = {
        "run_mode": "live",
        "secrets": {"client_id": "cid", "client_secret": "csecret-777"},
        "variables": {"sub": "acme"},
    }
    run = run_module(build_module(oauth_spec(client_auth, body_format)), payload, mock(handler))
    assert run.exit_code == 0, run.result
    (req,) = token_requests
    assert req.method == "POST" and req.url.host == "acme.example.com"
    if body_format == "json":
        assert json.loads(req.content) == {
            "grant_type": "client_credentials",
            "scope": "read",
            "client_id": "cid",
            "client_secret": "csecret-777",
        }
    else:
        assert req.headers["Authorization"].startswith("Basic ")
        assert b"client_secret" not in req.content and b"grant_type=client_credentials" in req.content
    assert "fresh-access-token-9" not in run.text() and "csecret-777" not in run.text()


def test_oauth_token_refused_is_auth_rejected(build_module: Build) -> None:
    payload = {"run_mode": "live", "secrets": {"client_id": "a", "client_secret": "b"}, "variables": {"sub": "acme"}}
    run = run_module(build_module(oauth_spec("body", "form")), payload, flaky([401]))
    assert run.exit_code == 2 and run.result["error_code"] == "AUTH_REJECTED"


def test_variable_not_matching_pattern_is_bad_input(build_module: Build) -> None:
    payload = {
        "run_mode": "live",
        "secrets": {"client_id": "a", "client_secret": "b"},
        "variables": {"sub": "evil.com/x"},
    }
    run = run_module(build_module(oauth_spec("body", "form")), payload, flaky([]))
    assert run.exit_code == 1 and run.result["error_code"] == "BAD_INPUT"


# --- usage: partial when only usage is blocked --------------------------------------------------


def usage_spec() -> dict[str, Any]:
    spec = base_spec()
    spec["app"]["tier"] = "T2"
    del spec["streams"]["users"]["field_map"]["last_active_at"]
    spec["streams"]["usage"] = {
        "method": "GET",
        "path": "/events",
        "query": {"since": "{now_minus_days:30}"},
        "records_path": "data",
        "pagination": {"type": "none"},
        "aggregate": {
            "explode_path": None,
            "user_key_path": "user_id",
            "join_on": "external_id",
            "time_path": "at",
            "window_days": 30,
            "metrics": [{"target": "usage_metric_value", "op": "count"}],
        },
    }
    spec["usage_definition"] = {
        "metric_label": "Events (30 days)",
        "active_rule": {"field": "usage_metric_value", "op": "gte", "value": 1},
        "proxy": True,
        "fallback": None,
    }
    return spec


def test_usage_403_gives_partial_with_users(build_module: Build) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events"):
            return httpx.Response(403)
        return httpx.Response(200, json={"data": USERS})

    run = run_module(build_module(usage_spec()), LIVE, mock(handler))
    assert run.exit_code == 0
    assert run.result["status"] == "partial" and run.result["usage_error_code"] == "PERMISSION_OR_SCOPE"
    assert len(run.records) == len(USERS) and not any(r["usage_available"] for r in run.records)


def test_usage_404_is_an_error_for_repair(build_module: Build) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events"):
            return httpx.Response(404)
        return httpx.Response(200, json={"data": USERS})

    run = run_module(build_module(usage_spec()), LIVE, mock(handler))
    assert run.exit_code == 4 and run.result["error_code"] == "WRONG_REQUEST"


def test_users_without_activity_get_zero(build_module: Build) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json={"data": [{"user_id": 1, "at": "2099-01-01T00:00:00Z"}]})
        return httpx.Response(200, json={"data": USERS})

    run = run_module(build_module(usage_spec()), LIVE, mock(handler))
    assert run.exit_code == 0
    assert {r["usage_metric_value"] for r in run.records} == {0}  # the future event doesn't count
    assert all(r["usage_is_proxy"] and r["usage_window_days"] == 30 for r in run.records)
