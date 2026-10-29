"""Flattened draft (what the LLM fills, schemas/draft_spec.schema.json) ↔ full connector spec (TRD §3).

The draft has no method field: every stream and bootstrap call becomes GET here, so a draft can't
ask for a write. Values the draft carries as JSON text (lookup maps, constants) are parsed back.
"""

from __future__ import annotations

import json
import re
from typing import Any

AUTH_EXTRA = {
    "bearer_token": ("bearer_template",),
    "basic": ("basic_username", "basic_password"),
    "api_key_header": ("header_name", "value_template"),
    "oauth_client_credentials": (
        "token_url",
        "grant_type",
        "client_auth",
        "body_format",
        "scope",
        "extra_params",
        "token_path",
    ),
}
PAGINATION_FIELDS = {
    "none": (),
    "cursor": ("request_param", "next_cursor_path", "has_more_path"),
    "next_url": ("next_url_path",),
    "link_header": (),
    "offset_limit": ("offset_param", "limit_param", "limit"),
    "page_number": ("page_param", "start"),
}


def _json_value(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    try:
        return json.loads(text)
    except ValueError:
        return text


def _json_text(value: Any) -> str:
    return json.dumps(value)


def _query(items: list[dict[str, Any]] | None) -> dict[str, str | list[str]]:
    out: dict[str, str | list[str]] = {}
    for item in items or []:
        values = [str(v) for v in item.get("values", [])]
        if values:
            out[item["name"]] = values[0] if len(values) == 1 else values
    return out


def _pagination(p: dict[str, Any]) -> dict[str, Any]:
    kind = p.get("type", "none")
    out: dict[str, Any] = {"type": kind}
    for key in PAGINATION_FIELDS.get(kind, ()):
        if p.get(key) is not None:
            out[key] = p[key]
    return out


def _field_map(entries: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for e in entries:
        kind = e.get("kind")
        if kind == "const":
            out[e["target"]] = {"const": _json_value(e.get("const"))}
        elif kind == "lookup":
            mapping = {m["key"]: _json_value(m["value"]) for m in e.get("map") or []}
            value: dict[str, Any] = {"path": e.get("path"), "map": mapping}
            if e.get("default") is not None:
                value["default"] = _json_value(e["default"])
            out[e["target"]] = value
        elif e.get("path"):
            out[e["target"]] = e["path"]
    return out


def _bare_host(value: Any) -> Any:
    """'https://API.example.com/v2/' → 'api.example.com'. Only tidies the shape; the rule checks still judge it."""
    if not isinstance(value, str):
        return value
    host = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", value.strip())
    host = re.split(r"[/?#]", host, maxsplit=1)[0]
    host = re.sub(r":\d+$", "", host).rstrip(".")
    return re.sub(r"[^{}]+(?=\{|$)", lambda m: m.group(0).lower(), host)  # placeholders keep their case


def draft_to_spec(draft: dict[str, Any]) -> dict[str, Any]:
    auth_in = draft.get("auth", {})
    kind = auth_in.get("type", "bearer_token")
    auth: dict[str, Any] = {
        "type": kind,
        "fields": auth_in.get("fields", []),
        "scopes": auth_in.get("scopes", []),
        "role_required": auth_in.get("role_required"),
        "setup_steps": auth_in.get("setup_steps", []),
    }
    for key in AUTH_EXTRA.get(kind, ()):
        value = auth_in.get(key)
        if key == "extra_params":
            auth[key] = {i["name"]: i["value"] for i in value or []}
        elif key == "scope" or value is not None:
            auth[key] = value

    rate_in = draft.get("rate_limit", {})
    headers = {k: rate_in[f"{k}_header"] for k in ("limit", "remaining", "reset_seconds") if rate_in.get(f"{k}_header")}
    users_in = draft.get("users_stream", {})
    usage_in = draft.get("usage_stream")
    streams: dict[str, Any] = {
        "users": {
            "method": "GET",
            "path": users_in.get("path"),
            "query": _query(users_in.get("query")),
            "records_path": users_in.get("records_path"),
            "pagination": _pagination(users_in.get("pagination", {})),
            "field_map": _field_map(users_in.get("field_map", [])),
        },
        "usage": None,
    }
    if usage_in:
        metrics = []
        for m in usage_in.get("metrics", []):
            metric = {"target": m["target"], "op": m["op"]}
            for key in ("value_path", "label"):
                if m.get(key):
                    metric[key] = m[key]
            metrics.append(metric)
        streams["usage"] = {
            "method": "GET",
            "path": usage_in.get("path"),
            "query": _query(usage_in.get("query")),
            "records_path": usage_in.get("records_path"),
            "pagination": _pagination(usage_in.get("pagination", {})),
            "aggregate": {
                "explode_path": usage_in.get("explode_path"),
                "user_key_path": usage_in.get("user_key_path"),
                "join_on": usage_in.get("join_on"),
                "time_path": usage_in.get("time_path"),
                "window_days": usage_in.get("window_days"),
                "metrics": metrics,
            },
        }
    evidence: dict[str, Any] = {}
    for item in draft.get("evidence", []):
        if item.get("openapi_pointer") is not None:
            evidence[item["field"]] = {"source": "openapi", "pointer": item["openapi_pointer"]}
        elif item.get("url") and item.get("quote"):
            evidence[item["field"]] = {"url": item["url"], "quote": item["quote"]}
    spec: dict[str, Any] = {
        "spec_version": "1.1",
        "origin": "ai",
        "app": {**draft.get("app", {}), "api_host_pattern": _bare_host(draft.get("app", {}).get("api_host_pattern"))},
        "variables": draft.get("variables", []),
        "base_url": draft.get("base_url"),
        "auth": auth,
        "default_headers": {h["name"]: h["value"] for h in draft.get("default_headers", [])},
        "rate_limit": {
            "requests_per_minute": rate_in.get("requests_per_minute") or 60,
            "plan_note": rate_in.get("plan_note"),
            "headers": headers,
            "retry_after_header": rate_in.get("retry_after_header"),
        },
        "bootstrap": [
            {
                "name": b["name"],
                "method": "GET",
                "path": b["path"],
                "query": _query(b.get("query")),
                "extract": {e["var"]: e["path"] for e in b.get("extract", [])},
            }
            for b in draft.get("bootstrap", [])
        ],
        "streams": streams,
        "usage_definition": draft.get("usage_definition", {}),
        "warnings": list(draft.get("warnings", [])),
        "evidence": evidence,
    }
    if not rate_in.get("requests_per_minute"):
        spec["warnings"].append("The docs don't state a rate limit; pacing at 60 requests per minute")
    conflicts = [
        {
            "field": c["field"],
            "values": [{"value": _json_value(v["value"]), "source": v["source"]} for v in c.get("values", [])],
            "chosen": _json_value(c.get("chosen")),
            "reason": c.get("reason", ""),
        }
        for c in draft.get("conflicts", [])
        if len(c.get("values", [])) >= 2
    ]
    if conflicts:
        spec["conflicts"] = conflicts
    return spec


def spec_to_draft(spec: dict[str, Any]) -> dict[str, Any]:
    """The inverse, for tests and the benchmark's 'perfect answer' baseline."""

    def query(q: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"name": k, "values": v if isinstance(v, list) else [v]} for k, v in q.items()]

    def pagination(p: dict[str, Any]) -> dict[str, Any]:
        out = {k: None for f in PAGINATION_FIELDS.values() for k in f}
        out.update(p)
        return out

    def field_map(fm: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for target, value in fm.items():
            if isinstance(value, str):
                out.append({"target": target, "kind": "path", "path": value})
            elif "const" in value:
                out.append({"target": target, "kind": "const", "const": _json_text(value["const"])})
            else:
                out.append(
                    {
                        "target": target,
                        "kind": "lookup",
                        "path": value["path"],
                        "map": [{"key": k, "value": _json_text(v)} for k, v in value["map"].items()],
                        "default": _json_text(value["default"]) if "default" in value else None,
                    }
                )
        return out

    auth = dict(spec["auth"])
    if "extra_params" in auth:
        auth["extra_params"] = [{"name": k, "value": v} for k, v in auth["extra_params"].items()]
    rate = spec["rate_limit"]
    users = spec["streams"]["users"]
    usage = spec["streams"]["usage"]
    draft: dict[str, Any] = {
        "app": spec["app"],
        "variables": spec["variables"],
        "base_url": spec["base_url"],
        "auth": auth,
        "default_headers": [{"name": k, "value": v} for k, v in spec["default_headers"].items()],
        "rate_limit": {
            "requests_per_minute": rate["requests_per_minute"],
            "plan_note": rate.get("plan_note"),
            "limit_header": rate.get("headers", {}).get("limit"),
            "remaining_header": rate.get("headers", {}).get("remaining"),
            "reset_seconds_header": rate.get("headers", {}).get("reset_seconds"),
            "retry_after_header": rate.get("retry_after_header"),
        },
        "bootstrap": [
            {
                "name": b["name"],
                "path": b["path"],
                "query": query(b["query"]),
                "extract": [{"var": k, "path": v} for k, v in b["extract"].items()],
            }
            for b in spec["bootstrap"]
        ],
        "users_stream": {
            "path": users["path"],
            "query": query(users["query"]),
            "records_path": users["records_path"],
            "pagination": pagination(users["pagination"]),
            "field_map": field_map(users["field_map"]),
        },
        "usage_stream": None,
        "usage_definition": spec["usage_definition"],
        "warnings": spec["warnings"],
        "evidence": [
            {"field": k, "url": v.get("url"), "quote": v.get("quote"), "openapi_pointer": v.get("pointer")}
            for k, v in spec.get("evidence", {}).items()
        ],
        "conflicts": [
            {
                "field": c["field"],
                "values": [{"value": _json_text(v["value"]), "source": v["source"]} for v in c["values"]],
                "chosen": _json_text(c["chosen"]),
                "reason": c["reason"],
            }
            for c in spec.get("conflicts", [])
        ],
    }
    if usage:
        agg = usage["aggregate"]
        draft["usage_stream"] = {
            "path": usage["path"],
            "query": query(usage["query"]),
            "records_path": usage["records_path"],
            "pagination": pagination(usage["pagination"]),
            **{k: agg[k] for k in ("explode_path", "user_key_path", "join_on", "time_path", "window_days")},
            "metrics": [{"value_path": None, "label": None, **m} for m in agg["metrics"]],
        }
    return draft
