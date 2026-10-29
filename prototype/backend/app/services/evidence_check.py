"""P4 Evidence (TRD §3, §8): every AI-filled field must be proved by the docs.

A quote passes when rapidfuzz.partial_ratio ≥ 90 against the cited page's text, after both are
normalised (lower-case, markdown stripped, whitespace collapsed). An OpenAPI pointer passes when it
exists in the fetched file. Conflicts are settled by source rank (PRD §6.3), not by the model.
"""

from __future__ import annotations

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


def _pointer_exists(document: Any, pointer: str) -> bool:
    if pointer in ("", "/"):
        return document is not None
    node = document
    for raw in pointer.lstrip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return False
    return True


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
        if item.get("source") == "openapi":
            if bundle.openapi is not None and _pointer_exists(bundle.openapi, item.get("pointer", "")):
                report.verified.append(pointer)
            else:
                report.failed[pointer] = "OpenAPI pointer not found"
            continue
        page = bundle.page(item.get("url", ""))
        if page is None:
            report.failed[pointer] = "cited page was not part of the fetched docs"
            continue
        text = page_text.setdefault(page.url, normalise(page.text))
        quote = normalise(item.get("quote", ""))
        if quote and fuzz.partial_ratio(quote, text) >= THRESHOLD:
            report.verified.append(pointer)
        else:
            report.failed[pointer] = "quote not found on the cited page"
    return report


def drop_unproven_optional(spec: dict[str, Any], report: EvidenceReport) -> list[str]:
    """Optional fields that still fail after the re-ask are removed; required ones are flagged."""
    dropped = []
    for pointer in list(report.failed):
        if not pointer.startswith(OPTIONAL_PREFIXES) or pointer.endswith("/external_id"):
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
