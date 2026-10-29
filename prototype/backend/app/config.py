"""Settings from the environment, with prototype/.env as a fallback (TRD §2). Values are never printed."""

from __future__ import annotations

import os
from pathlib import Path

PROTOTYPE = Path(__file__).resolve().parents[2]
ENV_FILE = PROTOTYPE / ".env"
DOCS_CACHE = PROTOTYPE / "data" / "docs_cache"  # fetched public docs, shared by the benchmark and offline demos


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


def on_vercel() -> bool:
    return bool(os.environ.get("VERCEL"))


def writable_data_dir() -> Path:
    """prototype/data locally; /tmp on read-only hosts such as Vercel (not shared between instances)."""
    data = PROTOTYPE / "data"
    try:
        data.mkdir(parents=True, exist_ok=True)
        probe = data / ".write-test"
        probe.write_text("ok")
        probe.unlink()
        return data
    except OSError:
        tmp = Path("/tmp/integration-builder")
        tmp.mkdir(parents=True, exist_ok=True)
        return tmp


def database_url() -> str:
    """DATABASE_URL (or Vercel's POSTGRES_URL), else a local SQLite file."""
    url = get("DATABASE_URL") or get("POSTGRES_URL")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if not url or url.startswith("sqlite:///./"):
        name = url.removeprefix("sqlite:///./data/") if url else "app.db"
        url = f"sqlite:///{writable_data_dir() / name}"
    return url
