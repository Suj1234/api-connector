"""SSRF guard for the docs fetcher (TRD §8 P1).

http(s) only; no credentials in the URL; standard ports; no private, loopback, link-local, metadata
or otherwise non-public address, checked for every address a name resolves to, and again for every
redirect hop. Where this machine has no DNS and all traffic goes through an outbound proxy (some
cloud sandboxes), names are passed to the proxy, which resolves them and applies its own policy;
IP literals and internal names are still refused here.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

Resolver = Callable[[str], list[str]]

INTERNAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".svc", ".cluster.local")
METADATA_HOSTS = {"metadata.google.internal", "metadata", "instance-data"}


class SSRFBlockedError(ValueError):
    """The link points to a private or internal address (SSRF_BLOCKED)."""


def system_resolver(host: str) -> list[str]:
    return sorted({str(info[4][0]) for info in socket.getaddrinfo(host, None)})


def _behind_proxy() -> bool:
    return bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def check_url(url: str, resolver: Resolver | None = None) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise SSRFBlockedError("only http and https links are allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise SSRFBlockedError("the link has no host")
    if parts.username or parts.password:
        raise SSRFBlockedError("links with credentials are not allowed")
    if parts.port not in (None, 80, 443):
        raise SSRFBlockedError("only standard web ports are allowed")
    if host in ("localhost", *METADATA_HOSTS) or host.endswith(INTERNAL_SUFFIXES):
        raise SSRFBlockedError("internal host names are not allowed")
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not _public(str(literal)):
            raise SSRFBlockedError("private or internal address")
        return
    try:
        addresses = (resolver or system_resolver)(host)
    except OSError:
        if resolver is None and _behind_proxy():
            return  # the outbound proxy resolves and enforces; see module docstring
        raise SSRFBlockedError("the host name could not be resolved") from None
    if not addresses or not all(_public(a) for a in addresses):
        raise SSRFBlockedError("the host resolves to a private or internal address")
