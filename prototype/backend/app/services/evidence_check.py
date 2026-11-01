"""P4 Evidence (TRD §3, §8): every AI-filled field must be proved by the docs.

A quote passes when rapidfuzz.partial_ratio ≥ 90 against the cited page's text, after both are
normalised (lower-case, markdown stripped, whitespace collapsed). An OpenAPI pointer passes when it
exists in the fetched file. A quote on the page isn't enough for the fields that say where we call
and how fast: the API host and every path must also appear on the cited page (or at the pointer),
and the rate limit's number in the quote. Conflicts are settled by source rank (PRD §6.3), not by the model.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from rapidfuzz import fuzz

from app.services.docs_fetcher import DocsBundle

THRESHOLD = 90
MARKDOWN = re.compile(r"[*_`#>|\[\]]")
# Fields the AI must prove. Other filled fields (warnings, setup steps) are advice, not behaviour.
OPTIONAL_PREFIXES = ("/streams/users/field_map/", "/streams/users/pagination/has_more_path")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", MARKDOWN.sub(" ", text.lower())).strip()


def required_pointers(spec: dict[str, Any]) -> list[str]:
    pointers = ["/base_url", "/auth/type", "/rate_limit/requests_per_minute"]
    if spec["auth"]["type"] == "oauth_client_credentials":
        pointers.append("/auth/token_url")
    for i, _ in enumerate(spec.get("bootstrap", [])):
        pointers.append(f"/bootstrap/{i}/path")
    for name in ("users", "usage"):
        stream = spec["streams"].get(name)
        if not stream:
            continue
        base = f"/streams/{name}"
        pointers += [f"{base}/path", f"{base}/records_path", f"{base}/pagination"]
        if name == "users":
            pointers += [
                f"{base}/field_map/{target}"
                for target, value in stream["field_map"].items()
                if not (isinstance(value, dict) and "const" in value)
            ]
        else:
            pointers.append(f"{base}/aggregate")
    return pointers


@dataclass
class EvidenceReport:
    verified: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def verified_pct(self) -> float:
        total = len(self.verified) + len(self.failed)
        return 100.0 * len(self.verified) / total if total else 100.0


def _pointer_node(document: Any, pointer: str) -> Any:
    """The node a JSON Pointer names in the OpenAPI file, or _MISSING."""
    if document is None:
        return _MISSING
    node = document
    for raw in pointer.strip("/").split("/") if pointer.strip("/") else []:
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return _MISSING
    return node


def _evidence_for(evidence: dict[str, Any], pointer: str) -> dict[str, Any] | None:
    """Evidence for /streams/users/pagination also proves its sub-fields, and the other way round."""
    if pointer in evidence:
        item: dict[str, Any] = evidence[pointer]
        return item
    for key, item in evidence.items():
        if pointer.startswith(key + "/") or key.startswith(pointer + "/"):
            found: dict[str, Any] = item
            return found
    return None


def check(spec: dict[str, Any], bundle: DocsBundle) -> EvidenceReport:
    report = EvidenceReport()
    evidence = spec.get("evidence", {})
    page_text: dict[str, str] = {}
    for pointer in required_pointers(spec):
        item = _evidence_for(evidence, pointer)
        if item is None:
            report.failed[pointer] = "no evidence given"
            continue
        terms = _value_terms(spec, pointer)
        if item.get("source") == "openapi":
            node = _pointer_node(bundle.openapi, item.get("pointer", ""))
            if node is _MISSING:
                report.failed[pointer] = "OpenAPI pointer not found"
            elif pointer == RATE_LIMIT and not _has_rate(json.dumps(node), spec["rate_limit"]["requests_per_minute"]):
                report.failed[pointer] = "the OpenAPI file doesn't give this number of requests there"
            elif missing := _missing(terms, normalise(item.get("pointer", "").replace("~1", "/") + json.dumps(node))):
                report.failed[pointer] = f"the OpenAPI file doesn't show {missing} there"
            else:
                report.verified.append(pointer)
            continue
        page = bundle.page(item.get("url", ""))
        if page is None:
            report.failed[pointer] = "cited page was not part of the fetched docs"
            continue
        text = page_text.setdefault(page.url, normalise(page.text))
        quote = normalise(item.get("quote", ""))
        if not quote or fuzz.partial_ratio(quote, text) < THRESHOLD:
            report.failed[pointer] = "quote not found on the cited page"
        elif pointer == RATE_LIMIT and not _has_rate(item.get("quote", ""), spec["rate_limit"]["requests_per_minute"]):
            report.failed[pointer] = "the quote doesn't give this number of requests"
        elif missing := _missing(terms, text):
            report.failed[pointer] = f"the cited page doesn't mention {missing}"
        else:
            report.verified.append(pointer)
    return report


RATE_LIMIT = "/rate_limit/requests_per_minute"
_MISSING = object()


def _value_terms(spec: dict[str, Any], pointer: str) -> list[str]:
    """What the proof of a "where we call" field must mention: the API host, or a path's fixed parts."""
    if pointer == "/base_url":
        host = urlsplit(spec["base_url"]).netloc.lower()
        return [".".join(label for label in host.split(".") if "{" not in label)]
    if pointer.endswith("/path") or pointer == "/auth/token_url":
        value = _field_value(spec, pointer)
        path = urlsplit(value).path if "://" in value else value
        return [part for part in path.split("/") if part and "{" not in part]
    return []


