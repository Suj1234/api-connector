from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.tools.scrubber import scrub_recording
from tests.conftest import REPLAY, example_spec, run_module


def test_scrubbed_recording_hides_people_and_customer_values() -> None:
    recording = {
        "variables": {"subdomain": "realcorp"},
        "interactions": [
            {
                "method": "GET",
                "url": "https://realcorp.zendesk.com/api/v2/users/0f8fad5b-d9cb-469f-a165-70867728950e",
                "query": {"page[after]": "abc"},
                "headers": {"Set-Cookie": "x", "X-RateLimit-Reset": "3"},
                "body": {
                    "users": [
                        {"id": 123, "name": "Real Person", "email": "Real.Person@realcorp.com", "manager_id": 123}
                    ],
                    "access_token": "live-token",
                    "next_page_token": "cursor-1",
                },
            }
        ],
    }
    out = scrub_recording(recording)
    text = json.dumps(out)
    for real in ("realcorp", "Real Person", "Real.Person", "0f8fad5b", "live-token", "Set-Cookie"):
        assert real.lower() not in text.lower(), real
    user = out["interactions"][0]["body"]["users"][0]
    assert user["id"] == user["manager_id"] != 123  # the same id maps to the same fake
    assert out["interactions"][0]["body"]["next_page_token"] == "cursor-1"  # paging survives
    assert out["interactions"][0]["headers"] == {"X-RateLimit-Reset": "3"}
    assert out["variables"] == {"subdomain": "demo"}


def test_scrubbed_recording_still_replays(build_module: Callable[[dict[str, Any]], Path], tmp_path: Path) -> None:
    """IDs are replaced consistently, so joins (members ↔ event hosts) still work after scrubbing."""
    original = json.loads((REPLAY / "calendly" / "recording.json").read_text())
    scrubbed = tmp_path / "scrubbed.json"
    scrubbed.write_text(json.dumps(scrub_recording(original)))
    run = run_module(build_module(example_spec("calendly")), {"run_mode": "replay", "replay_file": str(scrubbed)})
    assert run.exit_code == 0, run.result
    assert len(run.records) == 48
    assert len([r for r in run.records if r["usage_metric_value"]]) == 33
    assert not any("acme.example" in r["email"] for r in run.records)
