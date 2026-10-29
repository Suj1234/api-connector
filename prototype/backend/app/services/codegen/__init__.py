"""P6 Codegen (TRD §8): connector spec → Python module, then ruff + mypy --strict.

The AI never writes code. It fills the spec; this module renders the same templates for every app.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.spec_validator import validate_spec

TEMPLATES = Path(__file__).resolve().parent / "templates"
PROTOTYPE = Path(__file__).resolve().parents[4]
BACKEND = PROTOTYPE / "backend"
PYPROJECT = PROTOTYPE / "pyproject.toml"


class SpecRejectedError(ValueError):
    pass


@dataclass(frozen=True)
class CodeCheck:
    ok: bool
    ruff: str
    mypy: str


def one_line(text: Any) -> str:
    """Spec text placed in a comment or docstring can't add lines or close the docstring."""
    cleaned = re.sub(r"[\x00-\x1f\x7f  ]", " ", str(text))
    return cleaned.replace("\\", "/").replace('"""', "'''")


def slug_for(app_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", app_name.lower()).strip("_") or "app"


def module_name(spec: dict[str, Any], version: int) -> str:
    return f"{slug_for(spec['app']['name'])}_v{version}"


def render(spec: dict[str, Any], version: int = 1) -> str:
    result = validate_spec(spec)
    if not result.ok:
        raise SpecRejectedError(f"{result.error_code}: {result.issues[0].pointer} {result.issues[0].message}")
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,  # renders Python, not HTML; values go through |py
    )
    env.filters["py"] = repr
    env.filters["oneline"] = one_line
    code = env.get_template("connector.py.j2").render(**_context(spec, version))
    return format_code(code)


def format_code(code: str) -> str:
    done = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--config", str(PYPROJECT), "-"],
        input=code,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"ruff format failed: {done.stderr.strip()}")
    return done.stdout


def check_code(code: str, name: str = "connector") -> CodeCheck:
    """ruff + mypy --strict on one generated module (TRD §8 P6)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{name}.py"
        path.write_text(code)
        ruff = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--config", str(PYPROJECT), "--no-cache", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        mypy = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--strict",
                "--config-file",
                str(PYPROJECT),
                "--cache-dir",
                str(Path(tmp) / ".mypy_cache"),
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "MYPYPATH": str(BACKEND)},
        )
    return CodeCheck(ruff.returncode == 0 and mypy.returncode == 0, ruff.stdout.strip(), mypy.stdout.strip())


def _context(spec: dict[str, Any], version: int) -> dict[str, Any]:
    app = spec["app"]
    streams = spec["streams"]
    usage = streams.get("usage")
    usage_def = spec["usage_definition"]
    field_map = streams["users"]["field_map"]
    rate = spec["rate_limit"]

    stream_ctx = [{"name": "users", **streams["users"]}]
    if usage:
        stream_ctx.append({"name": "usage", **usage})

    meta = {
        "tier": app["tier"],
        "usage_definition": usage_def,
        "has_usage_stream": usage is not None,
        "has_last_active": "last_active_at" in field_map,
        "join_on": usage["aggregate"]["join_on"] if usage else None,
        "window_days": usage["aggregate"]["window_days"] if usage else None,
    }
    return {
        "app_name": app["name"],
        "slug": slug_for(app["name"]),
        "version": version,
        "summary_lines": _summary(spec),
        "host_pattern": app["api_host_pattern"],
        "base_url": spec["base_url"],
        "variable_patterns": {v["name"]: v["pattern"] for v in spec["variables"]},
        "auth_fields": [f["name"] for f in spec["auth"]["fields"]],
        "default_headers": spec["default_headers"],
        "meta": meta,
        "rpm": rate["requests_per_minute"],
        "retry_after_header": rate.get("retry_after_header"),
        "reset_seconds_header": rate.get("headers", {}).get("reset_seconds"),
        "auth": spec["auth"],
        "bootstrap": spec["bootstrap"],
        "streams": stream_ctx,
        "field_map": [_field(target, value) for target, value in field_map.items()],
        "usage": usage,
        "usage_comment": _usage_comment(spec),
    }


def _field(target: str, value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"target": target, "kind": "path", "path": value}
    if "const" in value:
        return {"target": target, "kind": "const", "const": value["const"]}
    return {
        "target": target,
        "kind": "lookup",
        "path": value["path"],
        "map": value["map"],
        "default": value.get("default"),
    }


def _summary(spec: dict[str, Any]) -> list[str]:
    app = spec["app"]
    label = spec["usage_definition"]["metric_label"] or "none in the API"
    lines = [f"Host: {app['api_host_pattern']} (read-only GET calls; the transport blocks every other host)."]
    lines += textwrap.wrap(f"Tier {app['tier']}: {app['tier_reason']}", width=95)
    lines.append(f"Usage: {label}{' (proxy)' if spec['usage_definition']['proxy'] else ''}.")
    return [one_line(line) for line in lines]


def _usage_comment(spec: dict[str, Any]) -> str:
    usage = spec["streams"].get("usage")
    usage_def = spec["usage_definition"]
    if usage:
        agg = usage["aggregate"]
        proxy = ", a proxy" if usage_def["proxy"] else ""
        return f"{usage_def['metric_label']} per user from {usage['path']}, last {agg['window_days']} days{proxy}."
    if "last_active_at" in spec["streams"]["users"]["field_map"]:
        return "comes from last_active_at on each user record; no separate usage calls."
    if usage_def.get("fallback") == "sso_last_login":
        return "not in this app's API; the platform falls back to SSO last login, labelled as such."
    return "not available from this app's API."


EXAMPLES = PROTOTYPE / "connectors" / "examples"


def write_examples() -> list[Path]:
    """Render the hand-written example specs into connectors/examples/ (committed, for reading)."""
    import json

    EXAMPLES.mkdir(parents=True, exist_ok=True)
    written = []
    for spec_file in sorted((PROTOTYPE / "specs" / "examples").glob("*.json")):
        spec = json.loads(spec_file.read_text())
        path = EXAMPLES / f"{module_name(spec, 1)}.py"
        path.write_text(render(spec, 1))
        written.append(path)
    return written
