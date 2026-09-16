"""Pydantic schemas for ``strategy_executions`` — list/detail API output."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StrategyExecutionRead(BaseModel):
    """Public read shape — used by GET /api/strategies/executions.

    ⛔ THE RAW BROKER PAYLOAD IS NOT IN THIS SHAPE, DELIBERATELY. ⛔
    This model used to carry ``broker_response``, which is Dhan's verbatim
    reply — ``dhanClientId``, ``exchangeOrderId``, ``securityId``,
    ``exchangeSegment``, the whole envelope — and it was serialised straight
    to the browser on every page load of the trades tab. A customer needs the
    broker's STATUS from that reply and nothing else, so the status is
    extracted server-side by ``owner_executions.broker_status_of`` and the
    payload stays where it belongs.

    ``broker_credential_id`` is gone for the same reason: it is an internal
    row id that identifies which credential placed the order, and no surface
    renders it.

    If you are adding a field here, ask what a CUSTOMER does with it. A field
    nobody renders is a field that can only leak.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    signal_id: uuid.UUID
    leg_number: int
    leg_role: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    price: Decimal | None
    broker_order_id: str | None
    #: The broker's own status, extracted from the response body. ``None``
    #: means we have not read one — the UI renders a dash, never "pending".
    broker_status: str | None
    error_code: str | None
    error_message: str | None
    placed_at: datetime
    completed_at: datetime | None
    created_at: datetime


class BrokerFillRead(BaseModel):
    """A fill that happened at the BROKER with no order of ours behind it.

    These are not ``strategy_executions`` rows and never become them — see
    :mod:`app.services.broker_fills`. They are served alongside, labelled, so
    the orders page can stop being silent about half the account: the engine's
    own resting-stop exits and the founder's manual Dhan-app trades.

    Same projection discipline as ``StrategyExecutionRead`` — the broker
    envelope (``dhanClientId``, ``exchangeOrderId``, ``securityId``) stays on
    the server. Only what the page renders crosses the wire.
    """

    model_config = ConfigDict(extra="forbid")

    broker_order_id: str
    symbol: str
    side: str
    quantity: int
    price: Decimal | None
    #: Broker exchange time as the broker reported it. ``None`` when absent —
    #: the UI shows a dash, never a substituted timestamp.
    filled_at: str | None
    #: ``engine_stop`` (pine_replica's Forever/GTT child), ``manual`` (Dhan
    #: app), or ``unknown``. Never forced into the nearest bucket.
    source: str


class StrategyExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executions: list[StrategyExecutionRead] = Field(default_factory=list)
    count: int = Field(..., ge=0)
    #: Fills the broker has that this platform never placed. A SEPARATE list,
    #: not merged into ``executions``: those are our orders and carry our ids,
    #: these carry neither. The page renders both and labels each.
    broker_fills: list[BrokerFillRead] = Field(default_factory=list)
    #: False when the broker-fill cache has never been populated. The page must
    #: then say the account view is unavailable rather than implying the
    #: account was quiet — an empty list is UNKNOWN, not "nothing happened".
    broker_fills_known: bool = False


__all__ = [
    "BrokerFillRead",
    "StrategyExecutionListResponse",
    "StrategyExecutionRead",
]
