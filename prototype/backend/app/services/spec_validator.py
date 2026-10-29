"""Connector spec validation (TRD §3): JSON Schema + the P5 rules.

Two layers, reported separately:
- SCHEMA_INVALID: the spec doesn't match connector_spec.schema.json.
- RULES_REJECTED: the spec asks for something we never allow (a non-GET call,
  another host, a secret in a URL, an unknown placeholder, a loose variable pattern).

The rules run even when the schema fails, and never trust the spec's shape,
so a malformed spec can't skip them. Nothing here is app-specific.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import jmespath
import jsonschema
from jmespath.exceptions import JMESPathError

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"

SCHEMA_INVALID = "SCHEMA_INVALID"
RULES_REJECTED = "RULES_REJECTED"

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
NAME = r"[a-z_][a-z0-9_]*"
VAR_REF = re.compile(rf"^{NAME}$")
SECRET_REF = re.compile(rf"^secrets\.({NAME})$")
TIME_REF = re.compile(r"^(now|now_minus_days:\d{1,4})$")
HOST_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")

# A variable that fills a host or a path must not be able to change where the call goes.
UNSAFE_VALUES = ("a.b", "a/b", "a:b", "a@b", "a?b", "a#b", "a%2fb", "a b", "a\\b", "")
MAX_QUOTE_WORDS = 25


@dataclass(frozen=True)
class Issue:
    code: str
    pointer: str
    message: str


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def error_code(self) -> str | None:
        """RULES_REJECTED wins: a forbidden spec is discarded, not repaired."""
        codes = {i.code for i in self.issues}
        if RULES_REJECTED in codes:
            return RULES_REJECTED
        if SCHEMA_INVALID in codes:
            return SCHEMA_INVALID
        return None


@cache
def load_schema(name: str = "connector_spec.schema.json") -> dict[str, Any]:
    with open(SCHEMA_DIR / name, encoding="utf-8") as f:
        schema: dict[str, Any] = json.load(f)
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def validate_spec(spec: Any) -> ValidationResult:
    result = ValidationResult()
    result.issues.extend(_schema_issues(spec))
    if isinstance(spec, dict):
        result.issues.extend(_RuleChecker(spec).run())
    return result


def _schema_issues(spec: Any) -> list[Issue]:
    validator = jsonschema.Draft202012Validator(load_schema())
    issues = []
    for err in sorted(validator.iter_errors(spec), key=lambda e: list(e.absolute_path)):
        pointer = "".join(f"/{p}" for p in err.absolute_path)
        issues.append(Issue(SCHEMA_INVALID, pointer or "/", err.message))
    return issues


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class _RuleChecker:
    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self.issues: list[Issue] = []
        self.auth = _dict(spec.get("auth"))
        self.variables = {
            v["name"]: v for v in _list(spec.get("variables")) if isinstance(v, dict) and isinstance(v.get("name"), str)
        }
        self.secret_fields = {
            f["name"] for f in _list(self.auth.get("fields")) if isinstance(f, dict) and isinstance(f.get("name"), str)
        }

    def reject(self, pointer: str, message: str) -> None:
        self.issues.append(Issue(RULES_REJECTED, pointer, message))

    def run(self) -> list[Issue]:
        self.check_variables()
        self.check_host()
        self.check_methods()
        self.check_placeholders()
        self.check_jmespath()
        self.check_evidence()
        return self.issues

    # --- variables -------------------------------------------------------

    def check_variables(self) -> None:
        for i, var in enumerate(_list(self.spec.get("variables"))):
            if not isinstance(var, dict):
                continue
            pointer = f"/variables/{i}/pattern"
            regex = self._compile_pattern(var.get("pattern"), pointer)
            if regex is None:
                continue
            example = var.get("example")
            if isinstance(example, str) and not regex.fullmatch(example):
                self.reject(f"/variables/{i}/example", "Example doesn't match the variable's pattern")

    def _compile_pattern(self, pattern: Any, pointer: str) -> re.Pattern[str] | None:
        if not isinstance(pattern, str) or not pattern.startswith("^") or not pattern.endswith("$"):
            self.reject(pointer, "Variable pattern must be anchored with ^ and $")
            return None
        try:
            return re.compile(pattern)
        except re.error as e:
            self.reject(pointer, f"Variable pattern is not a valid regex: {e}")
            return None

    def _require_safe_variable(self, name: str, pointer: str) -> None:
        """A variable used in a host or path must not be able to redirect the call."""
        var = self.variables.get(name)
        if var is None:
            return  # unknown names are reported by check_placeholders
        regex = self._compile_pattern(var.get("pattern"), pointer)
        if regex is None:
            return
        loose = [v for v in UNSAFE_VALUES if regex.fullmatch(v)]
        if loose:
            self.reject(pointer, f"Variable '{name}' is used in a URL, but its pattern allows {loose[0]!r}")

    # --- host ------------------------------------------------------------

    def check_host(self) -> None:
        app = _dict(self.spec.get("app"))
        pattern = app.get("api_host_pattern")
        if not isinstance(pattern, str):
            return
        if not self._host_pattern_ok(pattern):
            return
        self._check_url(self.spec.get("base_url"), "/base_url", pattern)
        if self.auth.get("type") == "oauth_client_credentials":
            self._check_url(self.auth.get("token_url"), "/auth/token_url", pattern)

    def _host_pattern_ok(self, pattern: str) -> bool:
        pointer = "/app/api_host_pattern"
        if pattern != pattern.lower():
            self.reject(pointer, "Host must be lower-case")
            return False
        literal = PLACEHOLDER.sub("x", pattern)
        try:
            ipaddress.ip_address(literal.strip("[]"))
            self.reject(pointer, "Host must be a domain name, not an IP address")
            return False
        except ValueError:
            pass
        labels = pattern.split(".")
        # Placeholders may only fill the left-most label, and the rest must be a fixed domain,
        # so a variable can pick the tenant's subdomain but never the domain itself.
        fixed = labels[1:] if PLACEHOLDER.search(labels[0]) else labels
        if any(PLACEHOLDER.search(label) for label in fixed):
            self.reject(pointer, "Placeholders are only allowed in the left-most part of the host")
            return False
        if len(fixed) < 2 or not all(HOST_LABEL.match(label) for label in fixed):
            self.reject(pointer, f"Host must end in a fixed domain such as example.com, not '{pattern}'")
            return False
        if PLACEHOLDER.search(labels[0]):
            if PLACEHOLDER.fullmatch(labels[0]) is None:
                self.reject(pointer, "A host placeholder must be the whole left-most label")
                return False
            name = labels[0][1:-1]
            if name not in self.variables:
                self.reject(pointer, f"Host placeholder '{{{name}}}' is not a declared variable")
                return False
            self._require_safe_variable(name, pointer)
        return True

    def _check_url(self, url: Any, pointer: str, host_pattern: str) -> None:
        if not isinstance(url, str):
            return
        if not url.startswith("https://"):
            self.reject(pointer, "URL must use https://")
            return
        rest = url[len("https://") :]
        host = rest.split("/", 1)[0]
        if host != host_pattern:
            self.reject(pointer, f"URL host '{host}' is not the app's host '{host_pattern}'")
        if "?" in rest or "#" in rest:
            self.reject(pointer, "URL must not carry a query string or fragment")
        path = rest[len(host) :]
        self._check_url_path(path, pointer, allow_empty=True)

    def _check_url_path(self, path: Any, pointer: str, allow_empty: bool = False) -> None:
        if not isinstance(path, str):
            return
        if not path and allow_empty:
            return
        if not path.startswith("/") or path.startswith("//"):
            self.reject(pointer, "Path must start with a single /")
        if "://" in path or "@" in path or "\\" in path:
            self.reject(pointer, "Path must not contain a URL, '@' or '\\'")
        if any(seg in ("..", ".") for seg in path.split("/")):
            self.reject(pointer, "Path must not contain '.' or '..' segments")
        for name in PLACEHOLDER.findall(path):
            if VAR_REF.match(name):
                self._require_safe_variable(name, pointer)

    # --- read-only -------------------------------------------------------

    def check_methods(self) -> None:
        streams = _dict(self.spec.get("streams"))
        calls: list[tuple[str, Any]] = [
            (f"/streams/{name}", streams.get(name)) for name in ("users", "usage") if streams.get(name) is not None
        ]
        calls += [(f"/bootstrap/{i}", step) for i, step in enumerate(_list(self.spec.get("bootstrap")))]
        for pointer, call in calls:
            call = _dict(call)
            if call.get("method") != "GET":
                self.reject(f"{pointer}/method", f"Only GET is allowed here, not {call.get('method')!r}")
            self._check_url_path(call.get("path"), f"{pointer}/path")

    # --- placeholders and secrets ------------------------------------------

    def check_placeholders(self) -> None:
        known = set(self.variables)
        for i, step in enumerate(_list(self.spec.get("bootstrap"))):
            step = _dict(step)
            self._scan(step.get("path"), f"/bootstrap/{i}/path", known, secrets_ok=False)
            self._scan(step.get("query"), f"/bootstrap/{i}/query", known, secrets_ok=False)
            # A step's extracts are only available to the steps after it.
            known |= {k for k in _dict(step.get("extract")) if isinstance(k, str)}

        self._scan(self.spec.get("base_url"), "/base_url", set(self.variables), secrets_ok=False)
        self._scan(self.spec.get("default_headers"), "/default_headers", known, secrets_ok=False)
        streams = _dict(self.spec.get("streams"))
        for name in ("users", "usage"):
            stream = _dict(streams.get(name))
            self._scan(stream.get("path"), f"/streams/{name}/path", known, secrets_ok=False)
            self._scan(stream.get("query"), f"/streams/{name}/query", known, secrets_ok=False)

        for key in ("bearer_template", "basic_username", "basic_password", "header_name", "value_template"):
            self._scan(self.auth.get(key), f"/auth/{key}", set(self.variables), secrets_ok=True)
        self._scan(self.auth.get("extra_params"), "/auth/extra_params", set(self.variables), secrets_ok=True)
        self._scan(self.auth.get("token_url"), "/auth/token_url", set(self.variables), secrets_ok=False)
        self._scan(self.auth.get("scope"), "/auth/scope", set(), secrets_ok=False)

        self._find_stray_secrets(self.spec, "")

    def _scan(self, value: Any, pointer: str, known: set[str], secrets_ok: bool) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                self._scan(k, pointer, known, secrets_ok)
                self._scan(v, f"{pointer}/{k}", known, secrets_ok)
            return
        if isinstance(value, list):
            for i, v in enumerate(value):
                self._scan(v, f"{pointer}/{i}", known, secrets_ok)
            return
        if not isinstance(value, str):
            return
        for name in PLACEHOLDER.findall(value):
            secret = SECRET_REF.match(name)
            if secret:
                if not secrets_ok:
                    self.reject(pointer, f"Secret '{{{name}}}' is not allowed here; secrets only go in auth")
                elif secret.group(1) not in self.secret_fields:
                    self.reject(pointer, f"'{{{name}}}' doesn't match any auth field")
            elif TIME_REF.match(name):
                continue
            elif VAR_REF.match(name):
                if name not in known:
                    self.reject(pointer, f"Unknown placeholder '{{{name}}}'")
            else:
                self.reject(pointer, f"Invalid placeholder '{{{name}}}'")

    def _find_stray_secrets(self, value: Any, pointer: str) -> None:
        """{secrets.*} anywhere outside /auth is rejected, whatever the field."""
        if pointer == "/auth":
            return
        if isinstance(value, dict):
            for k, v in value.items():
                self._find_stray_secrets(v, f"{pointer}/{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                self._find_stray_secrets(v, f"{pointer}/{i}")
        elif isinstance(value, str) and "{secrets." in value:
            self.reject(pointer or "/", "Secrets are only allowed inside auth")

    # --- JMESPath --------------------------------------------------------

    def check_jmespath(self) -> None:
        for pointer, expr in self._jmespath_fields():
            if not isinstance(expr, str):
                continue
            if expr.startswith("$parent."):
                expr = expr[len("$parent.") :]
            try:
                jmespath.compile(expr)
            except JMESPathError as e:
                self.issues.append(Issue(SCHEMA_INVALID, pointer, f"Not a valid JMESPath: {e}"))

    def _jmespath_fields(self) -> list[tuple[str, Any]]:
        out: list[tuple[str, Any]] = []
        if "token_path" in self.auth:
            out.append(("/auth/token_path", self.auth["token_path"]))
        for i, step in enumerate(_list(self.spec.get("bootstrap"))):
            for var, expr in _dict(_dict(step).get("extract")).items():
                out.append((f"/bootstrap/{i}/extract/{var}", expr))
        streams = _dict(self.spec.get("streams"))
        for name in ("users", "usage"):
            stream = _dict(streams.get(name))
            base = f"/streams/{name}"
            out.append((f"{base}/records_path", stream.get("records_path")))
            pagination = _dict(stream.get("pagination"))
            for key in ("next_cursor_path", "has_more_path", "next_url_path"):
                if key in pagination:
                    out.append((f"{base}/pagination/{key}", pagination[key]))
            for target, value in _dict(stream.get("field_map")).items():
                path = value if isinstance(value, str) else _dict(value).get("path")
                if path is not None:
                    out.append((f"{base}/field_map/{target}", path))
            aggregate = _dict(stream.get("aggregate"))
            for key in ("explode_path", "user_key_path", "time_path"):
                if aggregate.get(key) is not None:
                    out.append((f"{base}/aggregate/{key}", aggregate[key]))
            for j, metric in enumerate(_list(aggregate.get("metrics"))):
                if "value_path" in _dict(metric):
                    out.append((f"{base}/aggregate/metrics/{j}/value_path", metric["value_path"]))
        return out

    # --- evidence shape (the docs check itself is P4, milestone 5) -----------

    def check_evidence(self) -> None:
        for pointer, item in _dict(self.spec.get("evidence")).items():
            quote = _dict(item).get("quote")
            if isinstance(quote, str) and len(quote.split()) > MAX_QUOTE_WORDS:
                message = f"Quote is longer than {MAX_QUOTE_WORDS} words"
                self.issues.append(Issue(SCHEMA_INVALID, f"/evidence/{pointer.lstrip('/')}", message))
