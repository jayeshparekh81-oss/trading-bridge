"""File-based version store for strategy snapshots.

Phase-1 persistence layer. One JSON file per version, atomically
written via ``tmp + os.replace``, plus an in-process cache rebuilt on
first read so subsequent calls do not hit the disk.

Layout::

    ~/.cache/tradetri/strategy_versions/
        {strategy_id}/
            v1.json
            v2.json
            ...

Thread safety is provided by a single module-level :class:`threading.Lock`.
The lock is held for *every* mutation and during cache hydration; reads
that hit a hot cache also briefly take the lock to copy the entries
out so the caller can never observe a torn list.

The Phase-3 DB migration will replace the disk + cache pair with a
SQL store while keeping :func:`save_version`, :func:`load_version`,
and :func:`load_all_versions` signatures stable.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from app.strategy_engine.strategy_versioning.constants import (
    CACHE_DIR_NAME,
    LOCK_TIMEOUT_SECONDS,
)
from app.strategy_engine.strategy_versioning.models import StrategyVersion


class VersionStoreError(RuntimeError):
    """Raised when the store cannot fulfil a read or write — disk
    error, lock timeout, or corrupt file. Wraps the underlying cause
    so callers get one exception type to handle."""


_lock = threading.RLock()
_cache: dict[UUID, dict[int, StrategyVersion]] = {}
_hydrated_strategies: set[UUID] = set()
_base_dir_override: Path | None = None


def _base_dir() -> Path:
    """Return the root directory for version files.

    Honours an explicit override (set by tests via :func:`set_base_dir`)
    before falling back to the production location under the user's
    cache directory. The override mechanism is the only sanctioned way
    to redirect storage; production code never calls it.
    """
    if _base_dir_override is not None:
        return _base_dir_override
    return Path.home() / ".cache" / "tradetri" / CACHE_DIR_NAME


def set_base_dir(path: Path | None) -> None:
    """Override (or clear) the base directory. Tests use this to point
    the store at a temporary directory; production code should never
    call it. Resets the in-memory cache so the next read re-hydrates
    from the new location."""
    global _base_dir_override
    with _acquire():
        _base_dir_override = path
        _cache.clear()
        _hydrated_strategies.clear()


def _acquire() -> _LockGuard:
    """Acquire the module lock with the configured timeout. Returns a
    context manager so callers can use a ``with`` block."""
    return _LockGuard(_lock)


def lock() -> _LockGuard:
    """Public re-entrant lock context manager.

    The manager wraps a read-then-write sequence (compute the next
    version number, then save) inside ``with lock():`` so concurrent
    creators on the same strategy can't allocate duplicate version
    numbers. Backed by :class:`threading.RLock`, so nested calls from
    inside the block (``save_version``, ``load_all_versions``) re-take
    the lock without deadlocking.
    """
    return _LockGuard(_lock)


class _LockGuard:
    """Thin wrapper around ``threading.RLock.acquire(timeout=...)`` that
    raises a clear :class:`VersionStoreError` on timeout instead of
    returning ``False`` silently."""

    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock

    def __enter__(self) -> None:
        if not self._lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
            raise VersionStoreError(
                f"could not acquire version-store lock within {LOCK_TIMEOUT_SECONDS}s"
            )

    def __exit__(self, *exc_info: Any) -> None:
        self._lock.release()


def _strategy_dir(strategy_id: UUID) -> Path:
    return _base_dir() / str(strategy_id)


def _version_path(strategy_id: UUID, version_number: int) -> Path:
    return _strategy_dir(strategy_id) / f"v{version_number}.json"


def _hydrate_locked(strategy_id: UUID) -> None:
    """Populate the cache for ``strategy_id`` from disk. Caller must
    already hold the lock."""
    if strategy_id in _hydrated_strategies:
        return
    bucket = _cache.setdefault(strategy_id, {})
    folder = _strategy_dir(strategy_id)
    if folder.is_dir():
        for path in folder.glob("v*.json"):
            try:
                raw = path.read_text(encoding="utf-8")
                version = StrategyVersion.model_validate_json(raw)
            except (OSError, ValueError) as exc:
                raise VersionStoreError(f"cannot read {path.name}: {exc}") from exc
            bucket[version.version_number] = version
    _hydrated_strategies.add(strategy_id)


def _atomic_write(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` atomically. The temp file lives
    in the same directory so ``os.replace`` is a same-filesystem move
    and therefore atomic on POSIX."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        # Best-effort cleanup so we don't leave .tmp files lying around.
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise VersionStoreError(f"failed to write {path.name}: {exc}") from exc


def save_version(version: StrategyVersion) -> None:
    """Persist ``version`` to disk and the in-memory cache.

    Writes are atomic — readers either see the previous version or
    the new one, never a half-written file. Re-saving the same
    ``(strategy_id, version_number)`` overwrites the prior file; the
    manager guarantees uniqueness so this branch only fires from
    explicit roll-forward use cases (none in Phase 1).
    """
    payload = version.model_dump_json()
    with _acquire():
        path = _version_path(version.strategy_id, version.version_number)
        _atomic_write(path, payload)
        bucket = _cache.setdefault(version.strategy_id, {})
        bucket[version.version_number] = version
        _hydrated_strategies.add(version.strategy_id)


def load_version(strategy_id: UUID, version_number: int) -> StrategyVersion | None:
    """Return the cached/persisted version, or ``None`` if absent."""
    with _acquire():
        _hydrate_locked(strategy_id)
        return _cache.get(strategy_id, {}).get(version_number)


def load_all_versions(strategy_id: UUID) -> list[StrategyVersion]:
    """Return every stored version for ``strategy_id`` ordered by
    ``version_number`` ascending. Returns an empty list when the
    strategy has no history."""
    with _acquire():
        _hydrate_locked(strategy_id)
        bucket = _cache.get(strategy_id, {})
        return [bucket[n] for n in sorted(bucket.keys())]


def next_version_number(strategy_id: UUID) -> int:
    """Return the next monotonically-increasing version number for
    ``strategy_id``. ``1`` for a fresh strategy."""
    with _acquire():
        _hydrate_locked(strategy_id)
        bucket = _cache.get(strategy_id, {})
        if not bucket:
            return 1
        return max(bucket.keys()) + 1


def reset() -> None:
    """Clear the in-memory cache. Intended for tests — does **not**
    delete files on disk. Combine with :func:`set_base_dir` pointing
    at a fresh tmp path to get a fully clean slate."""
    with _acquire():
        _cache.clear()
        _hydrated_strategies.clear()


def serialise(version: StrategyVersion) -> str:
    """Public helper used by the manager to JSON-encode a version
    without re-implementing Pydantic-aware serialisation."""
    return version.model_dump_json()


def deserialise(raw: str) -> StrategyVersion:
    """Inverse of :func:`serialise` — used by tests that want to
    bypass the disk and exercise the model directly."""
    try:
        return StrategyVersion.model_validate_json(raw)
    except ValueError as exc:
        raise VersionStoreError(f"invalid stored version JSON: {exc}") from exc


def _ensure_json_safe(payload: dict[str, Any]) -> None:
    """Sanity-check that ``payload`` is JSON-serialisable. Saves us a
    confusing ``TypeError`` deep inside Pydantic at write time when a
    caller hands us a dict containing, say, a datetime. Pydantic's
    JSON encoder handles many such types, so this is a fast no-op
    check used only by the manager before persistence."""
    try:
        json.dumps(payload, default=str)
    except (TypeError, ValueError) as exc:
        raise VersionStoreError(f"strategy_json is not JSON-safe: {exc}") from exc


__all__ = [
    "VersionStoreError",
    "_ensure_json_safe",
    "deserialise",
    "load_all_versions",
    "load_version",
    "lock",
    "next_version_number",
    "reset",
    "save_version",
    "serialise",
    "set_base_dir",
]
