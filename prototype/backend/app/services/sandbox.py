"""P7 Sandbox (TRD §2, §6): run one generated connector, isolated, and collect its JSON lines.

docker (default):
  - replay: the runner container has no network at all.
  - live: the runner sits on an internal network whose only exit is a per-run egress proxy that
    allows CONNECT to the spec's host only. Read-only root, tmpfs /tmp, 256 MB, 0.5 CPU, 64 pids.
subprocess (fallback): same runner and host lock, no OS isolation. Shown as "demo isolation only".

Secrets go to the runner on stdin only: never in env vars, files, image layers or logs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.errors import EXIT_TIMEOUT

BACKEND = Path(__file__).resolve().parents[2]
RUNNER_IMAGE = os.environ.get("SANDBOX_RUNNER_IMAGE", "integration-runner:dev")
EGRESS_IMAGE = os.environ.get("SANDBOX_EGRESS_IMAGE", "integration-egress:dev")
DEMO_ISOLATION_LABEL = "demo isolation only"
TIMEOUT_S = {"test": 120, "full": 1800}
DOCKER_LIMITS = [
    "--read-only",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=16m",
    "--memory",
    "256m",
    "--cpus",
    "0.5",
    "--pids-limit",
    "64",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
]


@dataclass
class SandboxResult:
    exit_code: int
    lines: list[dict[str, Any]]
    sandbox: str
    isolation_note: str | None = None
    egress_log: list[dict[str, Any]] = field(default_factory=list)
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

    @property
    def blocked_calls(self) -> list[dict[str, Any]]:
        return [e for e in self.egress_log if e.get("event") == "blocked"]


def source_fingerprint() -> str:
    """Hash of the code baked into the runner image; a stale image must never run silently."""
    import hashlib

    digest = hashlib.sha256()
    files = sorted([*(BACKEND / "runtime").glob("*.py"), *(BACKEND / "runner").glob("*.py")])
    files.append(BACKEND / "app" / "models" / "canonical.py")
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


class StaleImageError(RuntimeError):
    pass


def image_fingerprint() -> str | None:
    done = _docker("image", "inspect", "--format", '{{ index .Config.Labels "source_fingerprint" }}', RUNNER_IMAGE)
    return done.stdout.strip() or None if done.returncode == 0 else None


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        done = subprocess.run(
            ["docker", "image", "inspect", RUNNER_IMAGE], capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def run_connector(
    code: str,
    payload: dict[str, Any],
    host: str,
    mode: str = "test",
    sandbox: str = "docker",
    timeout_s: int | None = None,
    egress_network: str = "bridge",
    extra_ca_file: str | None = None,
) -> SandboxResult:
    """Run generated `code` with `payload` (TRD §6 stdin). `host` is the resolved spec host."""
    timeout = timeout_s or TIMEOUT_S[mode]
    if payload.get("replay_file"):
        payload = {**payload, "replay_file": str(Path(payload["replay_file"]).resolve())}
    with tempfile.TemporaryDirectory(prefix="sbx-") as tmp:
        work = Path(tmp)
        os.chmod(work, 0o755)
        module = work / "connector.py"
        module.write_text(code)
        os.chmod(module, 0o644)
        if sandbox == "docker":
            if image_fingerprint() != source_fingerprint():
                raise StaleImageError("The sandbox image is out of date with the runtime code: run docker/build.sh")
            return _run_docker(work, payload, host, mode, timeout, egress_network, extra_ca_file)
        return _run_subprocess(module, payload, mode, timeout)


def _parse(stdout: str) -> list[dict[str, Any]]:
    lines = []
    for raw in stdout.splitlines():
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue  # anything that isn't a JSON line is dropped, never shown
    return lines


def _timeout_result(sandbox: str, note: str | None) -> SandboxResult:
    timed_out: dict[str, Any] = {"type": "result", "status": "error", "error_code": "TIMEOUT", "summary": {}}
    return SandboxResult(EXIT_TIMEOUT, [timed_out], sandbox, note)


# --- subprocess fallback --------------------------------------------------------------


def _run_subprocess(module: Path, payload: dict[str, Any], mode: str, timeout: int) -> SandboxResult:
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
        return _timeout_result("subprocess", DEMO_ISOLATION_LABEL)
    return SandboxResult(
        done.returncode, _parse(done.stdout), "subprocess", DEMO_ISOLATION_LABEL, stderr=done.stderr[-2000:]
    )


# --- docker -----------------------------------------------------------------------------


def _docker(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)


def _wait_for_proxy(name: str, seconds: float = 10.0) -> None:
    """The runner must not start before the proxy listens, or its first call fails."""
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if any(line.get("event") == "ready" for line in _parse(_docker("logs", name).stdout)):
            return
        time.sleep(0.1)
    raise RuntimeError("the egress proxy did not start")


def _run_docker(
    work: Path,
    payload: dict[str, Any],
    host: str,
    mode: str,
    timeout: int,
    egress_network: str,
    extra_ca_file: str | None,
) -> SandboxResult:
    run_id = uuid.uuid4().hex[:12]
    runner_name, proxy_name, network = f"sbx-run-{run_id}", f"sbx-egress-{run_id}", f"sbx-net-{run_id}"
    payload = dict(payload)
    mounts = ["-v", f"{work}:/work:ro"]
    env: list[str] = []
    live = payload.get("run_mode", "live") == "live"

    if not live:
        replay_file = Path(payload["replay_file"]).resolve()
        mounts += ["-v", f"{replay_file}:/replay/recording.json:ro"]
        payload["replay_file"] = "/replay/recording.json"
    if extra_ca_file:
        mounts += ["-v", f"{Path(extra_ca_file).resolve()}:/certs/ca.pem:ro"]
        env += ["-e", "SSL_CERT_FILE=/certs/ca.pem"]

    egress_log: list[dict[str, Any]] = []
    try:
        if live:
            _docker("network", "create", "--internal", network).check_returncode()
            _docker(
                "run", "-d", "--name", proxy_name, "--network", egress_network,
                "-e", f"ALLOW_HOST={host}", *(["-e", "ALLOW_PRIVATE_IPS=1"] if egress_network != "bridge" else []),
                "--read-only", "--memory", "64m", "--cpus", "0.25", "--pids-limit", "32", "--cap-drop", "ALL",
                EGRESS_IMAGE,
            ).check_returncode()  # fmt: skip
            _docker("network", "connect", network, proxy_name).check_returncode()
            _wait_for_proxy(proxy_name)
            net_args = ["--network", network, "-e", f"HTTPS_PROXY=http://{proxy_name}:3128"]
        else:
            net_args = ["--network", "none"]

        command = [
            "docker", "run", "--rm", "-i", "--name", runner_name, *DOCKER_LIMITS, *net_args, *env, *mounts,
            RUNNER_IMAGE, "--module", "/work/connector.py", "--mode", mode,
        ]  # fmt: skip
        try:
            done = subprocess.run(
                command, input=json.dumps(payload), capture_output=True, text=True, timeout=timeout + 15, check=False
            )
        except subprocess.TimeoutExpired:
            _docker("kill", runner_name)
            return _timeout_result("docker", None)
        if live:
            egress_log = _parse(_docker("logs", proxy_name).stdout)
        return SandboxResult(done.returncode, _parse(done.stdout), "docker", None, egress_log, done.stderr[-2000:])
    finally:
        if live:
            _docker("rm", "-f", proxy_name)
            _docker("network", "rm", network)
