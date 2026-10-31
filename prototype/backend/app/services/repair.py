"""P8 Repair (TRD §8): only for exit codes 4 and 6, as a limited JSON Patch (RFC 6902).

The model sees the spec (no secrets in it), the error code, a masked response shape (keys and
types only) and the relevant docs. It may only patch /streams, /bootstrap, the non-secret parts of
/auth and /default_headers. Tries 1–2 use the draft model, try 3 the escalation model.
"""

from __future__ import annotations

import copy
from typing import Any

import jsonpatch

REPAIRABLE_EXITS = (4, 6)
ALLOWED_PREFIXES = ("/streams/", "/bootstrap", "/default_headers")
ALLOWED_AUTH = (
    "/auth/token_url",
    "/auth/grant_type",
    "/auth/client_auth",
    "/auth/body_format",
    "/auth/scope",
    "/auth/token_path",
    "/auth/header_name",
)
MAX_TRIES = 3

PATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string", "description": "One sentence: what was wrong"},
        "patch": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["add", "replace", "remove"]},
                    "path": {"type": "string"},
                    "value_json": {"type": ["string", "null"], "description": "The new value as JSON text"},
                },
                "required": ["op", "path"],
            },
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"field": {"type": "string"}, "url": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["field", "url", "quote"],
            },
        },
    },
    "required": ["diagnosis", "patch"],
}


class PatchRejectedError(ValueError):
    pass


def allowed(path: str) -> bool:
    return path.startswith(ALLOWED_PREFIXES) or path in ALLOWED_AUTH


def to_operations(answer: dict[str, Any]) -> list[dict[str, Any]]:
    import json

    ops = []
    for item in answer.get("patch", []):
        op: dict[str, Any] = {"op": item["op"], "path": item["path"]}
        if item["op"] != "remove":
            raw = item.get("value_json")
            try:
                op["value"] = json.loads(raw) if isinstance(raw, str) else raw
            except ValueError:
                op["value"] = raw
        ops.append(op)
    return ops


def apply_patch(spec: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    if not operations:
        raise PatchRejectedError("empty patch")
    for op in operations:
        if op.get("op") not in ("add", "replace", "remove") or not allowed(str(op.get("path", ""))):
            raise PatchRejectedError(f"not allowed to change {op.get('path')}")
        if "{secrets." in str(op.get("value", "")):
            raise PatchRejectedError("a patch can't add secret placeholders")
    try:
        patched: dict[str, Any] = jsonpatch.apply_patch(copy.deepcopy(spec), operations)
    except (jsonpatch.JsonPatchException, jsonpatch.JsonPointerException) as error:
        raise PatchRejectedError(str(error)) from error
    return patched


def model_for_try(attempt: int, draft_model: str, escalate_model: str) -> str:
    return escalate_model if attempt >= MAX_TRIES else draft_model
