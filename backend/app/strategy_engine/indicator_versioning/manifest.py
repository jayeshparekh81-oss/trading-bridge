"""Manifest capture — the public write path.

:func:`capture_manifest` resolves an indicator-id list against the
in-memory version registry, stamps the current engine + schema
versions onto a frozen :class:`BacktestVersionManifest`, and returns
it for the caller to attach to a backtest response.

The function is the only place the manifest's ``captured_at`` clock
is read, keeping the rest of the module deterministic and easy to
mock in tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from app.strategy_engine.indicator_versioning.constants import (
    DEFAULT_SCHEMA_VERSION,
    ENGINE_VERSION,
)
from app.strategy_engine.indicator_versioning.models import (
    BacktestVersionManifest,
    IndicatorVersionRecord,
)
from app.strategy_engine.indicator_versioning.registry import get_current_version


def capture_manifest(
    *,
    backtest_id: UUID,
    strategy_id: UUID,
    indicators_used: Iterable[str],
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    engine_version: str = ENGINE_VERSION,
) -> BacktestVersionManifest:
    """Build a :class:`BacktestVersionManifest` for one backtest.

    Args:
        backtest_id: Unique id for this backtest run.
        strategy_id: The strategy the backtest was run against.
        indicators_used: Registry indicator ids (e.g. ``["ema",
            "rsi"]``) referenced by the strategy. Duplicates are
            collapsed — the manifest pins one version per indicator.
        schema_version: ``StrategyJSON`` schema version. Defaults to
            :data:`constants.DEFAULT_SCHEMA_VERSION`.
        engine_version: Backtest engine version. Defaults to
            :data:`constants.ENGINE_VERSION`.

    Returns:
        :class:`BacktestVersionManifest` with the resolved version
        for every indicator in ``indicators_used``.

    Raises:
        UnknownIndicatorError: if any id in ``indicators_used`` has
            no registered version. The seeder runs every known
            registry indicator at module import, so this only fires
            when a strategy references an indicator id that does not
            exist in the runtime registry.
    """
    seen: set[str] = set()
    resolved: dict[str, IndicatorVersionRecord] = {}
    for indicator_id in indicators_used:
        if indicator_id in seen:
            continue
        seen.add(indicator_id)
        resolved[indicator_id] = get_current_version(indicator_id)

    return BacktestVersionManifest(
        backtest_id=backtest_id,
        strategy_id=strategy_id,
        indicators_used=resolved,
        schema_version=schema_version,
        engine_version=engine_version,
        captured_at=datetime.now(UTC),
    )


__all__ = ["capture_manifest"]
