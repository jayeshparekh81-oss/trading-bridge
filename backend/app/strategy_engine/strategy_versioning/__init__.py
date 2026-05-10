"""Strategy versioning — public boundary.

Tracks every saved version of every strategy so users can edit,
compare, and roll back. Phase 1 ships an in-memory cache backed by
file-based persistence under ``~/.cache/tradetri/strategy_versions/``;
the Phase 3 migration will swap this for a SQL store while keeping
the surface below unchanged.

Public surface::

    create_version /
    get_version / get_latest_version / list_versions /
    compare_versions / rollback_to_version /
    StrategyVersion / StrategyVersionDiff / StrategyVersionComparison /
    StrategyVersionNotFoundError
"""

from __future__ import annotations

from app.strategy_engine.strategy_versioning.manager import (
    StrategyVersionNotFoundError,
    compare_versions,
    create_version,
    get_latest_version,
    get_version,
    list_versions,
    rollback_to_version,
)
from app.strategy_engine.strategy_versioning.models import (
    StrategyVersion,
    StrategyVersionComparison,
    StrategyVersionDiff,
)

__all__ = [
    "StrategyVersion",
    "StrategyVersionComparison",
    "StrategyVersionDiff",
    "StrategyVersionNotFoundError",
    "compare_versions",
    "create_version",
    "get_latest_version",
    "get_version",
    "list_versions",
    "rollback_to_version",
]
