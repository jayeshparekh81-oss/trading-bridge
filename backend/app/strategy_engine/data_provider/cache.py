"""File-based cache for fetched Dhan candles.

A pragmatic on-disk JSON store keyed on the exact request shape
(symbol, timeframe, from-date, to-date). Cache entries are
self-describing — each file holds the candle payload plus the
``fetched_at`` timestamp the entry was written, and the reader gates
freshness against the configured TTL.

Locations: ``/tmp/{CACHE_DIR_NAME}`` when ``/tmp`` is writable;
otherwise ``~/.cache/{CACHE_DIR_NAME}``. The directory is created on
first use.

The store is intentionally process-local — multiple workers each
maintain their own cache. The Friday DB phase will swap a shared
cache in behind the same call sites.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.strategy_engine.data_provider.constants import (
    CACHE_DIR_NAME,
    CACHE_TTL_HISTORICAL_HOURS,
    CACHE_TTL_RECENT_HOURS,
    RECENT_DATA_THRESHOLD_DAYS,
)


def cache_root() -> Path:
    """Return the cache directory, creating it if missing.

    ``/tmp`` is the preferred location (process-isolated, world-
    writable); falls back to the user's cache directory when ``/tmp``
    is read-only or absent. The directory is created with mode 0o700
    so cache contents stay private to the running user.
    """
    candidates: list[Path] = []
    tmp = tempfile.gettempdir()
    if tmp:
        candidates.append(Path(tmp) / CACHE_DIR_NAME)
    home = Path.home() if Path.home() != Path(".") else None
    if home is not None:
        candidates.append(home / ".cache" / CACHE_DIR_NAME)

    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Touch a probe file to verify writability. Cheap; if it
            # fails we fall through to the next candidate.
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue

    raise RuntimeError("Cannot find a writable cache directory; tried /tmp and ~/.cache.")


def _safe_filename_part(value: str) -> str:
    """Sanitise a value for use inside a filename.

    Replaces characters that confuse filesystems (path separators,
    colon, whitespace) with hyphens. Keeps cache filenames portable
    across macOS/Linux/Windows.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "-", value)


def cache_key(symbol: str, timeframe: str, from_date: datetime, to_date: datetime) -> str:
    """Build the cache filename for one ``(symbol, timeframe, range)``."""
    return (
        f"{_safe_filename_part(symbol)}_"
        f"{_safe_filename_part(timeframe)}_"
        f"{_safe_filename_part(from_date.isoformat())}_"
        f"{_safe_filename_part(to_date.isoformat())}.json"
    )


def _ttl_for(to_date: datetime) -> timedelta:
    """Pick the appropriate TTL based on how recent the requested
    window is. ``to_date`` within the last
    :data:`RECENT_DATA_THRESHOLD_DAYS` ⇒ short TTL; older ⇒ long TTL."""
    now = datetime.now(UTC)
    age = now - to_date
    if age <= timedelta(days=RECENT_DATA_THRESHOLD_DAYS):
        return timedelta(hours=CACHE_TTL_RECENT_HOURS)
    return timedelta(hours=CACHE_TTL_HISTORICAL_HOURS)


def cache_get(
    symbol: str,
    timeframe: str,
    from_date: datetime,
    to_date: datetime,
) -> dict[str, Any] | None:
    """Read the cached payload for ``(symbol, timeframe, range)``.

    Returns ``None`` when the entry is absent, malformed, or older
    than the TTL. A malformed file is not an error — the cache is
    advisory; the fetcher will simply re-fetch.
    """
    path = cache_root() / cache_key(symbol, timeframe, from_date, to_date)
    if not path.exists():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    fetched_at_raw = envelope.get("fetched_at")
    if not isinstance(fetched_at_raw, str):
        return None
    try:
        fetched_at = datetime.fromisoformat(fetched_at_raw)
    except ValueError:
        return None
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    ttl = _ttl_for(to_date)
    if datetime.now(UTC) - fetched_at > ttl:
        return None

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        return None
    return payload


def cache_put(
    symbol: str,
    timeframe: str,
    from_date: datetime,
    to_date: datetime,
    payload: dict[str, Any],
) -> None:
    """Write ``payload`` to the cache for ``(symbol, timeframe,
    range)``. Best-effort: an OS-level write failure is logged
    upstream but never raised — the cache is advisory."""
    envelope = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    path = cache_root() / cache_key(symbol, timeframe, from_date, to_date)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(json.dumps(envelope), encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError:
        # Best-effort — drop the partial file so the next read sees
        # the previous (still valid) entry, if any.
        tmp_path.unlink(missing_ok=True)


def clear() -> None:
    """Delete every cached entry. Intended for tests only."""
    root = cache_root()
    if not root.exists():
        return
    for entry in root.iterdir():
        if entry.is_file():
            entry.unlink(missing_ok=True)


__all__ = [
    "cache_get",
    "cache_key",
    "cache_put",
    "cache_root",
    "clear",
]
