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
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription

if TYPE_CHECKING:
    from datetime import datetime

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
    """PAPER ONLY — simulate the signal's execution for each active subscriber.

    For every subscriber this runs ONE simulated (paper) fill using the SAME
    primitive the owner's paper path uses
    (:func:`app.services.strategy_executor._simulate_fill`). It returns one
    :class:`PaperExecutionResult` per subscriber.

    Hard guarantees (Module 2):
      * **PAPER ONLY.** The only execution primitive called is
        ``_simulate_fill`` (pure — no broker). No real broker is built or
        called, no real order is placed, for any subscriber, under any config.
        This module does NOT read or honour ``strategy.is_paper`` /
        ``settings.strategy_paper_mode`` for subscribers — subscribers are
        forced to paper regardless. Real money is a later, separately-gated
        module (post-empanelment).
      * **Owner untouched.** No ``StrategyPosition`` / ``StrategyExecution`` row
        is written. A subscriber paper position would otherwise sum into the
        OWNER's live position (positions are keyed by ``(strategy, symbol,
        side)`` ignoring ``user_id``), corrupting the owner — so durable
        per-subscriber positions wait for Module 4 (which adds the per-
        subscriber scoping column + migration).
      * **Per-subscriber isolation.** One subscriber's simulation raising is
        logged + recorded as ``status='failed'``; the other subscribers (and
        the owner) proceed.

    A "sensible default" quantity is used for now (``strategy.entry_lots`` or 1,
    paper ``lot_size=1``); per-subscriber quantity is Module 4.

    ``db`` is accepted for interface stability with later modules; Module 2
    performs no writes, so it is unused here.
    """
    # Lazy import (mirrors the executor-import pattern in signal_execution.py)
    # binds the EXACT paper-fill code the owner path runs — strategy_executor
    # line ~193 calls this same ``_simulate_fill``.
    from app.services.strategy_executor import _simulate_fill

    default_qty = int(strategy.entry_lots or 1)
    side_hint = (signal.raw_payload or {}).get("side")
    side = str(side_hint) if side_hint is not None else None

    results: list[PaperExecutionResult] = []
    for sub in subscribers:
        try:
            sim = _simulate_fill(signal, default_qty)  # FORCED paper — pure, no broker
            avg = sim.get("avg_price")
            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=side,
                    quantity=default_qty,
                    paper=True,
                    broker_order_id=str(sim.get("broker_order_id")),
                    avg_price=str(avg) if avg is not None else None,
                    status="filled",
                )
            )
            logger.info(
                "fanout.paper.executed",
                paper=True,
                signal_id=str(signal.id),
                strategy_id=str(strategy.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                symbol=signal.symbol,
                action=signal.action,
                quantity=default_qty,
                broker_order_id=str(sim.get("broker_order_id")),
            )
        except Exception as exc:  # isolate per-subscriber failures — never escalate
            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=side,
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

    filled = sum(1 for r in results if r.status == "filled")
    logger.info(
        "fanout.paper.summary",
        signal_id=str(signal.id),
        strategy_id=str(strategy.id),
        subscriber_count=len(subscribers),
        paper_filled=filled,
        paper_failed=len(results) - filled,
    )
    return results
