from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.canonical import CanonicalUser

SOURCE = {
    "tenant": "acme",
    "connector": "calendly",
    "version": 1,
    "run_id": "run-1",
    "run_mode": "replay",
    "fetched_at": datetime(2026, 10, 29, tzinfo=UTC),
}


def user(**kw: Any) -> CanonicalUser:
    return CanonicalUser.model_validate({"external_id": "u1", "source": SOURCE, **kw})


def test_email_is_lower_cased_and_trimmed() -> None:
    assert user(email="  Jane.Doe@Acme.COM ").email == "jane.doe@acme.com"
    assert user(email="  ").email is None


def test_numeric_id_becomes_text() -> None:
    assert user(external_id=12345).external_id == "12345"


def test_blank_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        user(external_id=" ")


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        user(status="enabled")


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        user(password="x")


def test_usage_flags_must_agree() -> None:
    with pytest.raises(ValidationError):
        user(usage_available=True)
    with pytest.raises(ValidationError):
        user(usage_source="app")
    ok = user(usage_available=True, usage_source="app", usage_metric_value=3, usage_is_proxy=True)
    assert ok.usage_metric_value == 3


@pytest.mark.parametrize(
    ("status", "is_billable", "expected"),
    [("active", None, True), ("invited", None, True), ("suspended", None, False), ("active", False, False)],
)
def test_billable_default(status: str, is_billable: bool | None, expected: bool) -> None:
    assert user(status=status, is_billable=is_billable).billable is expected
