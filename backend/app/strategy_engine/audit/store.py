"""Thread-safe in-memory ring buffer for audit events.

A module-level ``deque(maxlen=MAX_EVENTS_IN_MEMORY)`` guarded by a
``threading.Lock``. The lock is held only for the duration of a single
append / snapshot / clear — never across user code — so contention
stays bounded.

This module is intentionally dependency-free (stdlib only). A future
phase will swap this implementation with a DB-backed store while
keeping the same call sites in :mod:`emitter` unchanged.
"""

from __future__ import annotations

import threading
from collections import deque

from app.strategy_engine.audit.constants import MAX_EVENTS_IN_MEMORY
from app.strategy_engine.audit.models import AuditEvent

_lock = threading.Lock()
_events: deque[AuditEvent] = deque(maxlen=MAX_EVENTS_IN_MEMORY)


def append(event: AuditEvent) -> None:
    """Append ``event`` to the ring buffer.

    When the buffer is at capacity, the oldest event is evicted to
    make room for the newest. The deque mutation is atomic under the
    GIL but the lock makes the operation safe against future
    refactors that touch multiple fields together.
    """
    with _lock:
        _events.append(event)


def snapshot() -> tuple[AuditEvent, ...]:
    """Return a frozen snapshot of every event currently buffered.

    The returned tuple is decoupled from the underlying deque, so
    further appends won't change what the caller sees. Events are
    ordered oldest → newest (insertion order).
    """
    with _lock:
        return tuple(_events)


def size() -> int:
    """Return the current number of buffered events."""
    with _lock:
        return len(_events)


def clear() -> None:
    """Empty the buffer. Intended for tests only."""
    with _lock:
        _events.clear()


__all__ = [
    "append",
    "clear",
    "size",
    "snapshot",
]
