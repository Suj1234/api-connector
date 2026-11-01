"""P7 Sandbox (TRD §2, §6): run one generated connector in its own process and collect its JSON lines.

The runner gets a minimal environment (no app settings, no vault key, no AI key) and the run's inputs on
stdin only. Its HTTP transport allows the spec's host alone: a call anywhere else ends the run with exit 8.
There is no OS isolation, so the screens label it "demo isolation only" (a locked container per run is on
the roadmap, PRD §13).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.errors import EXIT_TIMEOUT

BACKEND = Path(__file__).resolve().parents[2]
DEMO_ISOLATION_LABEL = "demo isolation only"
SANDBOX = "subprocess"
TIMEOUT_S = {"test": 120, "full": 1800}


@dataclass
class SandboxResult:
    exit_code: int
    lines: list[dict[str, Any]]
    sandbox: str = SANDBOX
    isolation_note: str | None = DEMO_ISOLATION_LABEL
    stderr: str = ""

    @property
    def result(self) -> dict[str, Any]:
        for line in reversed(self.lines):
            if line.get("type") == "result":
                return dict(line)
        return {"type": "result", "status": "error", "error_code": "INTERNAL", "summary": {}}

    @property
    def records(self) -> list[dict[str, Any]]:
        return [line["data"] for line in self.lines if line.get("type") == "record"]


def run_connector(
    code: str, payload: dict[str, Any], host: str, mode: str = "test", timeout_s: int | None = None
) -> SandboxResult:
    """Run generated `code` with `payload` (TRD §6 stdin). `host` is the resolved spec host."""
    timeout = timeout_s or TIMEOUT_S[mode]
    if payload.get("replay_file"):
        payload = {**payload, "replay_file": str(Path(payload["replay_file"]).resolve())}
    with tempfile.TemporaryDirectory(prefix="sbx-") as tmp:
        module = Path(tmp) / "connector.py"
        module.write_text(code)
        return _run(module, payload, mode, timeout)


def _parse(stdout: str) -> list[dict[str, Any]]:
    lines = []
    for raw in stdout.splitlines():
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue  # anything that isn't a JSON line is dropped, never shown
    return lines


def _run(module: Path, payload: dict[str, Any], mode: str, timeout: int) -> SandboxResult:
    # A minimal environment: no app settings, no VAULT_KEY, no LLM key. Only proxy and CA settings
    # pass through so live calls work on machines behind a proxy.
    # The runner needs the installed packages; on some hosts (Vercel) they live outside site-packages.
    python_path = os.pathsep.join([str(BACKEND), *(p for p in sys.path if p and os.path.isdir(p))])
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": python_path, "PYTHONDONTWRITEBYTECODE": "1"}
    for key in ("HTTPS_PROXY", "https_proxy", "SSL_CERT_FILE", "NO_PROXY", "no_proxy"):
        if key in os.environ:
            env[key] = os.environ[key]
    try:
        done = subprocess.run(
            [sys.executable, "-m", "runner", "--module", str(module), "--mode", mode],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=BACKEND,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        timed_out: dict[str, Any] = {"type": "result", "status": "error", "error_code": "TIMEOUT", "summary": {}}
        return SandboxResult(EXIT_TIMEOUT, [timed_out])
    return SandboxResult(done.returncode, _parse(done.stdout), stderr=done.stderr[-2000:])
