"""Two kill switches for the customer lane, and nothing else.

GLOBAL   — ``CUSTOMER_LANE_KILL_ALL``. One env var stops every customer at once.
PER-CUSTOMER — ``CustomerLinkStatus.DISABLED``. Stops exactly one customer.

BLAST RADIUS IS THE POINT. Neither switch touches the founder's own BSE live
strategy, the webhook, the executor, or ``app/brokers/dhan.py``. This module imports
none of them. Killing the customer lane must never stop the founder's own money.

The global switch is read FRESH at every check. A worker that has been up for hours
must see a kill the moment it is set, not at its next restart.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer_lane import CustomerBrokerLink, CustomerLinkStatus
from app.domains.customer_lane import config as lane_config

logger = logging.getLogger("customer_lane.kill")


class LaneKilled(RuntimeError):
    """Raised whenever a kill switch forbids an act. Always loud, never a silent skip."""


def global_kill_engaged() -> bool:
    return lane_config.load().kill_all


async def kill_customer(session: AsyncSession, customer_id: uuid.UUID, *,
                        reason: str) -> None:
    """Stop ONE customer. Their token is left intact so this is reversible."""
    link = (await session.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == customer_id))).scalar_one_or_none()
    if link is None:
        raise LaneKilled(f"no broker link for {customer_id}")
    link.status = CustomerLinkStatus.DISABLED
    await session.flush()
    logger.warning("customer lane KILLED customer=%s reason=%s at=%s",
                   customer_id, reason, datetime.now(timezone.utc).isoformat())


async def revive_customer(session: AsyncSession, customer_id: uuid.UUID) -> None:
    """Undo a per-customer kill. The customer must reconnect to trade again: we drop
    them to NEVER_CONNECTED rather than assuming their old token is still good."""
    link = (await session.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == customer_id))).scalar_one_or_none()
    if link is None:
        raise LaneKilled(f"no broker link for {customer_id}")
    link.status = CustomerLinkStatus.NEVER_CONNECTED
    await session.flush()
    logger.warning("customer lane revived customer=%s", customer_id)


def assert_lane_permitted(customer_id: uuid.UUID) -> None:
    """The global gate. Per-customer kill is enforced by is_connected(), which is
    the single source; this function deliberately does not duplicate that logic."""
    if global_kill_engaged():
        raise LaneKilled(
            "CUSTOMER_LANE_KILL_ALL is engaged; the entire customer lane refuses")


__all__ = ["LaneKilled", "global_kill_engaged", "kill_customer", "revive_customer",
           "assert_lane_permitted"]
