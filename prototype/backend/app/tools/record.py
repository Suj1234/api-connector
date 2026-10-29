"""Record a live run, scrub it, and save it as a replay recording (TRD §12).

    python -m app.tools.record calendly            # reads CALENDLY_TOKEN from the env / .env
    python -m app.tools.record zendesk --out path  # ZENDESK_SUBDOMAIN, ZENDESK_CLIENT_ID, ZENDESK_CLIENT_SECRET

Writes fixtures/replay/<app>/recorded.json by default; the synthetic demo recording is never touched.
Nothing is written unless the run succeeded and the scrubber ran.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.config import PROTOTYPE, get
from app.services.codegen import render
from app.tools.scrubber import scrub_recording
from runner.__main__ import _network_transport, run
from runtime import helpers as h

# Which env vars hold each example app's credentials (live tests use the same names).
LIVE_ENV: dict[str, dict[str, Any]] = {
    "calendly": {"secrets": {"token": "CALENDLY_TOKEN"}, "variables": {}},
    "zendesk": {
        "secrets": {"client_id": "ZENDESK_CLIENT_ID", "client_secret": "ZENDESK_CLIENT_SECRET"},
        "variables": {"subdomain": "ZENDESK_SUBDOMAIN"},
    },
    "notion": {"secrets": {"token": "NOTION_TOKEN"}, "variables": {}},
}


class RecordingTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport) -> None:
        self.inner = inner
        self.interactions: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        response.read()
        try:
            body = response.json()
        except ValueError:
            body = None
        query: dict[str, Any] = {}
        for key, value in request.url.params.multi_items():
            query.setdefault(key, []).append(value)
        self.interactions.append(
            {
                "method": request.method,
                "url": str(request.url.copy_with(query=None)),
                "query": {k: v[0] if len(v) == 1 else v for k, v in query.items()},
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": body,
            }
        )
        return response


def live_payload(app: str) -> dict[str, Any]:
    names = LIVE_ENV[app]
    return {
        "run_mode": "live",
        "secrets": {field: get(env) for field, env in names["secrets"].items()},
        "variables": {field: get(env) for field, env in names["variables"].items()},
        "context": {"tenant": "recording", "run_id": "record"},
    }


def record(app: str, out: Path) -> int:
    spec = json.loads((PROTOTYPE / "specs" / "examples" / f"{app}.json").read_text())
    payload = live_payload(app)
    recorder = RecordingTransport(_network_transport())
    lines: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        module = Path(tmp) / f"{app}_v1.py"
        module.write_text(render(spec, 1))
        exit_code = run(module, "full", payload, lines.append, live_transport=recorder)
    result = next(line for line in lines if line["type"] == "result")
    if exit_code != 0:
        print(f"Live run failed: {result['error_code']} (exit {exit_code}). Nothing saved.", file=sys.stderr)
        return exit_code
    # Time-window parameters change every run; replay matches them with a wildcard.
    for item in recorder.interactions:
        for key, value in item["query"].items():
            if isinstance(value, str) and h.parse_time(value) is not None:
                item["query"][key] = "*"
    recording = {
        "app": app,
        "recorded_at": h.fmt_time(h.utc_now()),
        "variables": payload["variables"],
        "interactions": recorder.interactions,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scrub_recording(recording), indent=1) + "\n")
    print(f"Saved {len(recorder.interactions)} scrubbed responses ({result['summary']['users']} users) to {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="record")
    parser.add_argument("app", choices=sorted(LIVE_ENV))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    return record(args.app, args.out or PROTOTYPE / "fixtures" / "replay" / args.app / "recorded.json")


if __name__ == "__main__":
    sys.exit(main())
