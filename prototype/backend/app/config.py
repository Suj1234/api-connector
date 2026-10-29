"""Settings from the environment, with prototype/.env as a fallback (TRD §2). Values are never printed."""

from __future__ import annotations

import os
from pathlib import Path

PROTOTYPE = Path(__file__).resolve().parents[2]
ENV_FILE = PROTOTYPE / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    """Fill os.environ from .env without overriding variables that are already set."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


def get(key: str, default: str = "") -> str:
    load_env()
    return os.environ.get(key, default)
