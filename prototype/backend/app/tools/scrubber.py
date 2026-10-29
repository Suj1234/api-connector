"""Scrubber for live recordings (TRD §12): real people never reach a committed file.

Generic, key- and pattern-based, and consistent: the same real value always becomes the same fake
value within one recording, so IDs still join (a user's URI in a member list and in an event).
- emails → fake.N@example.com          - person names → "Person N"
- UUIDs (also inside URIs) → stable fake UUIDs
- numeric ids → stable fake numbers   - tokens, secrets, keys, passwords → "[scrubbed]"
- headers are dropped except a small allowlist (rate-limit headers, Link)
"""

from __future__ import annotations

import re
import uuid
from typing import Any

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UUID = re.compile(r"\b[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}\b")
SECRET_KEY = re.compile(r"(token|secret|password|api[-_]?key|authorization|signature)", re.IGNORECASE)
NAME_KEY = re.compile(r"^(name|full_name|display_name|first_name|last_name|user_name|given_name|family_name)$")
ID_KEY = re.compile(r"(^id$|_id$)")
PAGING_KEY = re.compile(r"(page|cursor|after|before|next)", re.IGNORECASE)  # page_token is paging, not a secret
KEPT_HEADERS = {"link", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"}
NAMESPACE = uuid.UUID("a3c4f6d0-2b1e-4c55-9a77-5e1d2f0b8c42")


class Scrubber:
    def __init__(self, replace: dict[str, str] | None = None) -> None:
        # Admin-entered values (e.g. a Zendesk subdomain) name the customer; they become "demo".
        self.replace = {k: v for k, v in (replace or {}).items() if k}
        self.emails: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self.uuids: dict[str, str] = {}
        self.numbers: dict[int, int] = {}

    def email(self, value: str) -> str:
        key = value.lower()
        if key not in self.emails:
            self.emails[key] = f"fake.{len(self.emails) + 1}@example.com"
        return self.emails[key]

    def name(self, value: str) -> str:
        if value not in self.names:
            self.names[value] = f"Person {len(self.names) + 1}"
        return self.names[value]

    def uuid(self, value: str) -> str:
        key = value.lower().replace("-", "")
        if key not in self.uuids:
            fake = str(uuid.uuid5(NAMESPACE, f"fake-{len(self.uuids)}"))
            self.uuids[key] = fake if "-" in value else fake.replace("-", "")
        return self.uuids[key]

    def number(self, value: int) -> int:
        if value not in self.numbers:
            self.numbers[value] = 100000 + len(self.numbers) + 1
        return self.numbers[value]

    def text(self, value: str) -> str:
        for real, fake in self.replace.items():
            value = re.sub(re.escape(real), fake, value, flags=re.IGNORECASE)
        value = EMAIL.sub(lambda m: self.email(m.group(0)), value)
        return UUID.sub(lambda m: self.uuid(m.group(0)), value)

    def value(self, value: Any, key: str = "") -> Any:
        if SECRET_KEY.search(key) and not PAGING_KEY.search(key) and value is not None:
            return "[scrubbed]"
        if isinstance(value, dict):
            return {k: self.value(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.value(v, key) for v in value]
        if isinstance(value, str):
            if NAME_KEY.match(key) and value and not EMAIL.fullmatch(value):
                return self.name(value)
            return self.text(value)
        if isinstance(value, int) and not isinstance(value, bool) and ID_KEY.search(key):
            return self.number(value)
        return value

    def interaction(self, item: dict[str, Any]) -> dict[str, Any]:
        headers = {k: v for k, v in item.get("headers", {}).items() if k.lower() in KEPT_HEADERS}
        return {
            "method": item["method"],
            "url": self.text(item["url"]),
            "query": self.value(item.get("query", {})),
            "status": item.get("status", 200),
            "headers": {k: self.text(v) for k, v in headers.items()},
            "body": self.value(item.get("body")),
        }


def scrub_recording(recording: dict[str, Any]) -> dict[str, Any]:
    variables = recording.get("variables", {})
    scrubber = Scrubber({str(v): "demo" for v in variables.values() if len(str(v)) >= 3})
    return {
        **{k: v for k, v in recording.items() if k not in ("interactions", "variables")},
        "variables": {k: "demo" for k in recording.get("variables", {})},
        "interactions": [scrubber.interaction(i) for i in recording.get("interactions", [])],
    }
