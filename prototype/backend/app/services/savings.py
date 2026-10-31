"""Cross-check and savings preview (TRD §11, screen F6).

Every app user lands in exactly one bucket, checked in order: excluded, left the company, not in HR
data, inactive, active, usage unknown. The join key is the lower-cased email.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from runtime import helpers as h

SSO_INACTIVE_DAYS = 30
MISMATCH_LIMIT = 0.02
BUCKETS = ("excluded", "left", "not_in_hr", "inactive", "active", "usage_unknown")


@dataclass
class CrossCheckFiles:
    hris: dict[str, dict[str, str]] = field(default_factory=dict)  # email -> row
    sso: dict[str, dict[str, str]] = field(default_factory=dict)  # email -> row for this app
    contract: dict[str, Any] | None = None


@dataclass
class Savings:
    app: str
    users: int
    buckets: dict[str, int]
    billable_users: int
    seats: int | None
    never_assigned: int | None
    price_per_seat: float | None
    recoverable_seats: int | None
    recoverable_annual: float | None
    renewal_date: str | None
    days_to_renewal: int | None
    sso_assigned: int | None
    mismatch_pct: float | None
    needs_note: bool
    usage_label: str
    usage_source: str
    missing: list[str]
    people: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_files(app: str, hris_csv: str | None, sso_csv: str | None, contract_json: str | None) -> CrossCheckFiles:
    files = CrossCheckFiles()
    if hris_csv:
        for row in csv.DictReader(io.StringIO(hris_csv)):
            files.hris[row["email"].strip().lower()] = row
    if sso_csv:
        for row in csv.DictReader(io.StringIO(sso_csv)):
            if row.get("app", "").strip().lower() == app.lower():
                files.sso[row["email"].strip().lower()] = row
    if contract_json:
        contracts = json.loads(contract_json)
        contracts = contracts if isinstance(contracts, list) else [contracts]
        files.contract = next((c for c in contracts if str(c.get("app", "")).lower() == app.lower()), None)
    return files


def bucket_for(
    user: dict[str, Any], files: CrossCheckFiles, rule: dict[str, Any] | None, fallback: str | None,
    token_owner: str | None, today: datetime,
) -> tuple[str, str]:  # fmt: skip
    """Returns (bucket, reason) for one canonical user record."""
    email = (user.get("email") or "").lower()
    if user.get("excluded_reason") or (token_owner and email == token_owner.lower()):
        return "excluded", "The connector's own account; never counted as inactive"
    hr = files.hris.get(email) if email else None
    if files.hris:
        if hr and hr.get("employment_status") == "terminated":
            return (
                "left",
                f"Left the company{' on ' + hr['termination_date'] if hr.get('termination_date') else ''} (HRIS)",
            )
        if hr is None:
            return "not_in_hr", "Not in HR data (contractor or shared mailbox); not counted as recoverable"
    if user.get("usage_available"):
        verdict = h.active_rule_passes(user, rule, today)
        if verdict is True:
            return "active", "Active per the app"
        if verdict is False:
            return "inactive", "Inactive per the app"
    if fallback == "sso_last_login" and files.sso:
        sso = files.sso.get(email)
        last = h.parse_time(sso.get("last_login_at")) if sso else None
        if last is None or (today - last).days > SSO_INACTIVE_DAYS:
            return "inactive", "No SSO login in 30 days (per SSO login)"
        return "active", "Logged in through SSO in the last 30 days (per SSO login)"
    return "usage_unknown", "No usage data and no fallback"


def compute(
    app: str,
    users: list[dict[str, Any]],
    spec: dict[str, Any],
    files: CrossCheckFiles,
    token_owner: str | None,
    today: datetime,
) -> Savings:
    usage_def = spec["usage_definition"]
    rule, fallback = usage_def.get("active_rule"), usage_def.get("fallback")
    counts = dict.fromkeys(BUCKETS, 0)
    people = []
    for user in users:
        bucket, reason = bucket_for(user, files, rule, fallback, token_owner, today)
        counts[bucket] += 1
        people.append(
            {
                "name": user.get("name"),
                "email": user.get("email"),
                "bucket": bucket,
                "reason": reason,
                "usage_metric_value": user.get("usage_metric_value"),
                "last_active_at": user.get("last_active_at"),
            }
        )
    billable = sum(1 for u in users if _billable(u))
    missing = [
        name
        for name, present in (("HRIS", files.hris), ("SSO", files.sso), ("contract", files.contract))
        if not present
    ]
    seats = int(files.contract["seats"]) if files.contract else None
    cost = float(files.contract["annual_cost"]) if files.contract else None
    never_assigned = max(0, seats - billable) if seats is not None else None
    price = round(cost / seats, 2) if cost is not None and seats else None
    recoverable = counts["left"] + counts["inactive"] + (never_assigned or 0) if seats is not None else None
    renewal = files.contract.get("renewal_date") if files.contract else None
    days = (date.fromisoformat(renewal) - today.date()).days if renewal else None
    assigned = (
        sum(1 for row in files.sso.values() if str(row.get("assigned", "")).lower() == "true") if files.sso else None
    )
    mismatch = abs(billable - assigned) / assigned if assigned else None
    if usage_def.get("metric_label") and spec["app"]["tier"] != "T3":
        label = usage_def["metric_label"] + (" · proxy" if usage_def.get("proxy") else "")
        source = "app"
    elif fallback == "sso_last_login":
        label, source = "Last login · from SSO, not from the app", "sso_fallback"
    else:
        label, source = "No usage data", "none"
    return Savings(
        app=app,
        users=len(users),
        buckets=counts,
        billable_users=billable,
        seats=seats,
        never_assigned=never_assigned,
        price_per_seat=price,
        recoverable_seats=recoverable,
        recoverable_annual=round(recoverable * price, 2) if recoverable is not None and price is not None else None,
        renewal_date=renewal,
        days_to_renewal=days,
        sso_assigned=assigned,
        mismatch_pct=round(100 * mismatch, 1) if mismatch is not None else None,
        needs_note=mismatch is not None and mismatch > MISMATCH_LIMIT,
        usage_label=label,
        usage_source=source,
        missing=missing,
        people=people,
    )


def _nice_date(value: str | None) -> str | None:
    """DESIGN.md §7: "26 Dec 2026"."""
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        return f"{parsed.day} {parsed.strftime('%b %Y')}"
    except ValueError:
        return value


def _billable(user: dict[str, Any]) -> bool:
    if user.get("is_billable") is not None:
        return bool(user["is_billable"])
    # A member the admin API lists holds a seat unless the API says otherwise; an unknown status
    # (the connector has no status field) must not make every seat look unassigned.
    return user.get("status") in (None, "unknown", "active", "invited")
