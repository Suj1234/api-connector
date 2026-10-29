from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.services.codegen import render
from runner.__main__ import run

PROTOTYPE = Path(__file__).resolve().parents[1]
SPECS = PROTOTYPE / "specs" / "examples"
REPLAY = PROTOTYPE / "fixtures" / "replay"


def example_spec(name: str) -> dict[str, Any]:
    spec: dict[str, Any] = json.loads((SPECS / f"{name}.json").read_text())
    return spec


def base_spec(**streams: Any) -> dict[str, Any]:
    """A small generic T1 spec on api.example.com, for engine behaviour tests."""
    spec: dict[str, Any] = {
        "spec_version": "1.1",
        "origin": "hand_written",
        "app": {
            "name": "Example App",
            "docs_url": "https://docs.example.com",
            "api_host_pattern": "api.example.com",
            "tier": "T1",
            "tier_reason": "Users carry last_seen",
        },
        "variables": [],
        "base_url": "https://api.example.com/v1",
        "auth": {
            "type": "bearer_token",
            "fields": [{"name": "token", "label": "API token", "secret": True}],
            "bearer_template": "{secrets.token}",
            "scopes": [],
            "role_required": None,
            "setup_steps": [],
        },
        "default_headers": {"Accept": "application/json"},
        "rate_limit": {"requests_per_minute": 6000, "headers": {}, "retry_after_header": "Retry-After"},
        "bootstrap": [],
        "streams": {
            "users": {
                "method": "GET",
                "path": "/users",
                "query": {},
                "records_path": "data",
                "pagination": {"type": "none"},
                "field_map": {"external_id": "id", "email": "email", "last_active_at": "last_seen"},
            },
            "usage": None,
        },
        "usage_definition": {
            "metric_label": "Last seen",
            "active_rule": {"field": "last_active_at", "op": "within_days", "value": 30},
            "proxy": False,
            "fallback": None,
        },
        "warnings": [],
    }
    spec["streams"]["users"].update(streams)
    return spec


@pytest.fixture
def build_module(tmp_path: Path) -> Callable[[dict[str, Any]], Path]:
    def build(spec: dict[str, Any]) -> Path:
        path = tmp_path / f"conn_{len(list(tmp_path.glob('conn_*.py')))}.py"
        path.write_text(render(copy.deepcopy(spec), 1))
        return path

    return build


class RunResult:
    def __init__(self, exit_code: int, lines: list[dict[str, Any]]) -> None:
        self.exit_code = exit_code
        self.lines = lines

    @property
    def records(self) -> list[dict[str, Any]]:
        return [line["data"] for line in self.lines if line["type"] == "record"]

    @property
    def result(self) -> dict[str, Any]:
        return next(line for line in self.lines if line["type"] == "result")

    @property
    def logs(self) -> list[dict[str, Any]]:
        return [line for line in self.lines if line["type"] == "log"]

    def text(self) -> str:
        return "\n".join(json.dumps(line, default=str) for line in self.lines)


def run_module(
    module: Path,
    payload: dict[str, Any],
    transport: httpx.BaseTransport | None = None,
    mode: str = "test",
) -> RunResult:
    lines: list[dict[str, Any]] = []
    exit_code = run(module, mode, json.loads(json.dumps(payload)), lines.append, live_transport=transport)
    return RunResult(exit_code, json.loads(json.dumps(lines, default=str)))


def mock(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Live-mode tests never wait for real; the waits are recorded instead."""
    waits: list[float] = []
    monkeypatch.setattr("time.sleep", waits.append)
    return waits
