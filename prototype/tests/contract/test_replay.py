"""Milestone 2 done-criteria: the three example specs, run on replay recordings, give the right users.

The right answer comes from fixtures/replay/<app>/expected.json, built from the fake ground truth by
fixtures/make_demo_data.py, not from the engine's own output.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import REPLAY, example_spec, run_module

COMPARED = (
    "email",
    "name",
    "role",
    "status",
    "is_admin",
    "usage_available",
    "usage_is_proxy",
    "usage_metric_label",
    "usage_metric_value",
    "usage_window_days",
    "last_active_at",
)


def replay(app: str, build_module: Callable[[dict[str, Any]], Path]) -> tuple[Any, dict[str, Any]]:
    module = build_module(example_spec(app))
    payload = {
        "run_mode": "replay",
        "replay_file": str(REPLAY / app / "recording.json"),
        "context": {"tenant": "acme", "run_id": "contract"},
    }
    expected = json.loads((REPLAY / app / "expected.json").read_text())
    return run_module(module, payload), expected


@pytest.mark.parametrize("app", ["calendly", "zendesk", "notion"])
def test_replay_matches_expected_users(app: str, build_module: Callable[[dict[str, Any]], Path]) -> None:
    run, expected = replay(app, build_module)
    assert run.exit_code == 0, run.result
    assert run.result["status"] == "ok"
    got = {r["external_id"]: r for r in run.records}
    assert set(got) == set(expected), "user set differs"
    for external_id, want in expected.items():
        for field in COMPARED:
            if field in want:
                assert got[external_id][field] == want[field], f"{app} {external_id} {field}"
        assert got[external_id]["source"]["run_mode"] == "replay"


def test_calendly_demo_numbers(build_module: Callable[[dict[str, Any]], Path]) -> None:
    """TRD §11: 48 users; 31 active hosts + 2 who left had meetings; nobody else, despite a future meeting."""
    run, _ = replay("calendly", build_module)
    records = run.records
    assert len(records) == 48
    hosts = [r for r in records if r["usage_metric_value"] and r["usage_metric_value"] > 0]
    assert len(hosts) == 33
    assert all(r["email"] == r["email"].lower() for r in records)
    assert run.result["summary"]["pages"] == {"users": 2, "usage": 2}


def test_zendesk_end_users_are_never_requested(build_module: Callable[[dict[str, Any]], Path]) -> None:
    run, _ = replay("zendesk", build_module)
    assert run.exit_code == 0
    assert {r["role"] for r in run.records} == {"admin", "agent"}


def test_notion_drops_bots_and_has_no_usage(build_module: Callable[[dict[str, Any]], Path]) -> None:
    run, _ = replay("notion", build_module)
    assert len(run.records) == 87
    assert not any(r["usage_available"] for r in run.records)


@pytest.mark.parametrize("app", ["calendly", "zendesk", "notion"])
def test_replay_output_has_no_secrets(app: str, build_module: Callable[[dict[str, Any]], Path]) -> None:
    run, _ = replay(app, build_module)
    text = "\n".join(json.dumps(line) for line in run.logs)
    assert "replay-access-token" not in text
    assert "replay-demo" not in text
    assert "@acme.example" not in text.replace("***@acme.example", "")


def test_demo_data_is_reproducible(tmp_path: Path) -> None:
    """The committed fixtures are exactly what the generator makes (no hand edits, no drift)."""
    from fixtures.make_demo_data import build

    build(tmp_path)
    fixtures = REPLAY.parent
    for made in sorted(p for p in tmp_path.rglob("*") if p.is_file()):
        committed = fixtures / made.relative_to(tmp_path)
        assert committed.read_text() == made.read_text(), f"regenerate: python fixtures/make_demo_data.py ({committed})"
