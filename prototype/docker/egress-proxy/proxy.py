"""Allowlist CONNECT proxy: the sandbox's only route out (TRD §2).

One proxy per run. It allows `CONNECT <ALLOW_HOST>:443` and nothing else: no other host, no other
port, no plain HTTP. It never sees request contents (TLS stays end to end). Every decision is
logged as one JSON line, so a blocked attempt becomes a security event.

Env: ALLOW_HOST (required), PORT (default 3128), ALLOW_PRIVATE_IPS=1 (tests only: lets the allowed
host resolve to a private address, e.g. a fake API on a Docker network).
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import sys

ALLOW_HOST = os.environ.get("ALLOW_HOST", "").strip().lower()
PORT = int(os.environ.get("PORT", "3128"))
ALLOW_PRIVATE = os.environ.get("ALLOW_PRIVATE_IPS") == "1"
IDLE_SECONDS = 60


def log(**fields: object) -> None:
    print(json.dumps(fields), flush=True)


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await asyncio.wait_for(reader.read(65536), IDLE_SECONDS):
            writer.write(data)
            await writer.drain()
    except (TimeoutError, ConnectionError):
        pass
    finally:
        writer.close()


async def reply(writer: asyncio.StreamWriter, status: str) -> None:
    writer.write(f"HTTP/1.1 {status}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    writer.close()


def public_address(host: str) -> str | None:
    """Resolve once, check the address, and connect to that address (no DNS rebinding in between).

    Raises OSError when the name doesn't resolve; returns None when it resolves only to
    private or internal addresses (that one is a security event).
    """
    for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        address = str(info[4][0])
        ip = ipaddress.ip_address(address)
        if ALLOW_PRIVATE or ip.is_global:
            return address
    return None


async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        head = await asyncio.wait_for(client_reader.readuntil(b"\r\n\r\n"), 10)
    except (TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        client_writer.close()
        return
    method, _, rest = head.decode("latin-1").partition(" ")
    target = rest.split(" ", 1)[0]
    host, _, port = target.rpartition(":")
    host = host.strip("[]").lower()

    if method != "CONNECT":
        log(event="blocked", reason="not_connect", method=method)
        await reply(client_writer, "405 Method Not Allowed")
        return
    if host != ALLOW_HOST or port != "443":
        log(event="blocked", reason="host_not_allowed", host=host, port=port)
        await reply(client_writer, "403 Forbidden")
        return
    try:
        address = await asyncio.get_running_loop().run_in_executor(None, public_address, host)
    except OSError:
        log(event="error", reason="dns_failed", host=host)
        await reply(client_writer, "502 Bad Gateway")
        return
    if address is None:
        log(event="blocked", reason="no_public_address", host=host)
        await reply(client_writer, "403 Forbidden")
        return
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(address, 443), 10)
    except (OSError, TimeoutError):
        log(event="error", reason="connect_failed", host=host)
        await reply(client_writer, "502 Bad Gateway")
        return
    log(event="allowed", host=host)
    client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await client_writer.drain()
    await asyncio.gather(pipe(client_reader, upstream_writer), pipe(upstream_reader, client_writer))


async def main() -> None:
    if not ALLOW_HOST:
        print("ALLOW_HOST is required", file=sys.stderr)
        sys.exit(2)
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    log(event="ready", allow_host=ALLOW_HOST, port=PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
