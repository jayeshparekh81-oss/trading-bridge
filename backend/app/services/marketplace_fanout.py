"""Marketplace subscriber fan-out — read-only subscriber lookup (Module 1).

Purpose
-------
This module is the future home of "one TradingView signal -> many
subscribers' broker accounts" execution. It is being built module-by-module
behind a flag so the live owner path is never disturbed.

What is live today (and stays byte-identical)
---------------------------------------------
The owner path is strictly **1 -> 1**: an inbound webhook resolves ONE owner
:class:`Strategy` and the executor places orders against that strategy's
single ``broker_credential_id``. The ONLY call site of this module in the
live path is a **flag-gated, LOG-ONLY** block at the end of the strategy
webhook handler (``strategy_webhook.py``), AFTER the owner dispatch. When
``settings.marketplace_fanout_enabled`` is ``False`` (the default) that block
is skipped entirely and the owner path is byte-identical. ``strategy_executor``,
``signal_execution`` and ``direct_exit`` never import this module.

Master switch
-------------
All subscriber behaviour is gated by ``settings.marketplace_fanout_enabled``
(env ``MARKETPLACE_FANOUT_ENABLED``, default ``False`` — see
:mod:`app.core.config`). Keeping the flag ``False`` guarantees owner-only
1 -> 1 execution.

Scope (this file)
-----------------
* :func:`resolve_active_subscriptions` (Module 1) — a real, **READ-ONLY** SELECT
  (join of ``marketplace_subscriptions`` to ``marketplace_listings``) returning
  the active subscriptions for a strategy. No INSERT/UPDATE/DELETE, no flush,
  no commit, no session mutation.
* :func:`dispatch_subscriber_executions` (Module 2) — **PAPER ONLY**. For each
  active subscriber it runs ONE simulated fill using the OWNER's exact paper
  primitive (:func:`app.services.strategy_executor._simulate_fill`). It NEVER
  calls a real broker / places a real order, does NOT read or honour any
  live/paper flag for subscribers, and writes NO position or order row — so the
  owner's position state is untouched (a subscriber paper position would
  otherwise sum into the owner's live position, since positions are keyed by
  ``(strategy, symbol, side)`` ignoring ``user_id``). Durable per-subscriber
  positions with real credentials + per-subscriber quantity are Module 4 (which
  needs a migration). Per-subscriber failures are isolated (log + continue).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.strategy import Strategy
    from app.db.models.strategy_signal import StrategySignal

logger = get_logger("app.services.marketplace_fanout")

#: Subscription lifecycle value that means "currently entitled". The CHECK
#: constraint on ``marketplace_subscriptions.status`` pins the vocabulary at
#: the migration layer; this matches the API layer's "active" subscribe state.
_ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class SubscriberRef:
    """Read-only descriptor of one active subscriber of a strategy.

    Carries ONLY columns that exist on ``marketplace_subscriptions`` today and
    is decoupled from the ORM identity map (so callers can log/iterate it
    without holding the session open). It deliberately OMITS execution fields —
    the subscriber's broker_credential_id, per-subscriber quantity/size, etc.
    do not exist as columns yet; assuming them now would be wrong. Later
    modules extend this descriptor once those columns are added.
    """

    subscription_id: uuid.UUID
    subscriber_id: uuid.UUID
    listing_id: uuid.UUID
    status: str
    subscribed_at: datetime
    access_until: datetime | None


@dataclass(frozen=True)
class PaperExecutionResult:
    """Outcome of one PAPER (simulated) subscriber execution — Module 2.

    ``paper`` is always ``True`` in this module. ``status`` is ``"filled"`` for
    a successful simulated fill or ``"failed"`` (with ``error``) when that one
    subscriber's simulation raised — the other subscribers are unaffected.
    """

    subscription_id: uuid.UUID
    subscriber_id: uuid.UUID
    symbol: str
    action: str
    side: str | None
    quantity: int
    paper: bool
    broker_order_id: str | None
    avg_price: str | None
    status: str
    #: The persisted subscriber StrategyPosition id (entry signals); None for
    #: non-entry actions (subscriber exits are Module 4) or failures.
    position_id: str | None = None
    error: str | None = None


def fanout_enabled() -> bool:
    """Return the marketplace fan-out master switch.

    Reads ``settings.marketplace_fanout_enabled`` (env
    ``MARKETPLACE_FANOUT_ENABLED``). Pure, side-effect-free. Defaults to
    ``False`` so the owner 1 -> 1 path is the only behaviour today.
    """
    return bool(get_settings().marketplace_fanout_enabled)


async def resolve_active_subscriptions(
    strategy_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubscriberRef]:
    """Read-only: the active subscriptions whose listing maps to ``strategy_id``.

    Joins ``marketplace_subscriptions`` to ``marketplace_listings`` on
    ``listing_id`` and selects rows where the listing's ``strategy_id`` matches
    AND ``MarketplaceSubscription.status == 'active'``.

    This is a **pure SELECT**: it performs NO INSERT/UPDATE/DELETE, no flush,
    no commit, and does not mark anything dirty. It returns lightweight,
    immutable :class:`SubscriberRef` descriptors (only fields that exist today
    — no execution fields). Callers in Module 1 only LOG the result; nothing
    is dispatched or executed.
    """
    stmt = (
        select(MarketplaceSubscription)
        .join(
            MarketplaceListing,
            MarketplaceListing.id == MarketplaceSubscription.listing_id,
        )
        .where(
            MarketplaceListing.strategy_id == strategy_id,
            MarketplaceSubscription.status == _ACTIVE_STATUS,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SubscriberRef(
            subscription_id=row.id,
            subscriber_id=row.subscriber_id,
            listing_id=row.listing_id,
            status=row.status,
            subscribed_at=row.subscribed_at,
            access_until=row.access_until,
        )
        for row in rows
    ]


async def dispatch_subscriber_executions(
    signal: StrategySignal,
    strategy: Strategy,
    subscribers: list[SubscriberRef],
    db: AsyncSession,
) -> list[PaperExecutionResult]:
    """PAPER ONLY — run + persist one simulated execution per active subscriber.

    For every subscriber this runs ONE simulated (paper) fill using the SAME
    primitive the owner's paper path uses
    (:func:`app.services.strategy_executor._simulate_fill`) and, for ENTRY
    signals, persists an ISOLATED subscriber ``StrategyPosition`` +
    ``StrategyExecution`` tagged with the row's ``subscription_id``
    (migration 034). Returns one :class:`PaperExecutionResult` per subscriber.

    Hard guarantees (Module 3):
      * **PAPER ONLY.** The only execution primitive used is ``_simulate_fill``
        (pure — no broker). No real broker is built or called, no real order is
        placed, for any subscriber, under any config. This module does NOT read
        or honour ``strategy.is_paper`` / ``settings.strategy_paper_mode`` for
        subscribers — subscribers are forced to paper regardless.
      * **Owner isolation.** Subscriber rows carry a NON-NULL ``subscription_id``
        and are scoped to it. The owner's entry-sum / exit / position-loop /
        reconciliation lookups all filter ``subscription_id IS NULL``, so a
        subscriber row can NEVER sum into, close, or be managed alongside the
        owner's (LIVE) position, and the position loop never polls subscriber
        rows — so they never trigger a broker call.
      * **Per-subscriber isolation.** Each subscriber's write runs in its own
        SAVEPOINT; one subscriber failing rolls back ONLY its row (recorded as
        ``status='failed'``) — the others (and the owner) proceed.

    Sizing uses a sensible default (``strategy.entry_lots`` or 1, paper
    ``lot_size=1``); per-subscriber quantity is Module 4. Subscriber EXIT-signal
    handling (closing subscriber positions) is also Module 4 — for non-entry
    actions this logs a paper simulation without persisting.
    """
    # Lazy imports mirror signal_execution.py's executor-import pattern and bind
    # the EXACT paper primitives the owner path runs (never the live-order code).
    from app.db.models.strategy_execution import StrategyExecution
    from app.db.models.strategy_position import StrategyPosition
    from app.services.strategy_executor import (
        StrategyExecutorError,
        _compute_levels,
        _find_existing_open_position,
        _resolve_side,
        _simulate_fill,
    )

    default_qty = int(strategy.entry_lots or 1)
    side_hint = (signal.raw_payload or {}).get("side")

    # ENTRY actions resolve to an OrderSide; EXIT / PARTIAL / SL_HIT raise here —
    # those are subscriber exits, deferred to Module 4 (log-only this module).
    try:
        entry_side = _resolve_side(signal.action, side_hint=side_hint)
    except StrategyExecutorError:
        entry_side = None

    results: list[PaperExecutionResult] = []
    wrote_any = False

    for sub in subscribers:
        try:
            sim = _simulate_fill(signal, default_qty)  # FORCED paper — pure, no broker
            avg = sim.get("avg_price")
            order_id = str(sim.get("broker_order_id"))
            position_id: str | None = None

            if entry_side is not None:
                if strategy.broker_credential_id is None:
                    raise StrategyExecutorError(
                        "strategy has no broker_credential_id for the paper "
                        "placeholder; cannot persist subscriber position"
                    )
                # Per-subscriber SAVEPOINT — a single failure rolls back ONLY
                # this subscriber's rows, never the others'.
                async with db.begin_nested():
                    now = datetime.now(UTC)
                    existing = await _find_existing_open_position(
                        db,
                        strategy_id=strategy.id,
                        symbol=signal.symbol,
                        side=entry_side,
                        subscription_id=sub.subscription_id,
                    )
                    if existing is not None:
                        # Sum WITHIN this subscriber's own scope (mirrors the
                        # owner's re-entry summing, isolated per subscription).
                        existing.total_quantity += default_qty
                        existing.remaining_quantity += default_qty
                        position_id = str(existing.id)
                    else:
                        target, stop_loss, trail = _compute_levels(
                            avg_price=avg, side=entry_side, strategy=strategy
                        )
                        position = StrategyPosition(
                            user_id=sub.subscriber_id,
                            strategy_id=strategy.id,
                            # Paper placeholder FK — no broker is ever built or
                            # called in paper mode. Real per-subscriber creds = M4.
                            broker_credential_id=strategy.broker_credential_id,
                            subscription_id=sub.subscription_id,
                            signal_id=signal.id,
                            symbol=signal.symbol,
                            side=entry_side.value,
                            total_quantity=default_qty,
                            remaining_quantity=default_qty,
                            avg_entry_price=avg,
                            target_price=target,
                            stop_loss_price=stop_loss,
                            trail_offset=trail,
                            highest_price_seen=avg,
                            status="open",
                            opened_at=now,
                        )
                        db.add(position)
                        await db.flush()
                        position_id = str(position.id)

                    execution = StrategyExecution(
                        signal_id=signal.id,
                        broker_credential_id=strategy.broker_credential_id,
                        subscription_id=sub.subscription_id,
                        leg_number=1,
                        leg_role="entry",
                        symbol=signal.symbol,
                        side=entry_side.value,
                        quantity=default_qty,
                        order_type="market",
                        price=avg,
                        broker_order_id=order_id,
                        broker_status="complete",
                        broker_response={
                            "paper": True,
                            "marketplace_subscription_id": str(sub.subscription_id),
                            "broker_order_id": order_id,
                            "avg_price": str(avg) if avg is not None else None,
                            "quantity": default_qty,
                            "source": "marketplace_fanout",
                        },
                        placed_at=now,
                        completed_at=now,
                    )
                    db.add(execution)
                    await db.flush()
                wrote_any = True

            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=(
                        entry_side.value
                        if entry_side is not None
                        else (str(side_hint) if side_hint is not None else None)
                    ),
                    quantity=default_qty,
                    paper=True,
                    broker_order_id=order_id,
                    avg_price=str(avg) if avg is not None else None,
                    status="filled",
                    position_id=position_id,
                )
            )
            logger.info(
                "fanout.paper.executed"
                if entry_side is not None
                else "fanout.paper.simulated_no_persist",
                paper=True,
                persisted=entry_side is not None,
                signal_id=str(signal.id),
                strategy_id=str(strategy.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                symbol=signal.symbol,
                action=signal.action,
                quantity=default_qty,
                broker_order_id=order_id,
                position_id=position_id,
            )
        except Exception as exc:  # isolate per-subscriber failures — never escalate
            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=str(side_hint) if side_hint is not None else None,
                    quantity=default_qty,
                    paper=True,
                    broker_order_id=None,
                    avg_price=None,
                    status="failed",
                    error=str(exc),
                )
            )
            logger.warning(
                "fanout.paper.subscriber_failed",
                signal_id=str(signal.id),
                strategy_id=str(strategy.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                error=str(exc),
            )

    if wrote_any:
        await db.commit()

    filled = sum(1 for r in results if r.status == "filled")
    logger.info(
        "fanout.paper.summary",
        signal_id=str(signal.id),
        strategy_id=str(strategy.id),
        subscriber_count=len(subscribers),
        paper_filled=filled,
        paper_failed=len(results) - filled,
        persisted=entry_side is not None,
    )
    return results
