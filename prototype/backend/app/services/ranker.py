"""P2 Rank (TRD §8): pick the docs that matter and fit them in LLM_INPUT_TOKEN_BUDGET.

Pages are cut into sections and scored by keywords. The best auth, paging and rate-limit sections
are always included. OpenAPI paths about users and usage are included as compact JSON with their
JSON Pointer, so the model can cite them as evidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.services.docs_fetcher import DocsBundle

KEYWORDS = {
    "users": 3, "user": 2, "members": 3, "member": 2, "membership": 3, "seats": 3, "seat": 2, "license": 2,
    "activity": 3, "audit": 2, "login": 3, "last_login": 4, "last active": 4, "events": 2,
    "auth": 2, "authentication": 3, "authorization": 2, "token": 2, "oauth": 3, "scope": 2, "scopes": 3,
    "pagination": 4, "paginate": 3, "cursor": 3, "next_page": 3, "page_token": 3, "limit": 1, "offset": 1,
    "rate limit": 4, "rate-limit": 4, "429": 3, "retry-after": 3, "requests per minute": 4,
    "admin": 2, "role": 2, "permission": 2, "list": 1,
}  # fmt: skip
MUST_HAVE = {
    "auth": ("authentication", "oauth", "bearer", "api key", "access token", "scopes"),
    "paging": ("pagination", "cursor", "next_page", "page_token", "page[after]", "next_cursor"),
    "rate_limit": ("rate limit", "rate-limit", "429", "requests per minute"),
}
SECTION_CHARS = 2400
CHARS_PER_TOKEN = 4
OPENAPI_TERMS = ("user", "member", "seat", "license", "activity", "audit", "event", "login", "me")


@dataclass(frozen=True)
class Chunk:
    source: str  # page URL, or "openapi"
    pointer: str | None  # JSON Pointer into the OpenAPI file
    text: str
    score: float


def sections(text: str) -> list[str]:
    blocks = re.split(r"\n(?=#+ |\S[^\n]{0,80}\n[=-]{3,})", text)
    out: list[str] = []
    for block in blocks:
        while len(block) > SECTION_CHARS:
            cut = block.rfind("\n", 0, SECTION_CHARS)
            cut = cut if cut > SECTION_CHARS // 2 else SECTION_CHARS
            out.append(block[:cut])
            block = block[cut:]
        if block.strip():
            out.append(block)
    return out


def score(text: str) -> float:
    lower = text.lower()
    return sum(weight * min(lower.count(word), 5) for word, weight in KEYWORDS.items()) / (1 + len(text) / 4000)


def openapi_chunks(spec: dict[str, Any]) -> list[Chunk]:
    chunks: list[Chunk] = []
    head: dict[str, Any] = {k: spec[k] for k in ("servers", "host", "basePath", "schemes", "security") if k in spec}
    components = spec.get("components", {})
    if "securitySchemes" in components:
        head["components/securitySchemes"] = components["securitySchemes"]
    if "securityDefinitions" in spec:
        head["securityDefinitions"] = spec["securityDefinitions"]
    if head:
        chunks.append(Chunk("openapi", "", json.dumps(head, separators=(",", ":"))[:6000], 100.0))
    for path, item in spec.get("paths", {}).items():
        if not isinstance(item, dict) or "get" not in item:
            continue
        get = item["get"]
        blob = f"{path} {get.get('summary', '')} {' '.join(get.get('tags', []))}".lower()
        if not any(term in blob for term in OPENAPI_TERMS):
            continue
        pointer = "/paths/" + path.replace("~", "~0").replace("/", "~1") + "/get"
        text = json.dumps({"path": path, "get": get}, separators=(",", ":"))[:8000]
        chunks.append(Chunk("openapi", pointer, text, 10.0 + score(blob)))
    return chunks


def rank(bundle: DocsBundle, budget_tokens: int = 60000) -> list[Chunk]:
    candidates = [Chunk(p.url, None, s, score(s)) for p in bundle.pages for s in sections(p.text)]
    picked: list[Chunk] = []
    for terms in MUST_HAVE.values():
        hits = [c for c in candidates if any(t in c.text.lower() for t in terms)]
        if hits:
            best = max(hits, key=lambda c: c.score)
            if best not in picked:
                picked.append(best)
    if bundle.openapi is not None:
        picked += sorted(openapi_chunks(bundle.openapi), key=lambda c: -c.score)
    picked += sorted((c for c in candidates if c not in picked), key=lambda c: -c.score)
    budget = budget_tokens * CHARS_PER_TOKEN
    out: list[Chunk] = []
    used = 0
    for chunk in picked:
        if used + len(chunk.text) > budget:
            continue
        out.append(chunk)
        used += len(chunk.text)
    return out


def render_for_prompt(chunks: list[Chunk]) -> str:
    parts = []
    for chunk in chunks:
        if chunk.source == "openapi":
            parts.append(f"=== SOURCE: openapi POINTER: {chunk.pointer or '/'} ===\n{chunk.text}")
        else:
            parts.append(f"=== SOURCE: {chunk.source} ===\n{chunk.text}")
    return "\n\n".join(parts)
