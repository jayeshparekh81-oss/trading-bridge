"""Effective indicator status resolver.

Reads :class:`IndicatorStatusOverride` rows and falls back to the
registry default when no active override exists.

No Redis caching in Phase 1 — a single indexed SELECT per resolve
is fast enough at launch scale (the index
``ix_indicator_status_overrides_indicator_effective_from``
serves the lookup in O(log n)). Cache layer is deferred to v1.1
so we don't ship invalidation bugs alongside the dashboard.

Effective-status lookup window:

    effective_from <= now() AND
    (effective_until IS NULL OR effective_until > now())

ORDER BY effective_from DESC LIMIT 1
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.indicator_status_override import IndicatorStatusOverride
from app.strategy_engine.indicators.registry import get_indicator_by_id

#: Possible status strings that ``EffectiveStatus.status`` can hold.
#: Includes ``deprecated`` (an override-only state) plus
#: ``unknown`` (indicator id is not in the registry AND has no
#: override — should not happen in practice but the resolver
#: stays defensive).
EffectiveStatusValue = Literal[
    "active", "coming_soon", "experimental", "deprecated", "unknown"
]

#: The registry id stays a string rather than the enum so the
#: ``unknown`` sentinel can flow through the same path as known
#: ids — callers branch on string equality, not isinstance checks.
StatusSource = Literal["registry_default", "override"]


@dataclass(frozen=True)
class EffectiveStatus:
    """Resolved status for an indicator id at a point in time."""

    indicator_id: str
    status: EffectiveStatusValue
    source: StatusSource
    override_id: str | None = None
    override_reason: str | None = None
    approved_at: datetime | None = None


async def resolve_effective_status(
    db: AsyncSession,
    indicator_id: str,
    *,
    now: datetime | None = None,
) -> EffectiveStatus:
    """Return the effective status for ``indicator_id``.

    Prefers the latest in-window override row; falls back to the
    registry default when none exists. Returns ``unknown`` only
    when the id is in neither place.

    The ``now`` parameter is for testability — production callers
    should leave it as ``None`` so the function uses the actual
    current UTC time.
    """
    moment = now or datetime.now(UTC)

    stmt = (
        select(IndicatorStatusOverride)
        .where(
            IndicatorStatusOverride.indicator_id == indicator_id,
            IndicatorStatusOverride.effective_from <= moment,
        )
        .order_by(IndicatorStatusOverride.effective_from.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    # Filter for "still in effect" in Python — the SQL filter
    # would need a tz-aware comparison that's painful to
    # cross-dialect (SQLite stores naive timestamps).
    for row in rows:
        ends = row.effective_until
        if ends is not None:
            if ends.tzinfo is None:
                ends = ends.replace(tzinfo=UTC)
            if ends <= moment:
                continue
        return EffectiveStatus(
            indicator_id=indicator_id,
            status=row.override_status,  # type: ignore[arg-type]
            source="override",
            override_id=str(row.id),
            override_reason=row.override_reason,
            approved_at=row.approved_at,
        )

    meta = get_indicator_by_id(indicator_id)
    if meta is None:
        return EffectiveStatus(
            indicator_id=indicator_id,
            status="unknown",
            source="registry_default",
        )
    return EffectiveStatus(
        indicator_id=indicator_id,
        status=meta.status.value,
        source="registry_default",
    )


__all__ = ["EffectiveStatus", "EffectiveStatusValue", "resolve_effective_status"]
