"""Locked constants for strategy versioning.

Single tunable knobs for the on-disk cache directory, the first
version number, the per-strategy retention cap, and the lock-acquire
timeout. Keep this module dependency-free so it can be imported by
``models.py`` and ``store.py`` without cycles.
"""

from __future__ import annotations

from typing import Final

CACHE_DIR_NAME: Final[str] = "strategy_versions"
"""Sub-directory under ``~/.cache/tradetri/`` that holds one folder
per strategy. Each strategy folder contains ``v{N}.json`` files, one
per version. The Phase 3 DB migration will swap this for a Postgres
table while keeping the public API stable."""

INITIAL_VERSION_NUMBER: Final[int] = 1
"""Version number assigned to the first :class:`StrategyVersion`
created for a strategy. Subsequent versions monotonically increase by
one (no gaps)."""

MAX_VERSIONS_KEPT: Final[int] = 100
"""Soft cap on retained history per strategy. The Phase 1 store does
not actively prune — this constant is exposed for the Phase 3 DB
migration to enforce. Tests assert it is defined and >= 1 so future
pruning code has a known contract to honour."""

LOCK_TIMEOUT_SECONDS: Final[float] = 5.0
"""Wall-clock timeout for ``threading.Lock.acquire`` calls inside the
store. Above this the operation raises ``TimeoutError`` rather than
deadlocking the caller. Phase 1 contention is rare (one writer per
strategy edit) so a generous five-second window is fine."""


__all__ = [
    "CACHE_DIR_NAME",
    "INITIAL_VERSION_NUMBER",
    "LOCK_TIMEOUT_SECONDS",
    "MAX_VERSIONS_KEPT",
]
