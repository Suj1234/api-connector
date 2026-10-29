"""Milestone 5: P1–P8 with a scripted model. Every stage is real except the LLM call itself.

Docs come from fixtures/docs_example (a fictional "Example App") served by a fake web server.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.services.docs_fetcher import Fetcher
from app.services.draft_convert import spec_to_draft
from app.services.hints import scrub_hint
from app.services.llm_client import ScriptedLLM
from app.services.pipeline import Pipeline, PipelineError, Settings
from tests.conftest import PROTOTYPE, base_spec

DOCS = PROTOTYPE / "fixtures" / "docs_example"
CONFLICT = PROTOTYPE / "fixtures" / "docs_conflict"
ROOT = "https://docs.example.com"
PAGES = {
    "/reference": DOCS / "index.html",
    "/reference/authentication": DOCS / "authentication.html",
    "/reference/users": DOCS / "users.html",
    "/reference/pagination": DOCS / "pagination.html",
    "/reference/rate-limits": DOCS / "rate-limits.html",
}
SECRET = "live-token-should-never-reach-the-model"


def docs_site(pages: dict[str, Path], extra: dict[str, httpx.Response] | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if extra and request.url.path in extra:
            return extra[request.url.path]
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        file = pages.get(request.url.path)
        if file is None:
            return httpx.Response(404)
        return httpx.Response(200, text=file.read_text(), headers={"content-type": "text/html"})

    return httpx.MockTransport(handler)


def public(_: str) -> list[str]:
    return ["93.184.216.34"]


def ev(page: str, quote: str) -> dict[str, str]:
    return {"url": f"{ROOT}{page}", "quote": quote}


def good_spec() -> dict[str, Any]:
    spec = base_spec(pagination={"type": "cursor", "request_param": "cursor", "next_cursor_path": "next"})
    spec["origin"] = "ai"
    spec["rate_limit"] = {"requests_per_minute": 300, "headers": {}, "retry_after_header": "Retry-After"}
    spec["evidence"] = {
        "/base_url": ev("/reference", "The Example App REST API is served from https://api.example.com/v1."),
        "/auth/type": ev("/reference/authentication", "Authenticate every request with a bearer token."),
        "/rate_limit/requests_per_minute": ev(
            "/reference/rate-limits", "Each workspace may make 300 requests per minute."
        ),
        "/streams/users/path": ev("/reference/users", "GET /users returns the people in your workspace."),
        "/streams/users/records_path": ev(
            "/reference/users", "The users are returned in the data array of the response."
        ),
        "/streams/users/pagination": ev(
            "/reference/pagination",
            "Pass the value of the next field from the previous response as the cursor query parameter.",
        ),
        "/streams/users/field_map": ev(
            "/reference/users", "Each user object has an id, an email, a name and last_seen"
        ),
    }
    return spec


def recording(tmp_path: Path) -> Path:
    users = [{"id": i, "email": f"person{i}@acme.example", "last_seen": "2026-10-20T00:00:00Z"} for i in range(1, 6)]
    rec = {
        "recorded_at": "2026-10-29T09:00:00Z",
        "interactions": [
            {"url": "https://api.example.com/v1/users", "query": {}, "body": {"data": users[:3], "next": "c1"}},
            {
                "url": "https://api.example.com/v1/users",
                "query": {"cursor": "c1"},
                "body": {"data": users[3:], "next": None},
            },
        ],
    }
    path = tmp_path / "example.json"
    path.write_text(json.dumps(rec))
    return path


def pipeline(llm: ScriptedLLM, events: list[dict[str, Any]], transport: httpx.BaseTransport | None = None) -> Pipeline:
    fetcher = Fetcher(transport or docs_site(PAGES), resolver=public, render_js=False)
    settings = Settings(draft_model="draft-model", escalate_model="escalate-model", sandbox="subprocess")
    return Pipeline(llm, fetcher, events.append, settings)


# --- draft: P1–P5 -------------------------------------------------------------------------


def test_draft_happy_path_proves_every_field() -> None:
    events: list[dict[str, Any]] = []
    llm = ScriptedLLM([spec_to_draft(good_spec())])
    outcome = pipeline(llm, events).draft("Example App", f"{ROOT}/reference")
    assert outcome.evidence.failed == {}
    assert outcome.spec["streams"]["users"]["method"] == "GET"
    assert [e["stage"] for e in events if e["status"] == "ok"] == ["fetch", "draft", "evidence", "rules"]
    assert len(llm.prompts) == 1 and llm.models == ["draft-model"]


def test_robots_txt_is_respected() -> None:
    fetched: list[str] = []
    site = docs_site({**PAGES, "/private/admin": DOCS / "injection.html"})

    def spy(request: httpx.Request) -> httpx.Response:
        fetched.append(request.url.path)
        return site.handle_request(request)

    bundle = Fetcher(httpx.MockTransport(spy), resolver=public, render_js=False).fetch(f"{ROOT}/reference")
    assert "/private/admin" not in fetched
    assert f"{ROOT}/private/admin" in bundle.skipped
    assert {p.url for p in bundle.pages} >= {f"{ROOT}{path}" for path in PAGES}


def test_bad_evidence_is_reasked_once_then_proved() -> None:
    wrong = good_spec()
    wrong["evidence"]["/streams/users/path"] = ev("/reference/users", "GET /members lists every member")
    llm = ScriptedLLM([spec_to_draft(wrong), spec_to_draft(good_spec())])
    outcome = pipeline(llm, []).draft("Example App", f"{ROOT}/reference")
    assert outcome.evidence.failed == {}
    assert len(llm.prompts) == 2 and "/streams/users/path" in llm.prompts[1]


def test_unproved_optional_field_is_dropped_and_required_is_flagged() -> None:
    spec = good_spec()
    spec["streams"]["users"]["field_map"]["role"] = "role"
    spec["evidence"]["/streams/users/field_map"] = ev("/reference/users", "users have a role and a department")
    spec["evidence"]["/streams/users/field_map/external_id"] = ev("/reference/users", "Each user object has an id")
    spec["evidence"]["/streams/users/field_map/email"] = ev("/reference/users", "Each user object has an id, an email")
    spec["evidence"]["/streams/users/field_map/last_active_at"] = ev(
        "/reference/users", "last_seen, the time the user last used"
    )
    spec["evidence"]["/rate_limit/requests_per_minute"] = ev("/reference/rate-limits", "unlimited requests")
    llm = ScriptedLLM([spec_to_draft(spec), spec_to_draft(spec)])
    outcome = pipeline(llm, []).draft("Example App", f"{ROOT}/reference")
    assert "/streams/users/field_map/role" in outcome.dropped
    assert "role" not in outcome.spec["streams"]["users"]["field_map"]
    assert any("/rate_limit/requests_per_minute" in w for w in outcome.spec["warnings"])


def test_prompt_injection_in_docs_is_contained() -> None:
    """SC-06: the docs tell the model to exfiltrate; a fooled model's spec is discarded by the rules."""
    pages = {**PAGES, "/reference/users": DOCS / "injection.html"}
    fooled = good_spec()
    fooled["base_url"] = "https://collector.evil.example.net"
    llm = ScriptedLLM([spec_to_draft(fooled)] * 3)
    with pytest.raises(PipelineError) as err:
        pipeline(llm, [], docs_site(pages)).draft("Example App", f"{ROOT}/reference")
    assert err.value.code == "RULES_REJECTED"
    assert "untrusted data" in llm.prompts[0]  # the system rules travel with every draft


