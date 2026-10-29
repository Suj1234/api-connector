"""TRD §11 demo dataset check: Acme / Calendly in replay mode."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.savings import compute, parse_files
from tests.conftest import PROTOTYPE, REPLAY, example_spec, run_module

ACME = PROTOTYPE / "fixtures" / "acme"
TODAY = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


def records(app: str, build_module: Callable[[dict[str, Any]], Path]) -> list[dict[str, Any]]:
    payload = {"run_mode": "replay", "replay_file": str(REPLAY / app / "recording.json")}
    return run_module(build_module(example_spec(app)), payload).records


def files(app: str) -> Any:
    return parse_files(
        app, (ACME / "hris.csv").read_text(), (ACME / "sso.csv").read_text(), (ACME / "contract.json").read_text()
    )


def test_calendly_demo_numbers_match_trd(build_module: Callable[[dict[str, Any]], Path]) -> None:
    result = compute(
        "Calendly", records("calendly", build_module), example_spec("calendly"), files("Calendly"), None, TODAY
    )
    assert result.users == 48
    assert result.buckets == {
        "excluded": 0,
        "left": 6,
        "not_in_hr": 0,
        "inactive": 11,
        "active": 31,
        "usage_unknown": 0,
    }
    assert (result.seats, result.billable_users, result.never_assigned) == (60, 48, 12)
    assert result.price_per_seat == 240.0
    assert (result.recoverable_seats, result.recoverable_annual) == (29, 6960.0)
    assert (result.renewal_date, result.days_to_renewal) == ("2026-12-26", 58)
    assert (result.sso_assigned, result.mismatch_pct, result.needs_note) == (48, 0.0, False)
    assert result.usage_label == "Meetings hosted (90 days) · proxy"


def test_token_owner_is_excluded_never_inactive(build_module: Callable[[dict[str, Any]], Path]) -> None:
    owner = "diego.moreau@acme.example"  # fixtures/acme/notes.json
    result = compute(
        "Calendly", records("calendly", build_module), example_spec("calendly"), files("Calendly"), owner, TODAY
    )
    assert result.buckets["excluded"] == 1 and result.buckets["active"] == 30


def test_notion_uses_the_sso_fallback(build_module: Callable[[dict[str, Any]], Path]) -> None:
    result = compute("Notion", records("notion", build_module), example_spec("notion"), files("Notion"), None, TODAY)
    assert result.usage_label == "Last login · from SSO, not from the app"
    assert result.buckets["inactive"] > 0 and result.buckets["usage_unknown"] == 0
    assert all("per SSO login" in p["reason"] for p in result.people if p["bucket"] in ("active", "inactive"))


def test_zendesk_service_account_is_not_in_hr(build_module: Callable[[dict[str, Any]], Path]) -> None:
    result = compute(
        "Zendesk", records("zendesk", build_module), example_spec("zendesk"), files("Zendesk"), None, TODAY
    )
    assert result.buckets["not_in_hr"] == 1  # the service account
    # 2 suspended agents aren't billable (35) but SSO still assigns 36: a real gap the admin must explain.
    assert (result.billable_users, result.sso_assigned, result.mismatch_pct, result.needs_note) == (35, 36, 2.8, True)


def test_count_mismatch_needs_a_note(build_module: Callable[[dict[str, Any]], Path]) -> None:
    """SC-09: more than 2% off the SSO-assigned count."""
    users = records("calendly", build_module)[:40]
    result = compute("Calendly", users, example_spec("calendly"), files("Calendly"), None, TODAY)
    assert result.mismatch_pct == round(100 * 8 / 48, 1) and result.needs_note


def test_missing_files_are_reported() -> None:
    result = compute("Calendly", [], example_spec("calendly"), parse_files("Calendly", None, None, None), None, TODAY)
    assert result.missing == ["HRIS", "SSO", "contract"] and result.recoverable_annual is None


def test_users_without_a_status_still_hold_seats(build_module: Callable[[dict[str, Any]], Path]) -> None:
    """An AI-drafted spec may map no status field; that must not make every seat look unassigned."""
    users = [{**u, "status": "unknown"} for u in records("calendly", build_module)]
    result = compute("Calendly", users, example_spec("calendly"), files("Calendly"), None, TODAY)
    assert (result.billable_users, result.never_assigned, result.needs_note) == (48, 12, False)
