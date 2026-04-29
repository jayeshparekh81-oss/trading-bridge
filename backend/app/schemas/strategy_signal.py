"""Pydantic schemas for ``strategy_signals`` — webhook in, API out."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrategySignalRead(BaseModel):
    """Public read shape — used by GET /api/strategies/signals."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_id: uuid.UUID
    raw_payload: dict[str, Any]
    symbol: str
    action: str
    quantity: int | None
    order_type: str | None
    ai_decision: str | None
    ai_reasoning: str | None
    ai_confidence: Decimal | None
    status: str
    notes: str | None
    received_at: datetime
    validated_at: datetime | None
    processed_at: datetime | None
    created_at: datetime


class StrategySignalListResponse(BaseModel):
    """Wrapper returned by the list endpoint — keeps `count` close to data."""

    model_config = ConfigDict(extra="forbid")

    signals: list[StrategySignalRead] = Field(default_factory=list)
    count: int = Field(..., ge=0)


__all__ = ["StrategySignalListResponse", "StrategySignalRead"]
