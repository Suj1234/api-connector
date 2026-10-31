"""Runner entry point (TRD §6).

    python -m runner --module connectors/<file>.py --mode test|full  < input.json

stdin: {"secrets", "variables", "run_mode", "limits", "context", "replay_file"}. Nothing secret
comes from env vars or files. stdout: JSON lines (progress, log, record, result). Exit codes per TRD §6.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import ssl
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, TextIO

import httpx
from pydantic import ValidationError

from app.models.canonical import CanonicalUser
from runtime import helpers as h
from runtime.errors import EXIT_OK, EXIT_OTHER, PARTIAL_OK_USAGE_CODES, ConnectorError
from runtime.logs import RunLogger
from runtime.transport import AllowOnlyHost, ReplayTransport, load_recording

REPAIRABLE_CODES = {"WRONG_REQUEST", "MAPPING_FAILED", "PAGINATION_LOOP", "CURSOR_EXPIRED"}
MAPPING_FAILURE_LIMIT = 0.2  # TRD §7: more than 20% of records missing a required field
REPLAY_SECRET = "replay-demo"
DEFAULT_LIMITS: dict[str, dict[str, int | None]] = {
    "test": {"users_pages": 50, "usage_pages": 10, "timeout_s": 120},
    "full": {"users_pages": None, "usage_pages": None, "timeout_s": 1800},
}

Emit = Callable[[dict[str, Any]], None]


def load_module(path: str | Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(
    module_path: str | Path,
    mode: str,
    payload: dict[str, Any],
    emit: Emit,
    live_transport: httpx.BaseTransport | None = None,
) -> int:
    """live_transport replaces the network in tests; the AllowOnlyHost wrapper always stays."""
    module = load_module(module_path)
    context = dict(payload.get("context", {}))
    context.setdefault("connector", module.SLUG)
    context.setdefault("version", module.VERSION)
    run_mode = payload.get("run_mode", "live")
    context["run_mode"] = run_mode
    secrets = {k: str(v) for k, v in payload.get("secrets", {}).items()}
    log = RunLogger(emit, context, secrets.values())
    state = _RunState(mode)
    client: Any = None

    try:
        client = _make_client(module, mode, payload, secrets, log, live_transport)
        state.now = client.now
        _step(log, "login", client.login)
        users = _step(log, "users", lambda: _users(module, client, state))
        usage = _usage(module, client, users, log, state)
        log.progress("map", "start")
        records = _canonical(module, users, usage, state, context, client.now)
        for record in records:
            emit({"type": "record", "data": record.model_dump(mode="json")})
        log.progress("map", "ok", f"{len(records)} users")
        state.pages = client.pages
        state.warnings += client.warnings
    except ConnectorError as error:
        state.status = "error"
        state.error_code = error.code
        if client is not None:
            state.pages = client.pages
            if error.code in REPAIRABLE_CODES and client.last_shape is not None:
                emit({"type": "shape", "error_code": error.code, "shape": client.last_shape})
        _result(emit, state)
        return error.exit_code
    except Exception as error:  # noqa: BLE001 - never leak a traceback with values to stdout
        state.status = "error"
        state.error_code = "INTERNAL"
        print(f"runner: {type(error).__name__}", file=sys.stderr)
        _result(emit, state)
        return EXIT_OTHER
    _result(emit, state)
    return EXIT_OK


class _RunState:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.status = "ok"
        self.error_code: str | None = None
        self.usage_error_code: str | None = None
        self.usage_ran = False
        self.users = 0
        self.pages: dict[str, int] = {"users": 0, "usage": 0}
        self.warnings: list[str] = []
        self.now: datetime | None = None


def _make_client(
    module: ModuleType,
    mode: str,
    payload: dict[str, Any],
    secrets: dict[str, str],
    log: RunLogger,
    live_transport: httpx.BaseTransport | None,
) -> Any:
    variables = {k: str(v) for k, v in payload.get("variables", {}).items()}

    run_mode = payload.get("run_mode", "live")
    sleep: Callable[[float], None]
    if run_mode == "replay":
        # Demo data: recorded responses, fake people. No secret is needed or sent anywhere.
        recording = load_recording(payload["replay_file"])
        for name in module.AUTH_FIELDS:
            secrets.setdefault(name, REPLAY_SECRET)
        inner: httpx.BaseTransport = ReplayTransport(recording)
        variables = {**recording.get("variables", {}), **variables}
        now = h.parse_time(recording["recorded_at"]) or h.utc_now()

        sleep = _no_wait

    else:
        missing = [name for name in module.AUTH_FIELDS if not secrets.get(name)]
        if missing:
            raise ConnectorError("BAD_INPUT", detail=f"missing credentials: {', '.join(missing)}")
        inner = live_transport or _network_transport()
        now = h.utc_now()
        sleep = time.sleep

    for name, pattern in module.VARIABLE_PATTERNS.items():
        if name not in variables or not re.fullmatch(pattern, variables[name]):
            raise ConnectorError("BAD_INPUT", detail=f"variable {name} is missing or doesn't match its pattern")
    host = h.fill(module.HOST_PATTERN, variables, now)
    limits = {**DEFAULT_LIMITS[mode], **payload.get("limits", {})}
    transport = AllowOnlyHost(host, inner)
    return module.Client(secrets, variables, transport, log, limits, now, sleep)


def _network_transport() -> httpx.BaseTransport:
    """The real network. Inside the Docker sandbox HTTPS_PROXY is the per-run egress proxy."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
    ca_file = os.environ.get("SSL_CERT_FILE")
    verify: ssl.SSLContext | bool = ssl.create_default_context(cafile=ca_file) if ca_file else True
    return httpx.HTTPTransport(proxy=proxy, verify=verify)


