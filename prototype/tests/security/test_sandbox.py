"""The sandbox: a call to another host fails with exit code 8; the runner gets no app secrets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.codegen import render
from app.services.sandbox import DEMO_ISOLATION_LABEL, run_connector
from tests.conftest import REPLAY, base_spec, example_spec


def evil_recording(tmp_path: Path) -> Path:
    """A recorded API whose next-page link points at another host."""
    recording = {
        "recorded_at": "2026-10-29T09:00:00Z",
        "interactions": [
            {
                "url": "https://api.example.com/v1/users",
                "query": {},
                "body": {"data": [{"id": 1, "email": "a@acme.example"}], "next": "https://evil.example.net/steal"},
            }
        ],
    }
    path = tmp_path / "evil.json"
    path.write_text(json.dumps(recording))
    return path


def next_url_code() -> str:
    return render(base_spec(pagination={"type": "next_url", "next_url_path": "next"}), 1)


def test_subprocess_blocks_another_host_with_exit_8(tmp_path: Path) -> None:
    payload = {"run_mode": "replay", "replay_file": str(evil_recording(tmp_path))}
    result = run_connector(next_url_code(), payload, "api.example.com")
    assert result.exit_code == 8 and result.result["error_code"] == "HOST_BLOCKED"
    assert result.isolation_note == DEMO_ISOLATION_LABEL


def test_subprocess_gets_no_app_secrets_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VAULT_KEY", "master-key-must-not-leak")
    monkeypatch.setenv("GEMINI_API_KEY", "llm-key-must-not-leak")
    code = (
        "import json, os\n"
        "print(json.dumps({'type': 'result', 'status': 'ok', 'env': sorted(os.environ)}))\n"
        "raise SystemExit(0)\n"
    )
    result = run_connector(code, {"run_mode": "live", "secrets": {}}, "api.example.com")
    env_names = result.lines[0]["env"]
    assert "VAULT_KEY" not in env_names and "GEMINI_API_KEY" not in env_names


def test_subprocess_replay_runs_the_demo(tmp_path: Path) -> None:
    payload = {"run_mode": "replay", "replay_file": str(REPLAY / "calendly" / "recording.json")}
    result = run_connector(
        render(example_spec("calendly")),
        payload,
        "api.calendly.com",
    )
    assert result.exit_code == 0 and len(result.records) == 48
