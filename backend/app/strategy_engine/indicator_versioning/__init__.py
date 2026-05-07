"""Indicator versioning — public boundary.

Tracks the version of every indicator referenced by a backtest so a
strategy that ran today can be replayed faithfully tomorrow against
the same calculation logic. Phase 1 is in-memory; the Friday DB
migration will swap a persistent store in behind the same API.

The version registry is **seeded on first import** with v1.0.0
records for every indicator in
:data:`app.strategy_engine.indicators.INDICATOR_REGISTRY` (105 entries
at the time of writing). Re-importing or re-running
``seed_initial_versions`` is idempotent.

Public surface::

    capture_manifest /
    register_version / get_current_version / list_all_versions /
    BacktestVersionManifest / IndicatorVersionRecord /
    UnknownIndicatorError
"""

from __future__ import annotations

from app.strategy_engine.indicator_versioning.manifest import capture_manifest
from app.strategy_engine.indicator_versioning.models import (
    BacktestVersionManifest,
    IndicatorVersionRecord,
)
from app.strategy_engine.indicator_versioning.registry import (
    UnknownIndicatorError,
    get_current_version,
    list_all_versions,
    register_version,
)
from app.strategy_engine.indicator_versioning.seed import seed_initial_versions

# Seed v1.0.0 entries for every known indicator on first import.
# Idempotent — re-importing the module won't duplicate history.
seed_initial_versions()


__all__ = [
    "BacktestVersionManifest",
    "IndicatorVersionRecord",
    "UnknownIndicatorError",
    "capture_manifest",
    "get_current_version",
    "list_all_versions",
    "register_version",
    "seed_initial_versions",
]
