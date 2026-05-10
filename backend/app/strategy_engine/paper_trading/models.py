"""Pydantic boundary models for the Paper Trading Engine.

All three models are frozen + ``extra="forbid"`` so:

    * Tests can deep-equal model dumps for the determinism check.
    * The engine cannot mutate a returned snapshot by accident.
    * Stale fields surface loudly during a future schema change.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.strategy_engine.schema.strategy import Side


class PaperSession(BaseModel):
    """Public snapshot of a paper-trading session.

    Mutable engine state is held privately inside :mod:`engine`; this
    snapshot is what the caller sees. ``ended_at`` is ``None`` while
    the session is still accepting candles.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: uuid.UUID
    strategy_id: str = Field(..., min_length=1, max_length=128)
    user_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None = None
    candles_processed: int = Field(default=0, ge=0)


class PaperTrade(BaseModel):
    """One closed paper trade.

    ``pnl`` is computed from ``side``, ``entry_price``, ``exit_price``,
    and ``qty`` in a ``model_validator`` so the four fields stay
    consistent — no caller can hand the engine a trade with a PnL that
    contradicts its prices.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: uuid.UUID
    entry_time: datetime
    exit_time: datetime
    side: Side
    entry_price: float = Field(..., gt=0)
    exit_price: float = Field(..., gt=0)
    qty: float = Field(..., gt=0)
    pnl: float
    exit_reason: str = Field(..., min_length=1, max_length=128)
    entry_reasons: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _pnl_matches_prices(self) -> PaperTrade:
        if self.side is Side.BUY:
            expected = (self.exit_price - self.entry_price) * self.qty
        else:
            expected = (self.entry_price - self.exit_price) * self.qty
        if abs(expected - self.pnl) > 1e-6:
            raise ValueError(
                f"pnl ({self.pnl}) inconsistent with side / prices / qty; "
                f"expected {expected} from "
                f"({self.side.value}, {self.entry_price}, {self.exit_price}, {self.qty})."
            )
        if self.exit_time < self.entry_time:
            raise ValueError("exit_time must be >= entry_time.")
        return self


class PaperReadinessReport(BaseModel):
    """Live-readiness verdict from N completed paper sessions.

    Five gates (locked):

        completed_sessions >= 7
        paper_pnl > 0
        paper_win_rate >= 0.40
        rule_adherence_percent >= 80
        strategy has a stop loss configured

    Truth-score / trust-score gating belongs to the upcoming Broker
    Guard phase — those are deliberately *not* part of this report.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed_sessions: int = Field(..., ge=0)
    paper_pnl: float
    paper_win_rate: float = Field(..., ge=0, le=1)
    rule_adherence_percent: float = Field(..., ge=0, le=100)
    live_ready: bool
    blocked_reasons: tuple[str, ...] = Field(default_factory=tuple)


__all__ = [
    "PaperReadinessReport",
    "PaperSession",
    "PaperTrade",
]