def _field_value(spec: dict[str, Any], pointer: str) -> str:
    node: Any = spec
    for part in pointer.strip("/").split("/"):
        node = node[int(part)] if isinstance(node, list) else node.get(part, "")
    return str(node or "")


def _missing(terms: list[str], text: str) -> str | None:
    """The first term not on the page as a whole word ("users" in "/v1/users", not in "superusers")."""
    for term in terms:
        if not re.search(rf"(?<![a-z0-9]){re.escape(normalise(term))}(?![a-z0-9])", text):
            return term
    return None


def _has_rate(quote: str, per_minute: int) -> bool:
    """The quote gives the limit per minute, or the same limit per second or per hour."""
    numbers = {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", quote)}
    return per_minute in numbers or per_minute / 60 in numbers or per_minute * 60 in numbers


NEVER_DROPPED = ("/external_id", "/email")  # the user id and the cross-check join key


def drop_unproven_optional(spec: dict[str, Any], report: EvidenceReport, docs_read: bool = True) -> list[str]:
    """Optional fields that still fail after the re-ask are removed; required ones are flagged.

    When no docs could be read at all, nothing is dropped: that's missing docs, not a wrong field.
    """
    dropped = []
    for pointer in list(report.failed) if docs_read else []:
        if not pointer.startswith(OPTIONAL_PREFIXES) or pointer.endswith(NEVER_DROPPED):
            continue
        parts = pointer.strip("/").split("/")
        node = spec
        for part in parts[:-1]:
            node = node[part]
        if parts[-1] in node:
            del node[parts[-1]]
            dropped.append(pointer)
            del report.failed[pointer]
    unverified = sorted(report.failed)
    if unverified:
        spec["warnings"].append("Not proved by the docs (check before trusting): " + ", ".join(unverified))
    return dropped


# --- conflicts ---------------------------------------------------------------------------


def source_rank(source: str, spec: dict[str, Any]) -> int:
    """0 = vendor API reference, 1 = vendor OpenAPI, 2 = vendor guide, 3 = third party (PRD §6.3)."""
    if source == "openapi":
        return 1
    host = (urlsplit(source).hostname or "").lower()
    api_host = spec["app"]["api_host_pattern"].split("}", 1)[-1].lstrip(".").lower()
    vendor = ".".join(api_host.split(".")[-2:])
    if not host.endswith(vendor):
        return 3
    path = urlsplit(source).path.lower()
    return 0 if any(word in path for word in ("reference", "api-docs", "api-reference", "/api/")) else 2


def settle_conflicts(spec: dict[str, Any]) -> None:
    """The highest-ranked source wins, whatever the model chose; the spec field follows it."""
    for conflict in spec.get("conflicts", []):
        best = min(conflict["values"], key=lambda v: source_rank(v["source"], spec))
        if best["value"] != conflict["chosen"]:
            conflict["chosen"] = best["value"]
            conflict["reason"] = "The vendor's own documentation outranks other sources."
        parts = conflict["field"].strip("/").split("/")
        node: Any = spec
        for part in parts[:-1]:
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict) and parts[-1] in node:
            node[parts[-1]] = conflict["chosen"]
