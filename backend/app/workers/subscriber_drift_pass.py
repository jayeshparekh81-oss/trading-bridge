"""Subscriber AUTO→MANUAL drift pass — a SEPARATE, UNSCHEDULED worker.

WHAT IT DOES
------------
Walks the subscriptions that are ACTIVE + AUTO + real-money and hold an open
position, asks each subscriber's BROKER what they actually hold (via the shared
bounded+budgeted batch), and hands each answer to the already-built
:func:`app.services.subscriber_drift_service.check_and_flip_subscription`.

On a shortfall that flips the ONE subscription to MANUAL, after which the
fan-out's existing ``execution_mode != "auto"`` branch turns every further
signal for that trade into ``notify_only`` — no order fires.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* It places, cancels, modifies and closes NOTHING. It only *withholds* future
  automation. (Asserted by tests: ``place_order`` is never called.)
* It does NOT touch ``app/workers/reconciliation_loop.py``. That loop guards the
  live BSE money path and its owner query stays byte-identical; running this as
  a separate worker keeps the two completely independent, so a failure here can
  never degrade owner reconciliation.
* It does NOT schedule itself. There is no beat entry, no asyncio task, no
  lifespan hook. Wiring it to a scheduler is a separate, founder-gated step.

FLAG
----
Gated by ``settings.subscriber_drift_enabled`` (default ``False``). While that
is False :func:`run_subscriber_drift_pass` returns immediately without touching
a broker or the DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_position import StrategyPosition
from app.services.broker_position_batch import (
    POSITION_UNKNOWN,
    gather_broker_positions,
)
from app.services.subscriber_drift_service import (
    AUTO_MODE,
    DriftDecision,
    check_and_flip_subscription,
)
from app.services.symbol_match import find_matching_position

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DriftPassReport:
    """Outcome of one pass. ``flipped`` is the only side effect."""

    checked: int
    flipped: int
    unknown: int
    decisions: list[DriftDecision]
    dormant: bool = False


async def _candidates(db: AsyncSession) -> list[tuple[MarketplaceSubscription, Any]]:
    """ACTIVE + AUTO + real-money subscriptions that hold an open position.

    Paper subscribers are excluded on purpose: there is no broker position to
    compare against, so asking would be meaningless (and a network call for
    nothing).
    """
    stmt = (
        select(MarketplaceSubscription, StrategyPosition)
        .join(
            StrategyPosition,
            StrategyPosition.subscription_id == MarketplaceSubscription.id,
        )
        .where(
            MarketplaceSubscription.status == "active",
            MarketplaceSubscription.execution_mode == AUTO_MODE,
            MarketplaceSubscription.is_paper.is_(False),
            StrategyPosition.status.in_(("open", "partial")),
        )
    )
    return list((await db.execute(stmt)).all())


async def run_subscriber_drift_pass(
    db: AsyncSession,
    *,
    fetch_broker_positions,
    per_call_timeout: float | None = None,
    concurrency: int | None = None,
    total_budget: float | None = None,
) -> DriftPassReport:
    """One drift pass. Detection + flip only — never places an order.

    ``fetch_broker_positions`` is an async ``(subscription_id) -> iterable of
    broker positions``. Injected so this worker never builds a broker itself.
    """
    if not get_settings().subscriber_drift_enabled:
        logger.debug("subscriber_drift_pass.dormant")
        return DriftPassReport(
            checked=0, flipped=0, unknown=0, decisions=[], dormant=True
        )

    rows = await _candidates(db)
    if not rows:
        return DriftPassReport(checked=0, flipped=0, unknown=0, decisions=[])

    # ONE bounded + budgeted batch — never a per-subscription serial await.
    kwargs: dict[str, Any] = {}
    if per_call_timeout is not None:
        kwargs["per_call_timeout"] = per_call_timeout
    if concurrency is not None:
        kwargs["concurrency"] = concurrency
    if total_budget is not None:
        kwargs["total_budget"] = total_budget
    broker_by_sub = await gather_broker_positions(
        [sub.id for sub, _pos in rows], fetch_broker_positions, **kwargs
    )

    decisions: list[DriftDecision] = []
    unknown = 0

    for sub, pos in rows:
        raw = broker_by_sub.get(sub.id, POSITION_UNKNOWN)

        async def _fetch_one(*, subscription, symbol, _raw=raw):
            """Adapt the batch result to the drift service's fetcher contract.

            Raising is how we say UNKNOWN — the drift service treats a raised
            fetch as absence of evidence and refuses to flip.
            """
            if _raw is POSITION_UNKNOWN:
                raise RuntimeError("broker position unavailable")
            match, certain = find_matching_position(symbol, _raw)
            if not certain:
                # Ambiguous symbol is NOT evidence of flat — refuse to flip.
                raise RuntimeError(f"symbol not confidently matched: {symbol}")
            return None if match is None else abs(int(getattr(match, "quantity", 0)))

        decision = await check_and_flip_subscription(
            db, sub,
            symbol=pos.symbol,
            stored_quantity=int(pos.remaining_quantity or 0),
            fetch_broker_position=_fetch_one,
        )
        decisions.append(decision)
        if decision.reason == "broker_unavailable":
            unknown += 1

    flipped = sum(1 for d in decisions if d.flipped)
    logger.info(
        "subscriber_drift_pass.done",
        checked=len(rows),
        flipped=flipped,
        unknown=unknown,
    )
    return DriftPassReport(
        checked=len(rows), flipped=flipped, unknown=unknown, decisions=decisions
    )


__all__ = ["DriftPassReport", "run_subscriber_drift_pass"]
