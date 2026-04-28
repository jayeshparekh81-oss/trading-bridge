"""Pydantic schemas for ``strategy_executions`` — list/detail API output."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrategyExecutionRead(BaseModel):
    """Public read shape — used by GET /api/strategies/executions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    signal_id: uuid.UUID
    broker_credential_id: uuid.UUID
    leg_number: int
    leg_role: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    price: Decimal | None
    broker_order_id: str | None
    broker_status: str | None
    broker_response: dict[str, Any] | None
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
