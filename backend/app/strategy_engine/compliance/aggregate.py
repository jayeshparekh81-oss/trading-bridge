"""Admin-side aggregation of indicator usage across the platform.

These helpers iterate every strategy row, parse out the indicator
references, and roll up per-indicator counts. Cheap at our launch
scale (low thousands of strategies); will need an indexed counter
table or materialized view at the 100k+ scale point — flagged as
v1.1 in the dashboard's PERFORMANCE notes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.compliance.evaluator import _extract_indicator_pairs
from app.strategy_engine.indicators.registry import (
    INDICATOR_REGISTRY,
    get_indicator_by_id,
)
from app.strategy_engine.schema.indicator import IndicatorStatus

#: A coming_soon indicator that this many strategies use is a
#: candidate for promotion to ACTIVE — the implementation has
#: real demand backing it.
_PROMOTION_USAGE_THRESHOLD = 50

#: Window for the "is this getting more popular" signal.
_RECENT_WINDOW_DAYS = 30


class LicenseUsageStats(BaseModel):
    """Per-indicator usage roll-up — admin only."""

    model_config = ConfigDict(from_attributes=False)

    indicator_id: str
    name: str
    status: str
    total_strategies_using: int
    total_users_affected: int
    is_promotion_candidate: bool = Field(
        ...,
        description=(
            "True when a coming_soon indicator clears the usage "
            "threshold — signal to promote to ACTIVE."
        ),
    )
    last_30_day_usage_count: int = Field(
        ...,
        description=(
            "Strategies that referenced this indicator AND were "
            "created/updated in the last 30 days. Stand-in for "
            "'recent demand' until we have a proper events table."
        ),
    )


class StrategyRowLite:
    """Tiny duck-typed view of a strategy row.

    The aggregator is dialect-agnostic — callers pass in whatever
    object they've loaded as long as it exposes ``id``, ``user_id``,
    ``strategy_json``, and ``updated_at``. This keeps the function
    testable without spinning up an actual SQLAlchemy session.
    """

    id: Any
    user_id: Any
    strategy_json: dict[str, Any]
    updated_at: datetime


def compute_indicator_usage_stats(
    rows: Iterable[Any],
    *,
    now: datetime | None = None,
) -> list[LicenseUsageStats]:
    """Roll up per-indicator usage across the supplied strategy rows.

    Returns one entry **per known registry id**, even if usage is
    zero — the admin UI sorts by usage and an empty cell is more
    informative than a missing row. Unknown ids referenced by
    strategies (i.e. blocked indicators) get their own synthetic
    rows at the end, prefixed with ``unknown:``.
    """
    cutoff = (now or datetime.now(UTC)) - timedelta(days=_RECENT_WINDOW_DAYS)

    # registry_id -> set of strategy ids
    strategy_index: dict[str, set[Any]] = defaultdict(set)
    # registry_id -> set of user ids
    user_index: dict[str, set[Any]] = defaultdict(set)
    # registry_id -> count of recent (within cutoff) strategies
    recent_count: Counter[str] = Counter()

    for row in rows:
        json_blob = getattr(row, "strategy_json", None) or {}
        if not isinstance(json_blob, dict):
            continue
        pairs = _extract_indicator_pairs(json_blob)
        if not pairs:
            continue
        # Distinct ids per strategy: don't double-count a strategy
        # that uses ema twice.
        seen_in_row: set[str] = set()
        for registry_type, _instance in pairs:
            if registry_type in seen_in_row:
                continue
            seen_in_row.add(registry_type)
            strategy_index[registry_type].add(row.id)
            user_index[registry_type].add(row.user_id)
            updated = getattr(row, "updated_at", None)
            # SQLite doesn't natively store tz info; normalise naive
            # datetimes to UTC so the comparison against the
            # tz-aware ``cutoff`` doesn't raise. Postgres returns
            # tz-aware, so the branch is a no-op there.
            if isinstance(updated, datetime):
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=UTC)
                if updated >= cutoff:
                    recent_count[registry_type] += 1

    out: list[LicenseUsageStats] = []
    # Known registry ids first, in deterministic order.
    for registry_id in sorted(INDICATOR_REGISTRY.keys()):
        meta = get_indicator_by_id(registry_id)
        # ``meta`` is non-None here by construction (we just iterated
        # the registry's keys); the ``or registry_id`` fallback below
        # is a defence against future code that mutates the registry
        # mid-iteration.
        name = meta.name if meta is not None else registry_id
        status_str = (
            meta.status.value if meta is not None else "unknown"
        )
        total_strategies = len(strategy_index.get(registry_id, set()))
        total_users = len(user_index.get(registry_id, set()))
        is_candidate = (
            meta is not None
            and meta.status is IndicatorStatus.COMING_SOON
            and total_strategies >= _PROMOTION_USAGE_THRESHOLD
        )
        out.append(
            LicenseUsageStats(
                indicator_id=registry_id,
                name=name,
                status=status_str,
                total_strategies_using=total_strategies,
                total_users_affected=total_users,
                is_promotion_candidate=is_candidate,
                last_30_day_usage_count=recent_count.get(registry_id, 0),
            )
        )

    # Then any unknown ids that strategies referenced anyway.
    unknowns = sorted(
        set(strategy_index.keys()) - set(INDICATOR_REGISTRY.keys())
    )
    for unknown in unknowns:
        out.append(
            LicenseUsageStats(
                indicator_id=unknown,
                name=unknown,
                status="unknown",
                total_strategies_using=len(strategy_index[unknown]),
                total_users_affected=len(user_index.get(unknown, set())),
                is_promotion_candidate=False,
                last_30_day_usage_count=recent_count.get(unknown, 0),
            )
        )

    return out


__all__ = [
    "LicenseUsageStats",
    "compute_indicator_usage_stats",
]
