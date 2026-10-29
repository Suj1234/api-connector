"""The §15 demo flow through the real API (recorded AI, replay data, subprocess sandbox)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.api as api

ACME = {"X-Tenant": "acme"}
GLOBEX = {"X-Tenant": "globex"}
INTERNAL = {"X-Tenant": "internal"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setenv("SANDBOX_MODE", "subprocess")
    monkeypatch.setenv("LLM_PROVIDER", "recorded")
    monkeypatch.setenv("VAULT_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
    monkeypatch.setattr(api, "_state", None)
    with TestClient(api.app) as c:
        yield c


def wait(client: TestClient, connector_id: int, headers: dict[str, str]) -> list[dict[str, Any]]:
    with client.stream("GET", f"/api/connectors/{connector_id}/events", headers=headers) as stream:
        events = [json.loads(line[6:]) for line in stream.iter_lines() if line.startswith("data: ")]
    assert events[-1]["stage"] == "done", events
    return events


def test_full_demo_flow(client: TestClient) -> None:
    # F1: inventory
    inventory = {row["app"]: row for row in client.get("/api/inventory", headers=ACME).json()}
    assert inventory["Calendly"]["usage_status"] == "No usage data" and inventory["Calendly"]["days_to_renewal"] == 58
    assert not inventory["Calendly"]["in_library"]

    # F3: build with AI (recorded mode: the hand-written spec stands in, and says so)
    created = client.post(
        "/api/connectors",
        headers=ACME,
        data={"app_name": "Calendly", "docs_url": "https://developer.calendly.com/api-docs"},
    )
    cid = created.json()["id"]
    events = wait(client, cid, ACME)
    assert any(e["stage"] == "ai" and "Hand-written" in e["message"] for e in events)
    detail = client.get(f"/api/connectors/{cid}", headers=ACME).json()
    assert detail["status"] == "draft" and detail["tier"] == "T2"
    assert detail["summary"]["usage"]["label"] == "Meetings hosted (90 days)"
    assert any("Not proved by the docs" in w for w in detail["warnings"])  # no docs offline: honestly flagged

    # F5: test on demo data
    run_id = client.post(f"/api/connectors/{cid}/test", headers=ACME, json={}).json()["run_id"]
    wait(client, cid, ACME)
    run = client.get(f"/api/runs/{run_id}", headers=ACME).json()
    assert run["exit_code"] == 0 and run["summary"]["users"] == 48
    assert run["checklist"] == {"login": "ok", "users": "ok", "usage": "ok", "map": "ok"}
    assert "def get_users" in client.get(f"/api/connectors/{cid}/code", headers=ACME).text

    # F6: savings
    s = client.get(f"/api/connectors/{cid}/savings", headers=ACME).json()
    assert (s["buckets"]["left"], s["buckets"]["inactive"], s["buckets"]["active"]) == (6, 11, 31)
    assert (s["never_assigned"], s["recoverable_annual"], s["days_to_renewal"]) == (12, 6960.0, 58)
    assert client.post(f"/api/connectors/{cid}/confirm", headers=ACME, json={"accept": True}).json()["status"] == "live"

    # F8: library: Globex can't see it until the platform team approves it
    sub = client.post(f"/api/connectors/{cid}/submit-to-library", headers=ACME).json()
    assert sub["status"] == "pending_review"
    assert not {r["app"]: r for r in client.get("/api/inventory", headers=GLOBEX).json()}["Calendly"]["in_library"]
    assert client.get("/api/library/review-queue", headers=ACME).status_code == 403
    queue = client.get("/api/library/review-queue", headers=INTERNAL).json()
    assert queue[0]["app"] == "Calendly" and "def get_users" in queue[0]["code"]
    client.post(f"/api/library/{sub['library_spec_id']}/approve", headers=INTERNAL, json={"note": "ok"})
    row = {r["app"]: r for r in client.get("/api/inventory", headers=GLOBEX).json()}["Calendly"]
    assert row["in_library"]

    # Globex connects from the library with its own token; its own test runs
    gid = client.post(
        "/api/connectors", headers=GLOBEX, data={"app_name": "Calendly", "from_library_spec_id": row["library_spec_id"]}
    ).json()["id"]
    client.post(f"/api/connectors/{gid}/credentials", headers=GLOBEX, json={"secrets": {"token": "globex-own-token"}})
    gdetail = client.get(f"/api/connectors/{gid}", headers=GLOBEX).json()
    assert gdetail["from_library"] and gdetail["has_credentials"] and "globex-own-token" not in json.dumps(gdetail)
    client.post(f"/api/connectors/{gid}/test", headers=GLOBEX, json={"run_mode": "replay"})
    wait(client, gid, GLOBEX)
    assert client.get(f"/api/connectors/{gid}", headers=GLOBEX).json()["last_run"]["exit_code"] == 0
    # Acme's connector and users are invisible to Globex
    assert client.get(f"/api/connectors/{cid}", headers=GLOBEX).status_code == 404


def test_ssrf_link_fails_with_a_plain_message(client: TestClient) -> None:
    cid = client.post(
        "/api/connectors", headers=ACME, data={"app_name": "Calendly", "docs_url": "http://169.254.169.254/latest"}
    ).json()["id"]
    events = wait(client, cid, ACME)
    assert events[-1]["code"] == "SSRF_BLOCKED"
    assert "private or internal address" in events[-1]["message"]


def test_secrets_are_write_only(client: TestClient) -> None:
    cid = client.post(
        "/api/connectors",
        headers=ACME,
        data={"app_name": "Notion", "docs_url": "https://developers.notion.com/reference/get-users"},
    ).json()["id"]
    wait(client, cid, ACME)
    client.post(f"/api/connectors/{cid}/credentials", headers=ACME, json={"secrets": {"token": "secret-notion-token"}})
    everything = json.dumps(client.get(f"/api/connectors/{cid}", headers=ACME).json())
    assert "secret-notion-token" not in everything


def test_count_mismatch_needs_a_note(client: TestClient) -> None:
    cid = client.post(
        "/api/connectors",
        headers=ACME,
        data={"app_name": "Zendesk", "docs_url": "https://developer.zendesk.com/api-reference/"},
    ).json()["id"]
    wait(client, cid, ACME)
    client.post(f"/api/connectors/{cid}/test", headers=ACME, json={})
    wait(client, cid, ACME)
    assert client.get(f"/api/connectors/{cid}/savings", headers=ACME).json()["needs_note"]
    assert client.post(f"/api/connectors/{cid}/confirm", headers=ACME, json={"accept": True}).status_code == 422
    ok = client.post(
        f"/api/connectors/{cid}/confirm", headers=ACME, json={"accept": True, "note": "2 suspended agents"}
    )
    assert ok.json()["status"] == "live"