def test_a_draft_can_never_ask_for_delete() -> None:
    draft = spec_to_draft(good_spec())
    draft["users_stream"]["method"] = "DELETE"  # not in the draft schema; ignored
    outcome = pipeline(ScriptedLLM([draft]), []).draft("Example App", f"{ROOT}/reference")
    assert outcome.spec["streams"]["users"]["method"] == "GET"


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://localhost:8000/docs",
        "http://10.0.0.5/api",
        "file:///etc/passwd",
    ],
)
def test_ssrf_links_are_blocked(url: str) -> None:
    """SC-12."""
    with pytest.raises(PipelineError) as err:
        pipeline(ScriptedLLM([]), []).draft("X", url)
    assert err.value.code == "SSRF_BLOCKED"


def test_redirect_to_an_internal_address_is_not_followed() -> None:
    extra = {"/reference": httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})}
    with pytest.raises(PipelineError) as err:
        pipeline(ScriptedLLM([]), [], docs_site(PAGES, extra)).draft("X", f"{ROOT}/reference")
    assert err.value.code == "DOCS_UNREADABLE"


def test_name_resolving_to_a_private_address_is_blocked() -> None:
    fetcher = Fetcher(docs_site(PAGES), resolver=lambda host: ["10.1.2.3"], render_js=False)
    p = Pipeline(ScriptedLLM([]), fetcher, lambda e: None, Settings(sandbox="subprocess"))
    with pytest.raises(PipelineError) as err:
        p.draft("X", f"{ROOT}/reference")
    assert err.value.code == "SSRF_BLOCKED"


def test_unreadable_docs() -> None:
    with pytest.raises(PipelineError) as err:
        pipeline(ScriptedLLM([]), [], docs_site({})).draft("X", f"{ROOT}/nothing")
    assert err.value.code == "DOCS_UNREADABLE"


