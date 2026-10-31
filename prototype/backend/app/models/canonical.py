"""The canonical user record (TRD §5). Every connector outputs exactly this."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Status = Literal["active", "suspended", "deactivated", "invited", "unknown"]
RunMode = Literal["live", "replay"]
UsageSource = Literal["app", "sso_fallback"]


class RecordSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant: str
    connector: str
    version: int
    run_id: str
    run_mode: RunMode
    fetched_at: datetime


class CanonicalUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str
    email: str | None = None
    name: str | None = None
    role: str | None = None
    status: Status = "unknown"
    is_admin: bool | None = None
    license_type: str | None = None
    is_billable: bool | None = None
    last_active_at: datetime | None = None
    usage_metric_label: str | None = None
    usage_metric_value: float | None = None
    usage_window_days: int | None = None
    usage_available: bool = False
    usage_is_proxy: bool = False
    usage_source: UsageSource | None = None
    excluded_reason: str | None = None
    source: RecordSource

    @field_validator("external_id", mode="before")
    @classmethod
    def _id_to_text(cls, value: object) -> object:
        # Many APIs use numeric IDs (e.g. Zendesk); the record always stores text.
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value

    @field_validator("external_id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("external_id must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str | None) -> str | None:
        # The join key for the HRIS/SSO cross-check (TRD §11).
        if value is None:
            return None
        value = value.strip().lower()
        return value or None

    @model_validator(mode="after")
    def _usage_consistent(self) -> CanonicalUser:
        if not self.usage_available and self.usage_source is not None:
            raise ValueError("usage_source is set but usage_available is false")
        if self.usage_available and self.usage_source is None:
            raise ValueError("usage_available is true but usage_source is missing")
        return self

    @property
    def billable(self) -> bool:
        """is_billable; else true unless the app says the user is deactivated (or similar)."""
        if self.is_billable is not None:
            return self.is_billable
        return self.status in ("unknown", "active", "invited")
