"""Thread-safe in-memory store for runtime flag overrides.

A module-level ``dict[str, bool]`` guarded by a ``threading.Lock``.
Reads (``get``, ``contains``) are lock-free — atomic dict lookups in
CPython under the GIL. Writes (``set``, ``remove``, ``clear``) take
the lock so two concurrent ``set_flag`` calls can't tear the dict.

Stdlib only. A future phase will swap this implementation with a
DB-backed store while keeping the same call sites in :mod:`manager`
unchanged.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_overrides: dict[str, bool] = {}


def get(flag_name: str) -> bool | None:
    """Return the runtime override for ``flag_name`` or ``None`` if
    no override has been set."""
    return _overrides.get(flag_name)


def contains(flag_name: str) -> bool:
    """Return ``True`` if a runtime override exists for ``flag_name``."""
    return flag_name in _overrides


def set_value(flag_name: str, enabled: bool) -> None:
    """Record a runtime override for ``flag_name``."""
    with _lock:
        _overrides[flag_name] = enabled


def remove(flag_name: str) -> None:
    """Drop the runtime override for ``flag_name`` if one exists.
    Idempotent — calling on a flag without an override is a no-op."""
    with _lock:
        _overrides.pop(flag_name, None)


def clear() -> None:
    """Empty the override map. Intended for tests only."""
    with _lock:
        _overrides.clear()


def snapshot() -> dict[str, bool]:
    """Return a shallow copy of the current overrides."""
    with _lock:
        return dict(_overrides)


__all__ = [
    "clear",
    "contains",
    "get",
    "remove",
    "set_value",
    "snapshot",
]