def _no_wait(_: float) -> None:
    """Replay mode never waits: there is no real server to be polite to."""


def _step(log: RunLogger, step: str, action: Callable[[], Any]) -> Any:
    log.progress(step, "start")
    try:
        value = action()
    except ConnectorError as error:
        log.progress(step, "fail", error.code)
        raise
    log.progress(step, "ok", f"{len(value)} users" if isinstance(value, list) else "")
    return value


def _users(module: ModuleType, client: Any, state: _RunState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = module.get_users(client)
    unique: dict[str, dict[str, Any]] = {}
    missing = 0
    for row in rows:
        external_id = row.get("external_id")
        if external_id is None or external_id == "":
            missing += 1
            continue
        unique.setdefault(str(external_id), row)  # duplicates across pages are dropped
    if not rows:
        raise ConnectorError("MAPPING_FAILED", detail="no users found")
    if missing / len(rows) > MAPPING_FAILURE_LIMIT:
        raise ConnectorError("MAPPING_FAILED", detail=f"{missing} of {len(rows)} users have no id")
    state.users = len(unique)
    return list(unique.values())


def _usage(
    module: ModuleType, client: Any, users: list[dict[str, Any]], log: RunLogger, state: _RunState
) -> dict[str, dict[str, Any]]:
    if not module.META["has_usage_stream"]:
        return {}
    log.progress("usage", "start")
    try:
        usage: dict[str, dict[str, Any]] = module.get_usage(client, users)
    except ConnectorError as error:
        log.progress("usage", "fail", error.code)
        if error.code not in PARTIAL_OK_USAGE_CODES:
            raise
        # Users worked, usage is blocked by role, scope or plan: "partial" (TRD §6).
        state.status = "partial"
        state.usage_error_code = error.code
        return {}
    state.usage_ran = True
    log.progress("usage", "ok", f"{len(usage)} users with activity")
    return usage


def _canonical(
    module: ModuleType,
    users: list[dict[str, Any]],
    usage: dict[str, dict[str, Any]],
    state: _RunState,
    context: dict[str, Any],
    now: datetime,
) -> list[CanonicalUser]:
    meta = module.META
    usage_def = meta["usage_definition"]
    source = {
        "tenant": context.get("tenant", "unknown"),
        "connector": context["connector"],
        "version": context["version"],
        "run_id": context.get("run_id", "local"),
        "run_mode": context["run_mode"],
        "fetched_at": now,
    }
    records: list[CanonicalUser] = []
    failed = 0
    for row in users:
        data = {k: v for k, v in row.items() if v is not None}
        if meta["has_usage_stream"] and state.usage_ran:
            key = row.get(meta["join_on"])
            key = key.lower() if meta["join_on"] == "email" and isinstance(key, str) else key
            values = usage.get(str(key), {})
            data["usage_metric_value"] = values.get("usage_metric_value", 0)
            if values.get("last_active_at"):
                data["last_active_at"] = values["last_active_at"]
            data["usage_window_days"] = meta["window_days"]
            data.update(usage_available=True, usage_source="app")
        elif not meta["has_usage_stream"] and meta["has_last_active"]:
            data.update(usage_available=True, usage_source="app")
        if data.get("usage_available"):
            data["usage_metric_label"] = usage_def["metric_label"]
            data["usage_is_proxy"] = bool(usage_def["proxy"])
        try:
            records.append(CanonicalUser.model_validate({**data, "source": source}))
        except ValidationError:
            failed += 1
    if users and failed / len(users) > MAPPING_FAILURE_LIMIT:
        raise ConnectorError("MAPPING_FAILED", detail=f"{failed} of {len(users)} users didn't fit the user record")
    if failed:
        state.warnings.append(f"{failed}_users_skipped")
    return records


def _result(emit: Emit, state: _RunState) -> None:
    emit(
        {
            "type": "result",
            "status": state.status,
            "error_code": state.error_code,
            "usage_error_code": state.usage_error_code,
            "summary": {
                "users": state.users,
                "usage_sampled": state.mode == "test" and state.usage_ran,
                "pages": state.pages,
                "api_total": None,
                "warnings": state.warnings,
            },
        }
    )


def main(argv: list[str] | None = None, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="runner")
    parser.add_argument("--module", required=True)
    parser.add_argument("--mode", choices=["test", "full"], default="test")
    args = parser.parse_args(argv)
    payload = json.loads(stdin.read() or "{}")

    def emit(line: dict[str, Any]) -> None:
        stdout.write(json.dumps(line, default=str) + "\n")
        stdout.flush()

    return run(args.module, args.mode, payload, emit)


if __name__ == "__main__":
    sys.exit(main())
