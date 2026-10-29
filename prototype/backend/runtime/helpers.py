"""Generic helpers used by every generated connector (TRD §3, §7).

Placeholders, JMESPath, value lookups, usage aggregation and the active rule.
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import jmespath

from runtime.errors import ConnectorError

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
PARENT = "$parent."
Query = Mapping[str, str | list[str]]


def utc_now() -> datetime:
    return datetime.now(UTC)


def fmt_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def fill(
    template: str,
    values: Mapping[str, str],
    now: datetime,
    secrets: Mapping[str, str] | None = None,
    encode: bool = False,
) -> str:
    """Fill {name}, {secrets.name}, {now} and {now_minus_days:N}. The spec was validated, so names exist."""

    def sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "now":
            value = fmt_time(now)
        elif name.startswith("now_minus_days:"):
            value = fmt_time(now - timedelta(days=int(name.split(":", 1)[1])))
        elif name.startswith("secrets."):
            if secrets is None or name[len("secrets.") :] not in secrets:
                raise ConnectorError("BAD_INPUT", detail=f"missing secret {name[len('secrets.') :]}")
            value = secrets[name[len("secrets.") :]]
        elif name in values:
            value = values[name]
        else:
            raise ConnectorError("BAD_INPUT", detail=f"missing value for {{{name}}}")
        # Values placed inside a URL path are encoded, so a value can never add path segments.
        return quote(value, safe="") if encode else value

    return PLACEHOLDER.sub(sub, template)


def fill_query(query: Query, values: Mapping[str, str], now: datetime) -> list[tuple[str, str]]:
    """Query values are strings or lists; a list is sent as repeated keys (role[]=agent&role[]=admin)."""
    params: list[tuple[str, str]] = []
    for key, value in query.items():
        for item in value if isinstance(value, list) else [value]:
            params.append((key, fill(item, values, now)))
    return params


def search(expression: str, data: Any) -> Any:
    return jmespath.search(expression, data)


def records(expression: str, body: Any) -> list[Any]:
    found = search(expression, body)
    if found is None:
        # Usually a wrong records_path; repairable (exit 4), not an empty org.
        raise ConnectorError("MAPPING_FAILED", detail=f"records_path {expression!r} found nothing")
    if not isinstance(found, list):
        raise ConnectorError("MAPPING_FAILED", detail=f"records_path {expression!r} is not a list")
    return found


def lookup(value: Any, mapping: Mapping[str, Any], default: Any) -> Any:
    """Map keys are strings; other values are turned into JSON text first (true -> "true")."""
    key = value if isinstance(value, str) else json.dumps(value)
    return mapping.get(key, default)


def backoff(attempt: int) -> float:
    """1, 2, 4, 8, 16 seconds, plus jitter."""
    return float(2 ** min(max(attempt - 1, 0), 4)) + random.random()


def aggregate(
    rows: Iterable[Any],
    *,
    explode_path: str | None,
    user_key_path: str,
    time_path: str,
    window_days: int,
    metrics: list[dict[str, str]],
    now: datetime,
) -> dict[str, dict[str, Any]]:
    """Turn usage records into per-user values (TRD §3 `aggregate`).

    Records outside [now - window_days, now] are ignored even if the API returned them,
    which keeps future meetings out of "meetings hosted".
    """
    start = now - timedelta(days=window_days)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        items = search(explode_path, row) if explode_path else [row]
        if not isinstance(items, list):
            continue
        for item in items:
            key = search(user_key_path, item)
            if key is None:
                continue
            raw_time = (
                search(time_path[len(PARENT) :], row) if time_path.startswith(PARENT) else search(time_path, item)
            )
            when = parse_time(raw_time)
            if when is None or not start <= when <= now:
                continue
            values = out.setdefault(str(key), {})
            for metric in metrics:
                target = metric["target"]
                if metric["op"] == "count":
                    values[target] = values.get(target, 0) + 1
                elif metric["op"] == "sum":
                    amount = search(metric["value_path"], item)
                    if isinstance(amount, int | float) and not isinstance(amount, bool):
                        values[target] = values.get(target, 0) + amount
                elif metric["op"] == "max_time":
                    current = parse_time(values.get(target))
                    if current is None or when > current:
                        values[target] = fmt_time(when)
    return out


def active_rule_passes(record: Mapping[str, Any], rule: Mapping[str, Any] | None, now: datetime) -> bool | None:
    """True/False per the spec's active_rule; None when the data to decide isn't there."""
    if rule is None:
        return None
    value = record.get(rule["field"])
    if rule["op"] == "is_true":
        return None if value is None else value is True
    if value is None:
        return None
    if rule["op"] == "gte":
        return isinstance(value, int | float) and value >= rule["value"]
    if rule["op"] == "within_days":
        when = value if isinstance(value, datetime) else parse_time(value)
        if when is None:
            return None
        return now - when <= timedelta(days=rule["value"])
    return None
