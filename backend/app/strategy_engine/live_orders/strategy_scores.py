"""Cached Trust + Truth score reader for the live-orders SafetyChain.

Phase 8B-1 discovery exposed the gap: the SafetyChain enforces Trust
>= 70 and Truth >= 55 on every ``place_live_order`` call, but the
reports are computed only inside the backtest pipeline. Re-running
that pipeline on the order path would be expensive and would block
real-money trades on data fetches. Migration 012 added three columns
to ``strategies`` so the backtest endpoint can cache the latest scores;
this module is the read side, with a 24h staleness check matching the
existing Dhan scrip-master TTL pattern.

Public surface:

    StrategyScoresSnapshot — frozen dataclass; what callers see.
    SCORES_TTL              — :class:`timedelta` (24h, locked).
    get_cached_scores       — async lookup with TTL gate.

The function returns ``None`` when:

* No row matches ``strategy_id``.
* The row exists but ``last_scores_at`` is ``NULL`` (never backtested).
* Either score column is ``NULL`` (partial write, defence-in-depth).
* The cached scores are older than :data:`SCORES_TTL`.

NULL ≡ stale ≡ "no usable scores" — the SafetyChain renders the same
"Run a fresh backtest first" message for all three so the user-facing
surface stays simple.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.strategy import Strategy

#: Locked staleness threshold. Mirrors the 24h TTL on the Dhan
#: scrip-master cache (``app/brokers/dhan.py`` — ``_ttl =
#: timedelta(hours=24)``); changing this requires a corresponding
#: change to the SafetyChain's user-facing copy.
SCORES_TTL: timedelta = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class StrategyScoresSnapshot:
    """One read of the cached scores plus its age.

    ``age_hours`` is computed at read time so the SafetyChain can
    surface "scores from N hours ago" in the pre-flight panel. The
    field is read-only — frozen dataclass, no mutation between the
    SafetyChain's check and the order modal's display.
    """

    trust_score: float
    truth_score: float
    computed_at: datetime
    age_hours: float


async def get_cached_scores(
    db: AsyncSession, strategy_id: uuid.UUID
) -> StrategyScoresSnapshot | None:
    """Return the cached snapshot, or ``None`` for missing/stale rows.

    A single SELECT pulls the three score columns; the staleness check
    is local (no DB clock read) using ``datetime.now(UTC)``. The
    SafetyChain calls this before placing every live order, so the
    query path stays as a primary-key lookup with an index hit on
    ``last_scores_at`` if the planner picks it.
    """
    stmt = select(
        Strategy.last_trust_score,
        Strategy.last_truth_score,
        Strategy.last_scores_at,
    ).where(Strategy.id == strategy_id)
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None

    trust, truth, computed_at = row
    if trust is None or truth is None or computed_at is None:
        return None

    now = datetime.now(UTC)
    # Persisted timestamps are timezone-aware in production (Postgres
    # ``timestamptz``); the SQLite test engine stores them naive even
    # when the column is declared with ``DateTime(timezone=True)``.
    # Coerce to UTC so the staleness comparison never raises on the
    # naive-vs-aware mismatch.
    if computed_at.tzinfo is None:
        computed_at = computed_at.replace(tzinfo=UTC)

    age = now - computed_at
    if age > SCORES_TTL:
        return None

    return StrategyScoresSnapshot(
        trust_score=float(trust),
        truth_score=float(truth),
        computed_at=computed_at,
        age_hours=age.total_seconds() / 3600.0,
    )


__all__ = [
    "SCORES_TTL",
    "StrategyScoresSnapshot",
    "get_cached_scores",
]
