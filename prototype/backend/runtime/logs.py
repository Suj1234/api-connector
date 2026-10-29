"""Run logging with redaction (TRD §7).

JSON lines only. Authorization and any key named like a token, secret, key or password is
redacted; emails are masked as j***@acme.com; known secret values are scrubbed anywhere.
Response bodies are never logged.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

SENSITIVE_KEY = re.compile(r"(authorization|token|secret|password|api[-_]?key|^key$|_key$)", re.IGNORECASE)
EMAIL = re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
REDACTED = "[redacted]"


def mask_email(text: str) -> str:
    return EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)


def redact(value: Any, secrets: Iterable[str] = ()) -> Any:
    secret_values = [s for s in secrets if s and len(s) >= 4]
    return _redact(value, secret_values)


def _redact(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, dict):
        return {k: REDACTED if SENSITIVE_KEY.search(str(k)) else _redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, REDACTED)
        return mask_email(value)
    return value


class RunLogger:
    def __init__(self, emit: Callable[[dict[str, Any]], None], context: dict[str, Any], secrets: Iterable[str] = ()):
        self._emit = emit
        self.context = context
        self._secrets: list[str] = [s for s in secrets if s]

    def add_secret(self, value: str) -> None:
        """Tokens fetched during the run (e.g. an OAuth access token) are scrubbed too."""
        if value:
            self._secrets.append(value)

    def emit(self, line: dict[str, Any]) -> None:
        self._emit(redact(line, self._secrets))

    def request(
        self, step: str, method: str, path: str, status: int | None, ms: int, records: int | None, retry: int
    ) -> None:
        self.emit(
            {
                "type": "log",
                **self.context,
                "step": step,
                "method": method,
                "path": path,
                "status": status,
                "ms": ms,
                "records": records,
                "retry": retry,
            }
        )

    def progress(self, step: str, status: str, detail: str = "") -> None:
        self.emit({"type": "progress", "step": step, "status": status, "detail": detail})
