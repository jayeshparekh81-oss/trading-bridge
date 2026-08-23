"""Subscriber drift detection + the AUTO→MANUAL safety flip.

THE PROBLEM THIS SOLVES
-----------------------
A subscriber can close (or partially close) a copied position DIRECTLY at their
broker instead of on tradetri.com. Our stored row still says "open", so any
further signal for that trade (partial / trailing / exit) would act on a
position that no longer exists as we believe it does.

FIRST PRINCIPLE (founder, design-locked)
----------------------------------------
    "position hai ya nahi, iska SACH BROKER ki live position hai,
     TRADETRI ka stored record NAHI."

So the broker's live position is the truth. This module never trusts the stored
row on its own — it compares the two and, on drift, flips that ONE subscription
from AUTO to MANUAL. From then on the fan-out's existing ``execution_mode !=
"auto"`` branch turns every further signal for that subscriber into a
``notify_only`` result (see marketplace_fanout entry/exit paths) — no order
fires.

SCOPE — this is a PURE PRIMITIVE
--------------------------------
It decides and it flips. It deliberately does NOT:
  * schedule itself (no loop, no beat entry, no asyncio task),
  * place, cancel or close any order,
  * touch the owner's positions, the webhook, the executor or the kill switch.
Wiring it to a scheduler is a separate, gated step.

IMPORT DISCIPLINE
-----------------
This module must NOT import ``app.services.marketplace_fanout``: an invariant
test (tests/services/test_marketplace_fanout.py) pins the fan-out to exactly two
sanctioned importers (strategy_webhook.py, direct_exit.py) and a third would
break it. The broker-position seam below is therefore declared structurally
here, mirroring the shape of the fan-out's own ``SubscriberPositionProvider``
Protocol rather than importing it.

NO MIGRATION
------------
``marketplace_subscriptions`` has no column for a drift reason/timestamp, so the
machine-readable record is written to the existing append-only ``audit_logs``
table (``resource_type='marketplace_subscription'``), which carries a JSON
metadata column and its own ``created_at``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.marketplace_subscription import MarketplaceSubscription

logger = structlog.get_logger(__name__)

#: The value that means MANUAL. The DB CHECK constraint allows only
#: ('auto', 'one_click', 'offline', 'paper') — there is deliberately NO
#: 'manual' literal, and writing one would violate the constraint.
MANUAL_MODE = "offline"
AUTO_MODE = "auto"

#: audit_logs.action for the flip. Machine-readable and greppable.
DRIFT_FLIP_ACTION = "marketplace.subscription.auto_to_manual.broker_drift"
AUDIT_RESOURCE_TYPE = "marketplace_subscription"


class BrokerPositionFetcher(Protocol):
    """Fetches the subscriber's LIVE net position for one symbol.

    Mirrors the shape of the fan-out's ``SubscriberPositionProvider`` seam
    without importing it (see IMPORT DISCIPLINE above).

    Contract:
      * return the signed/absolute net quantity the BROKER reports, or
      * return ``None`` when the position is genuinely absent at the broker, or
      * RAISE when the broker could not be reached / answered.

    The distinction matters: ``None`` is evidence (broker says flat), a raised
    exception is the ABSENCE of evidence and must never cause a flip.
    """

    async def __call__(
        self, *, subscription: MarketplaceSubscription, symbol: str
    ) -> int | None: ...


@dataclass(frozen=True)
class DriftDecision:
    """Outcome of one drift check. ``flipped`` is the only side-effecting bit."""

    subscription_id: uuid.UUID
    #: True only when this call changed execution_mode auto → offline.
    flipped: bool
    #: Machine-readable outcome code (also written to audit metadata on a flip).
    reason: str
    #: What we believed we held.
    stored_quantity: int | None = None
    #: What the broker actually reports (None = flat/unknown, see `reason`).
    broker_quantity: int | None = None
    symbol: str | None = None
    #: Set only on a flip — the audit_logs row id.
    audit_log_id: uuid.UUID | None = None

    @property
    def drifted(self) -> bool:
        """Did we observe a real divergence (regardless of whether we flipped)?"""
        return self.reason in ("broker_flat", "broker_partial")


async def check_and_flip_subscription(
    db: AsyncSession,
    subscription: MarketplaceSubscription,
    *,
    symbol: str,
    stored_quantity: int,
    fetch_broker_position: BrokerPositionFetcher,
) -> DriftDecision:
    """Compare broker truth vs our stored quantity; flip AUTO→MANUAL on drift.

    Returns a :class:`DriftDecision` describing what happened. Commits only when
    it flips.

    Outcomes (``reason``):
      ``already_manual``      — subscription was not AUTO; idempotent no-op.
      ``broker_unavailable``  — the fetch raised; FAIL-SAFE, no flip.
      ``no_drift``            — broker holds at least what we think; no flip.
      ``broker_flat``         — broker holds nothing; DRIFT → flipped.
      ``broker_partial``      — broker holds less than stored; DRIFT → flipped.
    """
    sub_id = subscription.id

    # 1. IDEMPOTENT — only an AUTO subscription can be flipped to MANUAL. A
    #    subscription that is already manual (offline/one_click/paper) is left
    #    exactly as-is: no write, no audit row, no duplicate notification.
    current_mode = str(subscription.execution_mode or "").strip().lower()
    if current_mode != AUTO_MODE:
        logger.debug(
            "subscriber_drift.skip_already_manual",
            subscription_id=str(sub_id),
            execution_mode=current_mode,
        )
        return DriftDecision(
            subscription_id=sub_id,
            flipped=False,
            reason="already_manual",
            stored_quantity=stored_quantity,
            symbol=symbol,
        )

    # 2. BROKER TRUTH. A raised exception is the ABSENCE of evidence, not
    #    evidence of drift — an unreachable broker must NEVER cost a customer
    #    their AUTO mode. Fail safe: log loudly, change nothing.
    try:
        broker_quantity = await fetch_broker_position(
            subscription=subscription, symbol=symbol
        )
    except Exception as exc:
        logger.warning(
            "subscriber_drift.broker_unavailable",
            subscription_id=str(sub_id),
            symbol=symbol,
            error=str(exc),
            error_type=type(exc).__name__,
            flipped=False,
        )
        return DriftDecision(
            subscription_id=sub_id,
            flipped=False,
            reason="broker_unavailable",
            stored_quantity=stored_quantity,
            symbol=symbol,
        )

    # 3. COMPARE. Only a SHORTFALL is drift: the customer closed some or all of
    #    it themselves. Holding MORE than we recorded is not this bug (it is
    #    their own separate trade) and must not flip them.
    observed = 0 if broker_quantity is None else abs(int(broker_quantity))
    expected = abs(int(stored_quantity))

    if expected <= 0 or observed >= expected:
        return DriftDecision(
            subscription_id=sub_id,
            flipped=False,
            reason="no_drift",
            stored_quantity=expected,
            broker_quantity=observed,
            symbol=symbol,
        )

    reason = "broker_flat" if observed == 0 else "broker_partial"

    # 4. FLIP — per-subscription, and DELIBERATELY one-way. Nothing in this
    #    module (or anywhere else) flips it back: the customer must re-enable
    #    AUTO explicitly in settings. That is the founder's design.
    detected_at = datetime.now(UTC)
    subscription.execution_mode = MANUAL_MODE

    audit_metadata: dict[str, Any] = {
        "reason": reason,
        "previous_mode": AUTO_MODE,
        "new_mode": MANUAL_MODE,
        "symbol": symbol,
        "stored_quantity": expected,
        "broker_quantity": observed,
        "detected_at": detected_at.isoformat(),
        "auto_revert": False,
        "source": "subscriber_drift_service",
    }
    audit = AuditLog(
        user_id=subscription.subscriber_id,
        actor=ActorType.SYSTEM,
        action=DRIFT_FLIP_ACTION,
        resource_type=AUDIT_RESOURCE_TYPE,
        resource_id=str(sub_id),
        audit_metadata=audit_metadata,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    logger.warning(
        "subscriber_drift.flipped_to_manual",
        subscription_id=str(sub_id),
        subscriber_id=str(subscription.subscriber_id),
        symbol=symbol,
        stored_quantity=expected,
        broker_quantity=observed,
        reason=reason,
        audit_log_id=str(audit.id),
    )

    return DriftDecision(
        subscription_id=sub_id,
        flipped=True,
        reason=reason,
        stored_quantity=expected,
        broker_quantity=observed,
        symbol=symbol,
        audit_log_id=audit.id,
    )


__all__ = [
    "AUTO_MODE",
    "DRIFT_FLIP_ACTION",
    "MANUAL_MODE",
    "BrokerPositionFetcher",
    "DriftDecision",
    "check_and_flip_subscription",
]
