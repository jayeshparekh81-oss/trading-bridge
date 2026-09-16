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


class StrategyExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executions: list[StrategyExecutionRead] = Field(default_factory=list)
    count: int = Field(..., ge=0)


__all__ = ["StrategyExecutionListResponse", "StrategyExecutionRead"]
