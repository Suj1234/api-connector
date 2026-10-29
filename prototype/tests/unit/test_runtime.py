from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from runtime import helpers as h
from runtime.errors import ConnectorError
from runtime.logs import mask_email, redact
from runtime.transport import AllowOnlyHost, HostBlockedError, ReplayTransport

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


# --- placeholders ------------------------------------------------------------------


def test_fill_values_secrets_and_time() -> None:
    assert h.fill("{a}-{secrets.t}", {"a": "x"}, NOW, {"t": "s"}) == "x-s"
    assert h.fill("{now}", {}, NOW) == "2026-10-29T09:00:00Z"
    assert h.fill("{now_minus_days:90}", {}, NOW) == "2026-07-31T09:00:00Z"


def test_fill_encodes_path_values() -> None:
    # A value from an API response can't add path segments or a host.
    assert h.fill("/orgs/{org}", {"org": "../admin?x=1"}, NOW, encode=True) == "/orgs/..%2Fadmin%3Fx%3D1"


def test_fill_missing_value_is_bad_input() -> None:
    with pytest.raises(ConnectorError) as err:
        h.fill("{missing}", {}, NOW)
    assert err.value.code == "BAD_INPUT"


def test_fill_query_repeats_list_keys() -> None:
    assert h.fill_query({"role[]": ["agent", "admin"], "n": "1"}, {}, NOW) == [
        ("role[]", "agent"),
        ("role[]", "admin"),
        ("n", "1"),
    ]


# --- mapping ---------------------------------------------------------------------


def test_lookup_turns_non_strings_into_json_text() -> None:
    mapping = {"true": "suspended", "false": "active"}
    assert h.lookup(True, mapping, "unknown") == "suspended"
    assert h.lookup(False, mapping, "unknown") == "active"
    assert h.lookup(None, mapping, "unknown") == "unknown"


def test_records_path_that_finds_nothing_is_mapping_failed() -> None:
    with pytest.raises(ConnectorError) as err:
        h.records("members", {"data": []})
    assert err.value.code == "MAPPING_FAILED"
    assert h.records("data[?type=='person']", {"data": [{"type": "bot"}]}) == []


# --- aggregate ---------------------------------------------------------------------


def event(start: str, *hosts: str, minutes: int = 30) -> dict[str, object]:
    return {"start_time": start, "minutes": minutes, "hosts": [{"user": u} for u in hosts]}


AGG = {
    "explode_path": "hosts",
    "user_key_path": "user",
    "time_path": "$parent.start_time",
    "window_days": 90,
    "now": NOW,
}


def test_aggregate_counts_hosts_inside_the_window_only() -> None:
    rows = [
        event("2026-10-01T10:00:00Z", "a"),
        event("2026-10-02T10:00:00.000000Z", "a", "b"),
        event("2026-11-02T10:00:00Z", "c"),  # future: ignored
        event("2026-07-01T10:00:00Z", "c"),  # older than 90 days: ignored
    ]
    metrics = [{"target": "usage_metric_value", "op": "count"}, {"target": "last_active_at", "op": "max_time"}]
    out = h.aggregate(rows, metrics=metrics, **AGG)  # type: ignore[arg-type]
    assert out == {
        "a": {"usage_metric_value": 2, "last_active_at": "2026-10-02T10:00:00Z"},
        "b": {"usage_metric_value": 1, "last_active_at": "2026-10-02T10:00:00Z"},
    }


def test_aggregate_sum() -> None:
    rows = [{"start_time": "2026-10-01T10:00:00Z", "user": "a", "minutes": 30}] * 2
    metrics = [{"target": "usage_metric_value", "op": "sum", "value_path": "minutes"}]
    out = h.aggregate(rows, **{**AGG, "explode_path": None, "time_path": "start_time"}, metrics=metrics)  # type: ignore[arg-type]
    assert out == {"a": {"usage_metric_value": 60}}


# --- active_rule -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "rule", "expected"),
    [
        ({"usage_metric_value": 2}, {"field": "usage_metric_value", "op": "gte", "value": 1}, True),
        ({"usage_metric_value": 0}, {"field": "usage_metric_value", "op": "gte", "value": 1}, False),
        (
            {"last_active_at": "2026-10-20T00:00:00Z"},
            {"field": "last_active_at", "op": "within_days", "value": 30},
            True,
        ),
        (
            {"last_active_at": "2026-08-01T00:00:00Z"},
            {"field": "last_active_at", "op": "within_days", "value": 30},
            False,
        ),
        ({"last_active_at": None}, {"field": "last_active_at", "op": "within_days", "value": 30}, None),
        ({"is_billable": True}, {"field": "is_billable", "op": "is_true", "value": None}, True),
        ({}, None, None),
    ],
)
def test_active_rule(record: dict[str, object], rule: dict[str, object] | None, expected: bool | None) -> None:
    assert h.active_rule_passes(record, rule, NOW) is expected


# --- backoff ----------------------------------------------------------------------


def test_backoff_doubles_up_to_16_seconds() -> None:
    assert [int(h.backoff(n)) for n in range(1, 7)] == [1, 2, 4, 8, 16, 16]


# --- redaction --------------------------------------------------------------------


def test_redaction() -> None:
    line = {
        "Authorization": "Bearer abc",
        "api_key": "k",
        "client_secret": "s",
        "path": "/users/jane.doe@acme.example/x",
        "nested": [{"password": "p", "note": "token abcd1234 used"}],
    }
    out = redact(line, secrets=["abcd1234"])
    assert out["Authorization"] == out["api_key"] == out["client_secret"] == "[redacted]"
    assert out["path"] == "/users/j***@acme.example/x"
    assert out["nested"][0] == {"password": "[redacted]", "note": "token [redacted] used"}
    assert mask_email("no email here") == "no email here"


# --- transports -------------------------------------------------------------------


def ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={})


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/x",
        "http://api.example.com/x",
        "https://api.example.com:8443/x",
        "https://user:pw@api.example.com/x",
        "https://api.example.com.evil.com/x",
    ],
)
def test_allow_only_host_blocks_everything_else(url: str) -> None:
    client = httpx.Client(transport=AllowOnlyHost("api.example.com", httpx.MockTransport(ok)))
    with pytest.raises(HostBlockedError):
        client.get(url)


def test_allow_only_host_passes_its_own_host() -> None:
    client = httpx.Client(transport=AllowOnlyHost("api.example.com", httpx.MockTransport(ok)))
    assert client.get("https://API.example.com/x").status_code == 200


def test_replay_matches_query_with_wildcards_and_404s_the_rest() -> None:
    recording = {
        "interactions": [
            {"url": "https://api.example.com/e", "query": {"since": "*", "n": "1"}, "body": {"ok": True}},
        ]
    }
    client = httpx.Client(transport=ReplayTransport(recording))
    assert client.get("https://api.example.com/e", params={"since": "anything", "n": "1"}).json() == {"ok": True}
    assert client.get("https://api.example.com/e", params={"n": "1"}).status_code == 404
    assert client.get("https://api.example.com/other").status_code == 404
