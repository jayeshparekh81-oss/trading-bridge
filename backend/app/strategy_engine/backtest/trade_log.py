"""Trade + equity row models for the backtest output.

Both models are frozen Pydantic so they're hashable and round-trip cleanly
through ``model_dump()`` / ``model_validate()``. The runner accumulates
``Trade`` instances as positions close and emits one ``EquityPoint`` per
candle — the equity curve is *always* same-length as the input candles
even when no trade closes that bar (carry the prior equity forward).

``Trade.entry_reasons`` mirrors :class:`EntryDecision.reasons` from the
Phase 2 entry engine so the AI advisor (Phase 6) can show the user
exactly which conditions matched at entry time.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.schema.strategy import Side


class Trade(BaseModel):
    """Closed-trade audit row — appended to ``BacktestResult.trades``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_time: datetime
    exit_time: datetime
    side: Side
    entry_price: float = Field(..., gt=0)
    exit_price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    pnl: float
    exit_reason: str = Field(..., min_length=1, max_length=128)
    entry_reasons: tuple[str, ...] = Field(default_factory=tuple)


class EquityPoint(BaseModel):
    """One sample on the equity curve. ``equity`` is mark-to-market.

    Phase 3 marks-to-market on candle close: ``equity[i] = capital +
    realised_pnl_so_far + unrealised_pnl_at_close[i]``. Trade-close bars
    fold the realised P&L in immediately so the curve is continuous.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    equity: float


__all__ = ["EquityPoint", "Trade"]
