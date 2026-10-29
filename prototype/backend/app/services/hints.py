"""Admin hint scrubbing (TRD §8.1): a hint reaches the LLM only after this."""

from __future__ import annotations

import re
from collections.abc import Iterable

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_WITH_QUERY = re.compile(r"https?://\S+\?\S*")
LONG_DIGITS = re.compile(r"\d{6,}")
MAX_CHARS = 500


def scrub_hint(text: str, secrets: Iterable[str] = (), user_names: Iterable[str] = ()) -> str:
    text = EMAIL.sub("[email]", text)
    text = URL_WITH_QUERY.sub("[link]", text)
    text = LONG_DIGITS.sub("[number]", text)
    for secret in (s for s in secrets if s and len(s) >= 4):
        text = text.replace(secret, "[secret]")
    words = {w.lower() for name in user_names for w in re.findall(r"[A-Za-z][A-Za-z'-]{1,}", name or "")}
    if words:
        text = re.sub(
            r"[A-Za-z][A-Za-z'-]{1,}", lambda m: "[name]" if m.group(0).lower() in words else m.group(0), text
        )
    return text[:MAX_CHARS]
