"""Background jobs with an in-memory event log per connector, streamed to the UI over SSE."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._events: dict[int, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def emit(self, connector_id: int, event: dict[str, Any]) -> None:
        with self._lock:
            log = self._events.setdefault(connector_id, [])
            log.append({**event, "seq": len(log)})

    def since(self, connector_id: int, seq: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events.get(connector_id, [])[seq:])

    def reset(self, connector_id: int) -> None:
        with self._lock:
            self._events[connector_id] = []


def run_in_background(target: Callable[[], None]) -> threading.Thread:
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread
