"""P1 Fetch (TRD §8): read an app's public API docs, OpenAPI first.

- Every request (and every redirect hop) passes the SSRF guard.
- OpenAPI discovery: an uploaded file; links on the start page ending .json/.yaml/.yml that mention
  openapi/swagger; common paths (/openapi.json, /swagger.json, /openapi.yaml).
- Crawl: same host as the start page, max DOCS_MAX_PAGES pages, 3 levels, robots.txt respected.
- HTML → text with trafilatura; JavaScript-rendered pages (empty text) use Playwright if installed.
- Nothing readable at all → DOCS_UNREADABLE.
"""

from __future__ import annotations

import heapq
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
import yaml

from app.services.ssrf_guard import Resolver, SSRFBlockedError, check_url

MAX_BYTES = 3_000_000
MAX_REDIRECTS = 5
MAX_DEPTH = 3
USER_AGENT = "IntegrationBuilderDocsFetcher/0.1 (+public API docs only)"
RELEVANT_WORDS = (
    "user", "member", "people", "person", "seat", "licen", "auth", "token", "oauth", "scope",
    "rate", "limit", "paginat", "event", "activity", "audit", "login", "usage", "admin",
)  # fmt: skip
WRITE_WORDS = ("create", "update", "delete", "remove", "revoke", "patch", "webhook", "embed")
OPENAPI_PATHS = ("/openapi.json", "/swagger.json", "/openapi.yaml", "/openapi.yml")
LINK = re.compile(r"""href\s*=\s*["']([^"'#]+)""", re.IGNORECASE)
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".ico", ".woff", ".woff2", ".pdf", ".zip")


class DocsUnreadableError(Exception):
    """We couldn't read these docs (DOCS_UNREADABLE)."""


@dataclass
class DocPage:
    url: str
    title: str
    text: str


@dataclass
class DocsBundle:
    start_url: str
    pages: list[DocPage] = field(default_factory=list)
    openapi: dict[str, Any] | None = None
    openapi_url: str | None = None
    skipped: list[str] = field(default_factory=list)

    def page(self, url: str) -> DocPage | None:
        wanted = normalize_url(url)
        return next((p for p in self.pages if normalize_url(p.url) == wanted), None)


def normalize_url(url: str) -> str:
    return urldefrag(url)[0].rstrip("/").lower()


