"""Milestone 4 done-criteria: live runs against real accounts; user counts match each admin screen.

Skipped unless the account's env vars are set (prototype/.env or the environment). Runs in the
sandbox: Docker when the images exist, else the subprocess fallback.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import get
from app.services.codegen import render
from app.services.sandbox import docker_available, run_connector
from app.tools.record import LIVE_ENV, live_payload
from runtime import helpers as h
from tests.conftest import example_spec


def configured(app: str) -> bool:
    names: dict[str, Any] = LIVE_ENV[app]
    return all(get(env) for env in [*names["secrets"].values(), *names["variables"].values()])


@pytest.mark.parametrize("app", ["calendly", "zendesk", "notion"])
def test_live_user_count_matches_admin_screen(app: str) -> None:
    if not configured(app):
        pytest.skip(f"{app}: live credentials not set")
    spec = example_spec(app)
    payload = live_payload(app)
    host = h.fill(spec["app"]["api_host_pattern"], payload["variables"], h.utc_now())
    sandbox = "docker" if docker_available() else "subprocess"
    result = run_connector(render(spec, 1), payload, host, mode="test", sandbox=sandbox)
    assert result.exit_code == 0, (result.result, result.blocked_calls)
    expected = get(f"{app.upper()}_EXPECTED_USERS")
    if expected:
        assert len(result.records) == int(expected), "user count differs from the admin screen"
    secrets = [v for v in payload["secrets"].values() if v]
    text = json.dumps(result.lines) + result.stderr
    assert not any(secret in text for secret in secrets)