def test_openapi_is_found_and_pointer_evidence_counts() -> None:
    openapi = {
        "openapi": "3.0.0",
        "servers": [{"url": "https://api.example.com/v1"}],
        "paths": {"/users": {"get": {"summary": "List users", "responses": {"200": {"description": "ok"}}}}},
    }
    extra = {"/openapi.json": httpx.Response(200, json=openapi)}
    spec = good_spec()
    spec["evidence"]["/streams/users/path"] = {"source": "openapi", "pointer": "/paths/~1users/get"}
    llm = ScriptedLLM([spec_to_draft(spec)])
    outcome = pipeline(llm, [], docs_site(PAGES, extra)).draft("Example App", f"{ROOT}/reference")
    assert outcome.bundle.openapi_url == f"{ROOT}/openapi.json"
    assert "/streams/users/path" in outcome.evidence.verified
    assert "POINTER: /paths/~1users/get" in llm.prompts[0]


def test_docs_conflict_is_settled_by_the_vendor_page() -> None:
    """SC-17: a third-party guide says 60/min; the vendor reference says 500. The vendor wins."""
    pages = {**PAGES, "/reference/rate-limits": CONFLICT / "vendor-rate-limits.html"}
    blog = {"/blog/guide": httpx.Response(200, text=(CONFLICT / "thirdparty-guide.html").read_text())}
    spec = good_spec()
    spec["rate_limit"]["requests_per_minute"] = 60
    spec["evidence"]["/rate_limit/requests_per_minute"] = ev(
        "/reference/rate-limits", "500 requests per minute per user"
    )
    spec["conflicts"] = [
        {
            "field": "/rate_limit/requests_per_minute",
            "values": [
                {"value": 60, "source": "https://blog.example.org/guide"},
                {"value": 500, "source": f"{ROOT}/reference/rate-limits"},
            ],
            "chosen": 60,
            "reason": "The guide is clearer",
        }
    ]
    outcome = pipeline(ScriptedLLM([spec_to_draft(spec)]), [], docs_site(pages, blog)).draft(
        "Example App", f"{ROOT}/reference"
    )
    conflict = outcome.spec["conflicts"][0]
    assert conflict["chosen"] == 500 and outcome.spec["rate_limit"]["requests_per_minute"] == 500


# --- test + repair: P6–P8 ------------------------------------------------------------------


