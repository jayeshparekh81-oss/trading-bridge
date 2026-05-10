"""Thread-safe in-memory store for indicator version history.

A module-level ``dict[indicator_id -> list[IndicatorVersionRecord]]``
guarded by ``threading.Lock``. Each indicator's list is kept in
*reverse-chronological* order — index 0 is the latest version.

Reads (``get_current_version``, ``list_all_versions``) take the lock
only briefly to copy the relevant slice; the returned objects are
frozen Pydantic models so the caller can't mutate the registry by
accident.

Stdlib only by design — a future Friday phase will swap this
implementation with a DB-backed store while keeping the same call
sites in :mod:`manifest` unchanged.
"""

from __future__ import annotations

import threading

from app.strategy_engine.indicator_versioning.models import IndicatorVersionRecord


class UnknownIndicatorError(KeyError):
    """Raised when a caller asks about an indicator that has no
    registered versions. Subclasses :class:`KeyError` so existing
    dict-style miss handling still works."""


_lock = threading.Lock()
_versions: dict[str, list[IndicatorVersionRecord]] = {}


def register_version(record: IndicatorVersionRecord) -> None:
    """Add ``record`` as the new latest version for its indicator.

    If a record for the same ``(indicator_id, version)`` already
    exists, this is a no-op — re-seeding on import must be idempotent
    so the tests can call ``seed_initial_versions`` repeatedly without
    polluting the history.
    """
    with _lock:
        history = _versions.setdefault(record.indicator_id, [])
        for existing in history:
            if existing.version == record.version:
                return
        history.insert(0, record)


def get_current_version(indicator_id: str) -> IndicatorVersionRecord:
    """Return the latest non-deprecated record for ``indicator_id``.

    Falls back to the latest deprecated record if every version has
    been deprecated — the caller still gets *something* to anchor a
    manifest against, plus the ``deprecated=True`` flag they can
    surface to the user.

    Raises:
        UnknownIndicatorError: if no version has ever been registered
            for ``indicator_id``.
    """
    with _lock:
        history = _versions.get(indicator_id)
        if not history:
            raise UnknownIndicatorError(f"no versions registered for indicator {indicator_id!r}")
        for record in history:
            if not record.deprecated:
                return record
        return history[0]


def list_all_versions(indicator_id: str) -> list[IndicatorVersionRecord]:
    """Return every recorded version for ``indicator_id``, newest
    first. The returned list is a fresh copy — mutating it has no
    effect on the registry.

    Raises:
        UnknownIndicatorError: if no version has ever been registered
            for ``indicator_id``.
    """
    with _lock:
        history = _versions.get(indicator_id)
        if history is None:
            raise UnknownIndicatorError(f"no versions registered for indicator {indicator_id!r}")
        return list(history)


def known_indicators() -> tuple[str, ...]:
    """Return every indicator id that has at least one registered
    version. Used by tests + the future DB migration to enumerate the
    in-memory state."""
    with _lock:
        return tuple(_versions.keys())


def clear() -> None:
    """Empty the registry. Intended for tests only — production code
    should never need to wipe version history."""
    with _lock:
        _versions.clear()


__all__ = [
    "UnknownIndicatorError",
    "clear",
    "get_current_version",
    "known_indicators",
    "list_all_versions",
    "register_version",
]
