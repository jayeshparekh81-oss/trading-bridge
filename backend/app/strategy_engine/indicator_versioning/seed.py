"""Seed the version registry with v1.0.0 entries for every indicator.

Runs once at module import (via ``__init__.py``). Reads the existing
:data:`app.strategy_engine.indicators.INDICATOR_REGISTRY` (105 entries
at the time of writing — 20 active + 85 ``coming_soon``) and registers
the locked initial version for each.

The seeder is idempotent: ``register_version`` rejects duplicate
``(indicator_id, version)`` pairs, so re-importing the module never
duplicates history. Tests that need to re-seed after a ``clear()``
call can invoke :func:`seed_initial_versions` directly.
"""

from __future__ import annotations

from app.strategy_engine.indicator_versioning.constants import (
    INITIAL_CHANGELOG,
    INITIAL_FORMULA_VERSION,
    INITIAL_VERSION,
    INITIAL_VERSION_DATE,
)
from app.strategy_engine.indicator_versioning.models import IndicatorVersionRecord
from app.strategy_engine.indicator_versioning.registry import register_version
from app.strategy_engine.indicators import INDICATOR_REGISTRY


def seed_initial_versions() -> None:
    """Register a v1.0.0 record for every indicator in the runtime
    registry. Safe to call multiple times — duplicates are dropped by
    :func:`register_version`."""
    for indicator_id in INDICATOR_REGISTRY:
        record = IndicatorVersionRecord(
            indicator_id=indicator_id,
            version=INITIAL_VERSION,
            formula_version=INITIAL_FORMULA_VERSION,
            changelog=INITIAL_CHANGELOG,
            created_at=INITIAL_VERSION_DATE,
            deprecated=False,
        )
        register_version(record)


__all__ = ["seed_initial_versions"]
