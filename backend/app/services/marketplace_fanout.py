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

Module 1 scope (this file)
--------------------------
* :func:`resolve_active_subscriptions` — a real, **READ-ONLY** SELECT (join of
  ``marketplace_subscriptions`` to ``marketplace_listings``) returning the
  active subscriptions for a strategy. No INSERT/UPDATE/DELETE, no flush, no
  commit, no session mutation.
* :func:`dispatch_subscriber_executions` — STILL a no-op stub. No execution,
  no broker calls, no Celery dispatch in this module; later modules implement
  the additive, flag-guarded dispatch here.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.strategy import Strategy
    from app.db.models.strategy_signal import StrategySignal

logger = logging.getLogger(__name__)

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


def dispatch_subscriber_executions(
    signal: StrategySignal,
    strategy: Strategy,
) -> None:
    """STUB (no-op) — subscriber dispatch is NOT implemented yet.

    WILL: for each active subscription from
    :func:`resolve_active_subscriptions` (``strategy.id``), enqueue an
    **additive** per-subscriber execution — using the subscriber's own
    ``broker_credential_id`` and per-subscriber quantity — with a
    subscriber-scoped idempotency key and per-subscriber partial-failure
    isolation. It will run **alongside** the owner's 1 -> 1 execution, never
    replace it, and only when :func:`fanout_enabled` is ``True``.

    Today: dormant. Does nothing — zero broker calls, zero DB writes, zero
    Celery dispatch. There are no call sites for this function in the live
    path (Module 1 only resolves + logs).
    """
    # Not implemented in Module 1. Returns immediately. Future modules build
    # the real, flag-guarded fan-out dispatch here.
    return None