def test_test_passes_without_repair(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = []
    p = pipeline(ScriptedLLM([]), events)
    outcome = p.test(good_spec(), {"run_mode": "replay", "replay_file": str(recording(tmp_path))})
    assert outcome.status == "passed" and len(outcome.result.records) == 5
    assert outcome.repairs == []


def test_wrong_records_path_is_repaired_from_the_shape(tmp_path: Path) -> None:
    broken = good_spec()
    broken["streams"]["users"]["records_path"] = "users"
    fix = {
        "diagnosis": "The users are in data, not users",
        "patch": [{"op": "replace", "path": "/streams/users/records_path", "value_json": '"data"'}],
        "evidence": [
            {
                "field": "/streams/users/records_path",
                "url": f"{ROOT}/reference/users",
                "quote": "returned in the data array",
            }
        ],
    }
    llm = ScriptedLLM([fix])
    bundle = Fetcher(docs_site(PAGES), resolver=public, render_js=False).fetch(f"{ROOT}/reference")
    payload = {"run_mode": "replay", "replay_file": str(recording(tmp_path)), "secrets": {"token": SECRET}}
    outcome = pipeline(llm, []).test(broken, payload, bundle)
    assert outcome.status == "passed"
    assert outcome.spec["streams"]["users"]["records_path"] == "data"
    assert outcome.repairs[0]["accepted"] and llm.models == ["draft-model"]
    prompt = llm.prompts[0]
    assert "MAPPING_FAILED" in prompt and '"data": [{"id": "number"' in prompt  # shape, not values
    assert "person1" not in prompt and "acme.example" not in prompt and SECRET not in prompt


def test_repair_cannot_touch_the_host_and_third_try_escalates(tmp_path: Path) -> None:
    broken = good_spec()
    broken["streams"]["users"]["path"] = "/members"
    sneaky = {
        "diagnosis": "x",
        "patch": [{"op": "replace", "path": "/base_url", "value_json": '"https://evil.example.net"'}],
    }
    wrong = {"diagnosis": "x", "patch": [{"op": "replace", "path": "/streams/users/path", "value_json": '"/people"'}]}
    right = {"diagnosis": "x", "patch": [{"op": "replace", "path": "/streams/users/path", "value_json": '"/users"'}]}
    llm = ScriptedLLM([sneaky, wrong, right])
    outcome = pipeline(llm, []).test(broken, {"run_mode": "replay", "replay_file": str(recording(tmp_path))})
    assert outcome.status == "passed"
    assert [r["accepted"] for r in outcome.repairs] == [False, True, True]
    assert llm.models == ["draft-model", "draft-model", "escalate-model"]


def test_repair_gives_up_after_three_tries(tmp_path: Path) -> None:
    broken = good_spec()
    broken["streams"]["users"]["path"] = "/members"
    wrong = {"diagnosis": "x", "patch": [{"op": "replace", "path": "/streams/users/path", "value_json": '"/people"'}]}
    llm = ScriptedLLM([copy.deepcopy(wrong) for _ in range(3)])
    outcome = pipeline(llm, []).test(broken, {"run_mode": "replay", "replay_file": str(recording(tmp_path))})
    assert outcome.status == "needs_help" and len(outcome.repairs) == 3


def test_permission_errors_are_never_repaired(tmp_path: Path) -> None:
    rec = {"recorded_at": "2026-10-29T09:00:00Z", "interactions": [
        {"url": "https://api.example.com/v1/users", "query": {}, "status": 403, "body": {"error": "forbidden"}}]}  # fmt: skip
    path = tmp_path / "403.json"
    path.write_text(json.dumps(rec))
    llm = ScriptedLLM([])
    outcome = pipeline(llm, []).test(good_spec(), {"run_mode": "replay", "replay_file": str(path)})
    assert outcome.result.exit_code == 3 and outcome.status == "failed" and llm.prompts == []


# --- hints (TRD §8.1) ---------------------------------------------------------------------


def test_hint_scrubbing() -> None:
    hint = (
        "Users are under /members for jane.doe@acme.com, see https://x.example.com/a?token=abc. "
        "Account 12345678. Ask Priya Sharma. My token is sk-live-9999."
    )
    out = scrub_hint(hint, secrets=["sk-live-9999"], user_names=["Priya Sharma"])
    for leaked in ("jane.doe", "token=abc", "12345678", "Priya", "Sharma", "sk-live-9999"):
        assert leaked not in out
    assert "/members" in out
    assert len(scrub_hint("x" * 900)) == 500


def test_scrubbed_hint_reaches_the_prompt() -> None:
    llm = ScriptedLLM([spec_to_draft(good_spec())])
    hint = scrub_hint("Users live at /users; contact bob@acme.com", user_names=["Bob"])
    pipeline(llm, []).draft("Example App", f"{ROOT}/reference", hint=hint)
    assert "Users live at /users" in llm.prompts[0] and "bob@acme.com" not in llm.prompts[0]


def test_email_is_never_dropped_and_nothing_is_dropped_without_docs() -> None:
    spec = good_spec()
    spec["evidence"]["/streams/users/field_map"] = ev("/reference/users", "nothing like this on the page")
    llm = ScriptedLLM([spec_to_draft(spec), spec_to_draft(spec)])
    outcome = pipeline(llm, []).draft("Example App", f"{ROOT}/reference")
    assert "email" in outcome.spec["streams"]["users"]["field_map"]  # flagged, not dropped
    assert "/streams/users/field_map/last_active_at" in outcome.dropped

    from app.services.docs_fetcher import DocsBundle

    llm = ScriptedLLM([spec_to_draft(spec), spec_to_draft(spec)])
    offline = pipeline(llm, []).draft("Example App", f"{ROOT}/reference", bundle=DocsBundle(f"{ROOT}/reference"))
    assert offline.dropped == [] and "last_active_at" in offline.spec["streams"]["users"]["field_map"]


def test_a_host_given_as_a_url_is_tidied() -> None:
    draft = spec_to_draft(good_spec())
    draft["app"]["api_host_pattern"] = "https://API.example.com/v1/"
    llm = ScriptedLLM([draft])
    outcome = pipeline(llm, []).draft("Example App", f"{ROOT}/reference")
    assert outcome.spec["app"]["api_host_pattern"] == "api.example.com"
    assert len(llm.prompts) == 1  # no fix needed


def test_a_bad_host_gets_one_fix_then_passes() -> None:
    bad = spec_to_draft(good_spec())
    bad["app"]["api_host_pattern"] = "localhost"
    llm = ScriptedLLM([bad, spec_to_draft(good_spec())])
    outcome = pipeline(llm, []).draft("Example App", f"{ROOT}/reference")
    assert outcome.spec["app"]["api_host_pattern"] == "api.example.com"
    assert "not 'localhost'" in llm.prompts[1]
