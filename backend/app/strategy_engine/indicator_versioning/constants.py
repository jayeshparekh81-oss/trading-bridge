"""Locked constants for indicator versioning.

Single tunable knobs for the initial-seed date, the engine version,
and the default schema version we record on a manifest. Keep this
module dependency-free.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

INITIAL_VERSION: Final[str] = "1.0.0"
"""Semver string assigned to every indicator at module-seed time. New
versions are added via :func:`registry.register_version` after a
formula or behaviour change."""

INITIAL_FORMULA_VERSION: Final[str] = "f1"
"""Internal calculation-version tag for the initial release. Bumped
to ``f2``, ``f3``, … when the calculation function changes in a way
that affects backtest output (numeric drift, new parameter, etc.)."""

INITIAL_CHANGELOG: Final[str] = "Initial release"
"""Text recorded against the seeded v1.0.0 entry for every indicator."""

INITIAL_VERSION_DATE: Final[datetime] = datetime(2026, 5, 5, tzinfo=UTC)
"""Locked timestamp on the seeded v1.0.0 entries. Real-world creation
times only show up on subsequent versions registered at runtime."""

ENGINE_VERSION: Final[str] = "1.0.0"
"""Backtest engine version recorded on every manifest. Bump on a
material change to the simulator / runner that would alter results
for the same strategy + candles."""

DEFAULT_SCHEMA_VERSION: Final[str] = "1"
"""Fallback ``StrategyJSON`` schema version when the caller does not
pass one explicitly. ``StrategyJSON.version`` is currently an ``int``
(defaults to ``1``); the manifest stores it as a string for forward
compatibility with semver-style schema bumps."""


__all__ = [
    "DEFAULT_SCHEMA_VERSION",
    "ENGINE_VERSION",
    "INITIAL_CHANGELOG",
    "INITIAL_FORMULA_VERSION",
    "INITIAL_VERSION",
    "INITIAL_VERSION_DATE",
]
