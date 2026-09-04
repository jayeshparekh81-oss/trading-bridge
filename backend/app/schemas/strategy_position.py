"""Pydantic schemas for ``strategy_positions`` — list API output + kill switch."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StrategyPositionRead(BaseModel):
    """Public read shape — used by GET /api/strategies/positions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_id: uuid.UUID
    broker_credential_id: uuid.UUID
    signal_id: uuid.UUID | None
    symbol: str
    side: str
    total_quantity: int
    remaining_quantity: int
    avg_entry_price: Decimal | None
    target_price: Decimal | None
    stop_loss_price: Decimal | None
    trail_offset: Decimal | None
    highest_price_seen: Decimal | None
    status: str
    opened_at: datetime
    closed_at: datetime | None
    final_pnl: Decimal | None
    #: ``bot_only`` | ``account_flat`` | ``human_interfered`` | ``unpriceable``
    #: | ``paper_sim`` | None (not yet attributed). A NULL ``final_pnl`` with
    #: ``human_interfered`` means "human-interfered — not attributable": the
    #: founder's manual fills on the same contract make the bot's exit price a
    #: guess, so nothing is published rather than a wrong number.
    pnl_attribution: str | None = None
    pnl_attribution_detail: str | None = None
    created_at: datetime


class StrategyPositionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positions: list[StrategyPositionRead] = Field(default_factory=list)
    count: int = Field(..., ge=0)


class KillSwitchResponse(BaseModel):
    """Response from POST /api/strategies/kill-switch."""

    model_config = ConfigDict(extra="forbid")

    positions_closed: int = Field(..., ge=0)
    signals_rejected: int = Field(
        default=0,
        ge=0,
        description="Pending signals (status=received/validating) marked rejected.",
    )
    message: str


__all__ = [
    "KillSwitchResponse",
    "StrategyPositionListResponse",
    "StrategyPositionRead",
]
