"""Vercel entry point: the whole backend as one Python function (the UI is served as static files)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from app.api import app  # noqa: E402

__all__ = ["app"]
