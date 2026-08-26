"""Deliver ``notify_only`` fan-out results to the SUBSCRIBER.

WHAT THIS FIXES
---------------
The fan-out already COMPUTES the customer-facing message for a MANUAL
subscriber — both on entry and on exit it emits a result with
``status="notify_only"`` and a ``notify_message`` naming exactly what the
customer would have to do themselves. Nothing consumed it: the results were
returned and dropped, so the customer was never told. This module is that
missing delivery leg.

⚠️ CHANNEL DISCIPLINE — THE POINT OF THIS FILE
----------------------------------------------
Customer notifications go through ``NotificationService.send(user_id=…)``,
which resolves the recipient from the ``users`` row and honours their
preferences (email + their OWN ``telegram_chat_id``).

They must NEVER go through ``telegram_alerts.send_alert``: that is the
OPERATOR's single global chat (``settings.telegram_alert_chat_id``) and a
customer message landing there is an information leak to the wrong audience.
The fan-out's ``_alert_subscriber_failure`` is exactly that anti-pattern — it
mentions the subscriber but delivers to the operator — which is why the test
suite asserts this module never touches that channel.

IMPORT DISCIPLINE
-----------------
Must NOT import ``app.services.marketplace_fanout`` (an invariant test pins it
to two sanctioned importers). The result objects are therefore accepted
STRUCTURALLY via the Protocol below, which the fan-out's ``PaperExecutionResult``
satisfies without either module knowing about the other.

WIRING STATUS
-------------
This is a complete, tested primitive with NO production call site yet: the
fan-out's return value is consumed inside ``marketplace_fanout.py`` and its two
sacred callers, all of which are out of scope for this step. Hooking it up is
the separate, gated diff.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from typing import Any, Protocol, runtime_checkable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

#: The fan-out status that means "we told them, we placed nothing".
NOTIFY_ONLY_STATUS = "notify_only"

#: NotificationService event type for these messages.
#:
#: Deliberately NOT ``order_failed``: that template renders "❌ Order Failed",
#: which would be a lie here. Nothing failed — the customer is in MANUAL mode
#: and we placed nothing BY DESIGN. Telling them an order failed invites panic
#: or a wrong corrective action. This event type has its own templates
#: (telegram/subscriber_manual_action.txt, email/subscriber_manual_action.html)
#: whose copy says plainly that no order was placed and why.
NOTIFY_EVENT_TYPE = "subscriber_manual_action"


@runtime_checkable
class NotifyOnlyResult(Protocol):
    """Structural view of the fan-out's ``PaperExecutionResult``.

    Only the fields this module reads are declared, so it stays decoupled from
    the fan-out's dataclass (see IMPORT DISCIPLINE).
    """

    subscription_id: uuid.UUID
    subscriber_id: uuid.UUID
    symbol: str
    action: str
    quantity: int
    status: str
    notify_message: str | None


async def deliver_notify_only(
    db: AsyncSession,
    results: Sequence[Any] | Iterable[Any],
    *,
    notification_service: Any | None = None,
) -> list[dict[str, Any]]:
    """Send each ``notify_only`` result to its OWN subscriber.

    Non-``notify_only`` results are ignored, as are results carrying no
    message. Delivery failures are logged and never raised: a notification
    problem must not break the caller's execution path.

    Returns one delivery record per attempted send (for logging/tests).
    """
    if notification_service is None:
        # Imported lazily so this module stays cheap to import and easy to stub.
        from app.services.notification_service import notification_service as _svc

        notification_service = _svc

    delivered: list[dict[str, Any]] = []

    for result in results or []:
        status = str(getattr(result, "status", "") or "").strip().lower()
        if status != NOTIFY_ONLY_STATUS:
            continue

        message = getattr(result, "notify_message", None)
        subscriber_id = getattr(result, "subscriber_id", None)
        if not message or subscriber_id is None:
            logger.debug(
                "subscriber_notify.skipped_incomplete",
                subscription_id=str(getattr(result, "subscription_id", "")),
                has_message=bool(message),
            )
            continue

        context = {
            "message": message,
            "symbol": getattr(result, "symbol", None),
            "action": getattr(result, "action", None),
            "quantity": getattr(result, "quantity", None),
            "subscription_id": str(getattr(result, "subscription_id", "")),
            # Explicit: this is an informational notice, not a filled order.
            "placed": False,
            "reason": "manual_mode_notify_only",
        }

        try:
            # PER-USER channel only. Never telegram_alerts.send_alert.
            outcome = await notification_service.send(
                user_id=subscriber_id,
                event_type=NOTIFY_EVENT_TYPE,
                context=context,
                db=db,
            )
        except Exception as exc:
            logger.warning(
                "subscriber_notify.failed",
                subscriber_id=str(subscriber_id),
                symbol=context["symbol"],
                error=str(exc),
                error_type=type(exc).__name__,
            )
            delivered.append(
                {
                    "subscriber_id": str(subscriber_id),
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue

        logger.info(
            "subscriber_notify.sent",
            subscriber_id=str(subscriber_id),
            subscription_id=context["subscription_id"],
            symbol=context["symbol"],
            outcome=outcome,
        )
        delivered.append(
            {
                "subscriber_id": str(subscriber_id),
                "status": "sent",
                "channels": outcome,
            }
        )

    return delivered


__all__ = [
    "NOTIFY_EVENT_TYPE",
    "NOTIFY_ONLY_STATUS",
    "NotifyOnlyResult",
    "deliver_notify_only",
]
