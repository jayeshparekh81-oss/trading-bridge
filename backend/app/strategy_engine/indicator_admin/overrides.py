"""Direct admin overrides + history queries.

``create_direct_override`` is the one-shot path admins use when
they want to skip the queue (e.g. emergency deprecation of a
broken indicator). The queue's ``decide_request`` reuses this same
function under the hood — the only difference is whether a queue
row also gets stamped with ``decision_*``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.indicator_status_override import IndicatorStatusOverride
from app.strategy_engine.indicator_admin.resolver import (
    resolve_effective_status,
)

#: Allowed override-status values. ``deprecated`` is admin-action
#: only; the registry's ``IndicatorStatus`` enum doesn't include it.
_ALLOWED_OVERRIDE_STATUSES: frozenset[str] = frozenset(
    {"active", "coming_soon", "experimental", "deprecated"}
)


async def create_direct_override(
    db: AsyncSession,
    *,
    indicator_id: str,
    new_status: str,
    reason: str,
    approved_by_user_id: uuid.UUID,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
    decision_metadata: dict[str, Any] | None = None,
    audit_log_id: uuid.UUID | None = None,
) -> IndicatorStatusOverride:
    """Insert a new override row + return it.

    Caller is responsible for committing the session — keeping
    the commit at the API layer means a request-level transaction
    can roll back the override + its audit log entry together if
    a downstream step fails.

    Records the *prior* effective status on the new row so the
    history view shows a contiguous chain (registry_default →
    coming_soon override → active override → ...).
    """
    if new_status not in _ALLOWED_OVERRIDE_STATUSES:
        raise ValueError(
            f"new_status must be one of {sorted(_ALLOWED_OVERRIDE_STATUSES)!r}; "
            f"got {new_status!r}"
        )

    now = datetime.now(UTC)
    prior = await resolve_effective_status(db, indicator_id, now=now)

    row = IndicatorStatusOverride(
        indicator_id=indicator_id,
        override_status=new_status,
        override_reason=reason,
        approved_by_user_id=approved_by_user_id,
        approved_at=now,
        effective_from=effective_from or now,
        effective_until=effective_until,
        prior_status=prior.status,
        prior_status_source=prior.source,
        audit_log_id=audit_log_id,
        decision_metadata=decision_metadata or {},
    )
    db.add(row)
    await db.flush()  # populate ``id`` for the queue row that may reference it
    return row


async def list_active_overrides(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[IndicatorStatusOverride]:
    """Every currently-effective override across all indicators.

    Naive implementation: load the latest 500 rows, filter in
    Python. Indicator count + override volume is far too small
    for this to need a window-function rewrite. v1.1 can swap
    in DISTINCT ON when the table grows past 10k rows.
    """
    moment = now or datetime.now(UTC)
    rows = (
        (
            await db.execute(
                select(IndicatorStatusOverride)
                .order_by(IndicatorStatusOverride.effective_from.desc())
                .limit(500)
            )
        )
        .scalars()
        .all()
    )

    # Pick the latest in-window per indicator id. SQLite returns
    # naive datetimes — normalise to UTC before comparing against
    # the tz-aware ``moment``.
    seen: set[str] = set()
    out: list[IndicatorStatusOverride] = []
    for row in rows:
        if row.indicator_id in seen:
            continue
        starts = row.effective_from
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=UTC)
        if starts > moment:
            continue
        ends = row.effective_until
        if ends is not None:
            if ends.tzinfo is None:
                ends = ends.replace(tzinfo=UTC)
            if ends <= moment:
                continue
        seen.add(row.indicator_id)
        out.append(row)
    return out


async def get_indicator_history(
    db: AsyncSession,
    indicator_id: str,
    *,
    limit: int = 50,
) -> list[IndicatorStatusOverride]:
    """All historical override rows for one indicator, newest
    first. Drives the admin "history" view + serves as the
    audit trail for compliance reports."""
    rows = (
        (
            await db.execute(
                select(IndicatorStatusOverride)
                .where(IndicatorStatusOverride.indicator_id == indicator_id)
                .order_by(IndicatorStatusOverride.approved_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


__all__ = [
    "create_direct_override",
    "get_indicator_history",
    "list_active_overrides",
]
