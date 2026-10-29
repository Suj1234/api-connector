"""Milestone 3 done-criteria: a call to another host fails with exit code 8; no secret in any log.

Docker tests run the real images (integration-runner:dev, integration-egress:dev) and skip when
Docker or the images aren't there. The subprocess fallback is always tested.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.services.codegen import render
from app.services.sandbox import DEMO_ISOLATION_LABEL, EGRESS_IMAGE, docker_available, run_connector
from tests.conftest import REPLAY, base_spec, example_spec

HERE = Path(__file__).resolve().parent
TOKEN = "sandbox-secret-token-42"
needs_docker = pytest.mark.skipif(not docker_available(), reason="Docker or the sandbox images are not available")


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


def assert_no_secret(*texts: str) -> None:
    for text in texts:
        assert TOKEN not in text
        assert "replay-demo" not in text


# --- subprocess fallback --------------------------------------------------------------


def test_subprocess_blocks_another_host_with_exit_8(tmp_path: Path) -> None:
    payload = {"run_mode": "replay", "replay_file": str(evil_recording(tmp_path))}
    result = run_connector(next_url_code(), payload, "api.example.com", sandbox="subprocess")
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
    result = run_connector(code, {"run_mode": "live", "secrets": {}}, "api.example.com", sandbox="subprocess")
    env_names = result.lines[0]["env"]
    assert "VAULT_KEY" not in env_names and "GEMINI_API_KEY" not in env_names


def test_subprocess_replay_runs_the_demo(tmp_path: Path) -> None:
    payload = {"run_mode": "replay", "replay_file": str(REPLAY / "calendly" / "recording.json")}
    result = run_connector(render(example_spec("calendly")), payload, "api.calendly.com", sandbox="subprocess")
    assert result.exit_code == 0 and len(result.records) == 48


# --- docker: replay has no network at all ------------------------------------------------


@needs_docker
def test_docker_replay_runs_the_demo_without_network() -> None:
    payload = {"run_mode": "replay", "replay_file": str(REPLAY / "zendesk" / "recording.json")}
    result = run_connector(render(example_spec("zendesk")), payload, "acme-demo.zendesk.com", sandbox="docker")
    assert result.exit_code == 0, result.stderr
    assert len(result.records) == 37
    assert_no_secret(json.dumps(result.lines), result.stderr)


@needs_docker
def test_docker_blocks_another_host_with_exit_8(tmp_path: Path) -> None:
    payload = {"run_mode": "replay", "replay_file": str(evil_recording(tmp_path))}
    result = run_connector(next_url_code(), payload, "api.example.com", sandbox="docker")
    assert result.exit_code == 8 and result.result["error_code"] == "HOST_BLOCKED"


@needs_docker
def test_docker_container_has_no_way_out_even_for_raw_sockets() -> None:
    """Code that skips httpx entirely still can't reach anything from a replay sandbox."""
    code = (
        "import json, socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 443), timeout=3)\n"
        "    out = 'connected'\n"
        "except OSError as e:\n"
        "    out = type(e).__name__\n"
        "print(json.dumps({'type': 'result', 'status': 'ok', 'raw': out}))\n"
    )
    result = run_connector(
        code, {"run_mode": "replay", "replay_file": str(REPLAY / "notion" / "recording.json")}, "x.example.com"
    )
    assert result.lines[0]["raw"] != "connected"


# --- docker live: the per-run egress proxy ---------------------------------------------------


def self_signed(tmp: Path) -> Path:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "api.example.com")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("api.example.com")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    (tmp / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (tmp / "key.pem").write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    (tmp / "fake_api.py").write_text((HERE / "fake_api.py").read_text())
    for f in tmp.iterdir():
        f.chmod(0o644)
    tmp.chmod(0o755)
    return tmp / "cert.pem"


@pytest.fixture
def fake_api(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """api.example.com on a Docker network that only the egress proxy joins."""
    network, name = f"sbx-test-out-{uuid.uuid4().hex[:8]}", f"sbx-fakeapi-{uuid.uuid4().hex[:8]}"
    cert = self_signed(tmp_path)
    subprocess.run(["docker", "network", "create", network], check=True, capture_output=True)
    subprocess.run(
        ["docker", "run", "-d", "--name", name, "--network", network, "--network-alias", "api.example.com",
         "--user", "0", "-v", f"{tmp_path}:/srv:ro", "--entrypoint", "python", EGRESS_IMAGE, "/srv/fake_api.py"],
        check=True, capture_output=True,
    )  # fmt: skip
    time.sleep(1.5)
    try:
        yield network, cert
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)


@pytest.mark.skipif(not docker_available(), reason="Docker or the sandbox images are not available")
def test_docker_live_reaches_only_its_host_through_the_egress_proxy(fake_api: tuple[str, Path]) -> None:
    network, cert = fake_api
    payload: dict[str, Any] = {"run_mode": "live", "secrets": {"token": TOKEN}, "context": {"tenant": "acme"}}
    code = render(base_spec(), 1)
    result = run_connector(code, payload, "api.example.com", egress_network=network, extra_ca_file=str(cert))
    assert result.exit_code == 0, (result.result, result.stderr, result.egress_log)
    assert len(result.records) == 3
    assert {"event": "allowed", "host": "api.example.com"} in result.egress_log
    assert_no_secret(json.dumps(result.lines), result.stderr, json.dumps(result.egress_log))


@pytest.mark.skipif(not docker_available(), reason="Docker or the sandbox images are not available")
def test_docker_live_proxy_refuses_other_hosts_even_without_httpx(fake_api: tuple[str, Path]) -> None:
    """Hand-written code that asks the proxy for another host directly is refused (403) and logged."""
    network, cert = fake_api
    code = (
        "import json, os, socket\n"
        "proxy = os.environ['HTTPS_PROXY'].split('//')[1]\n"
        "host, port = proxy.split(':')\n"
        "s = socket.create_connection((host, int(port)), timeout=5)\n"
        "s.sendall(b'CONNECT evil.example.net:443 HTTP/1.1\\r\\nHost: evil.example.net\\r\\n\\r\\n')\n"
        "answer = s.recv(100).decode()\n"
        "try:\n"
        "    socket.create_connection(('api.example.com', 443), timeout=3)\n"
        "    direct = 'connected'\n"
        "except OSError as e:\n"
        "    direct = type(e).__name__\n"
        "print(json.dumps({'type': 'result', 'status': 'ok', 'proxy': answer.split('\\r\\n')[0], 'direct': direct}))\n"
    )
    result = run_connector(code, {"run_mode": "live", "secrets": {}}, "api.example.com", egress_network=network)
    line = result.lines[0]
    assert line["proxy"].startswith("HTTP/1.1 403")
    assert line["direct"] != "connected"  # the internal network has no route to the API either
    assert any(e.get("host") == "evil.example.net" for e in result.blocked_calls)
