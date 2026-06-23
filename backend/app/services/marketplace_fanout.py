"""Marketplace subscriber fan-out — DORMANT scaffold (Marketplace Module 0).

Purpose
-------
This module is the *future* home of "one TradingView signal -> many
subscribers' broker accounts" execution. As of Module 0 it is a pure
**safety scaffold**: stubs only, wired to nothing.

What is live today (and stays byte-identical)
---------------------------------------------
The owner path is strictly **1 -> 1**: an inbound webhook resolves ONE
owner :class:`Strategy` and the executor places orders against that
strategy's single ``broker_credential_id``. Nothing in this module is
imported or called by ``strategy_webhook.py`` / ``strategy_executor.py`` /
``signal_execution.py`` / ``direct_exit.py``. There are **zero call sites**
in the live path. Importing this module has no side effects.

Master switch
-------------
All future behaviour is gated by ``settings.marketplace_fanout_enabled``
(env ``MARKETPLACE_FANOUT_ENABLED``, default ``False`` — see
:mod:`app.core.config`). When the real implementation lands in later
modules it will run **additively, alongside** the owner execution (never
instead of it) and only when this flag is ``True``. Keeping the flag
``False`` guarantees owner-only 1 -> 1 execution.

Module 0 contract
-----------------
Every function here is a no-op stub: it returns an empty result / ``None``
and performs **no** DB access, **no** broker calls, **no** Celery dispatch,
and **no** mutation. The docstrings describe what each function WILL do so
later modules have a precise target; the bodies implement nothing live.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    # Type-only imports — never executed at runtime, so this module stays
    # fully decoupled from the ORM / live execution path.
    from app.db.models.marketplace_subscription import MarketplaceSubscription
    from app.db.models.strategy import Strategy
    from app.db.models.strategy_signal import StrategySignal

logger = logging.getLogger(__name__)


def fanout_enabled() -> bool:
    """Return the dormant marketplace fan-out master switch.

    Reads ``settings.marketplace_fanout_enabled`` (env
    ``MARKETPLACE_FANOUT_ENABLED``). Pure, side-effect-free. Defaults to
    ``False`` so the owner 1 -> 1 path is the only behaviour today. Later
    modules guard every subscriber action behind this.
    """
    return bool(get_settings().marketplace_fanout_enabled)


def resolve_active_subscriptions(
    strategy_id: uuid.UUID,
) -> list[MarketplaceSubscription]:
    """STUB (Module 0 — always returns ``[]``).

    WILL: given an owner ``strategy_id``, find that strategy's marketplace
    listing and return the **active, non-expired** subscriptions
    (``MarketplaceSubscription.status == 'active'`` AND ``access_until`` in
    the future) so the dispatcher can fan a signal out to each subscriber's
    OWN broker account. Read-only — it will never mutate subscriptions or
    positions.

    Today: dormant. Returns an empty list (no DB access), so any future
    caller sees "no subscribers" and the owner path is unaffected. There are
    no callers in Module 0.
    """
    # M0: intentionally unimplemented. The real (read-only) query lands in a
    # later module, behind fanout_enabled(). No I/O, no side effects here.
    return []


def dispatch_subscriber_executions(
    signal: StrategySignal,
    strategy: Strategy,
) -> None:
    """STUB (Module 0 — no-op).

    WILL: for each active subscription from
    :func:`resolve_active_subscriptions` (``strategy.id``), enqueue an
    **additive** per-subscriber execution — using the subscriber's own
    ``broker_credential_id`` and per-subscriber quantity — with a
    subscriber-scoped idempotency key and per-subscriber partial-failure
    isolation (one subscriber's broker rejection must not affect another's).
    It will run **alongside** the owner's 1 -> 1 execution, never replace it,
    and only when :func:`fanout_enabled` is ``True``.

    Today: dormant. Does nothing — zero broker calls, zero DB writes, zero
    Celery dispatch. The owner webhook/executor never calls this; it has no
    call sites in the live path.
    """
    # M0: intentionally unimplemented. Returns immediately. Future modules
    # build the real, flag-guarded fan-out here.
    return None