class Fetcher:
    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        resolver: Resolver | None = None,
        render_js: bool = True,
    ) -> None:
        self.client = httpx.Client(
            transport=transport, timeout=20.0, follow_redirects=False, headers={"User-Agent": USER_AGENT}
        )
        self.resolver = resolver
        self.render_js = render_js

    def get(self, url: str) -> httpx.Response | None:
        """GET with the SSRF guard on the URL and on every redirect hop. None if not usable."""
        for _ in range(MAX_REDIRECTS + 1):
            check_url(url, self.resolver)
            try:
                response = self.client.get(url)
            except httpx.HTTPError:
                return None
            if response.is_redirect and "location" in response.headers:
                url = urljoin(url, response.headers["location"])
                continue
            if response.status_code != 200 or len(response.content) > MAX_BYTES:
                return None
            return response
        return None

    def fetch(self, start_url: str, max_pages: int = 60, openapi_file: bytes | None = None) -> DocsBundle:
        check_url(start_url, self.resolver)  # SSRF_BLOCKED goes to the caller as is
        bundle = DocsBundle(start_url)
        if openapi_file is not None:
            bundle.openapi = parse_openapi(openapi_file)
            bundle.openapi_url = "upload"
        robots = self._robots(start_url)
        host = urlsplit(start_url).netloc.lower()
        # Most relevant pages first, so a page limit never cuts off the users or auth pages.
        queue: list[tuple[int, int, int, str]] = [(0, 0, 0, start_url)]
        order = 0
        seen = {normalize_url(start_url)}
        candidates: list[str] = []
        while queue and len(bundle.pages) < max_pages:
            _, depth, _, url = heapq.heappop(queue)
            if robots is not None and not robots.can_fetch(USER_AGENT, url):
                bundle.skipped.append(url)
                continue
            try:
                response = self.get(url)
            except SSRFBlockedError:
                bundle.skipped.append(url)
                continue
            if response is None:
                continue
            content_type = response.headers.get("content-type", "")
            if bundle.openapi is None and _looks_like_openapi(url, content_type):
                spec = _try_openapi(response.content)
                if spec is not None:
                    bundle.openapi, bundle.openapi_url = spec, url
                continue
            if "html" not in content_type and "text" not in content_type:
                continue
            html = response.text
            text = extract_text(html) or (self._render(url) if self.render_js else "")
            if text:
                bundle.pages.append(DocPage(url, _title(html), text))
            for link in LINK.findall(html):
                absolute = urldefrag(urljoin(url, link.strip()))[0]
                key = normalize_url(absolute)
                if _is_openapi_link(absolute):
                    candidates.append(absolute)
                if key in seen or urlsplit(absolute).netloc.lower() != host or absolute.lower().endswith(SKIP_EXT):
                    continue
                if not absolute.startswith(("http://", "https://")) or depth + 1 > MAX_DEPTH:
                    continue
                seen.add(key)
                order += 1
                heapq.heappush(queue, (-_relevance(absolute), depth + 1, order, absolute))
        if bundle.openapi is None:
            self._discover_openapi(bundle, candidates)
        if not bundle.pages and bundle.openapi is None:
            raise DocsUnreadableError(start_url)
        return bundle

    def _discover_openapi(self, bundle: DocsBundle, candidates: list[str]) -> None:
        parts = urlsplit(bundle.start_url)
        root = f"{parts.scheme}://{parts.netloc}"
        for url in [*candidates[:5], *(root + p for p in OPENAPI_PATHS)]:
            try:
                response = self.get(url)
            except SSRFBlockedError:
                continue
            spec = _try_openapi(response.content) if response is not None else None
            if spec is not None:
                bundle.openapi, bundle.openapi_url = spec, url
                return

    def _robots(self, start_url: str) -> RobotFileParser | None:
        parts = urlsplit(start_url)
        try:
            response = self.get(f"{parts.scheme}://{parts.netloc}/robots.txt")
        except SSRFBlockedError:
            return None
        if response is None:
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser

    def _render(self, url: str) -> str:
        """JavaScript-rendered docs: headless Chromium, if Playwright is installed."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url, timeout=20000)
                html = str(page.content())
                browser.close()
        except Exception:  # noqa: BLE001 - any browser failure just means "no text"
            return ""
        return extract_text(html)


def extract_text(html: str) -> str:
    text = trafilatura.extract(html, include_tables=True, include_links=False, favor_recall=True)
    return str(text or "").strip()


def _relevance(url: str) -> int:
    """How likely a docs page is to describe users, usage, login, paging or limits (from its URL only)."""
    path = urlsplit(url).path.lower()
    score = sum(2 for word in RELEVANT_WORDS if word in path)
    return score - sum(3 for word in WRITE_WORDS if word in path)


def parse_openapi(content: bytes) -> dict[str, Any]:
    spec = _try_openapi(content)
    if spec is None:
        raise DocsUnreadableError("the uploaded file is not an OpenAPI document")
    return spec


def _try_openapi(content: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(content)
    except ValueError:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            return None
    if isinstance(data, dict) and ("openapi" in data or "swagger" in data) and isinstance(data.get("paths"), dict):
        return data
    return None


def _is_openapi_link(url: str) -> bool:
    lower = url.lower()
    return lower.endswith((".json", ".yaml", ".yml")) and ("openapi" in lower or "swagger" in lower)


def _looks_like_openapi(url: str, content_type: str) -> bool:
    return _is_openapi_link(url) or "yaml" in content_type or "json" in content_type


def _title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
