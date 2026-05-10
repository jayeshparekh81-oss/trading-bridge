"""Boundary models for the Deviation Monitor.

All models are frozen + ``extra="forbid"`` so the report flows through
the rest of the engine (UI, advisor, kill-switch wiring future phase)
as an immutable snapshot.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["normal", "watch", "warning", "critical"]


class LiveTradingStats(BaseModel):
    """Aggregated live / paper performance stats for deviation comparison.

    The caller is responsible for aggregating these from the underlying
    paper trade list or live broker positions — this module is consumer-
    side, pure math. ``LiveTradingStats`` is the *complete* shape: when
    the caller hands in a :class:`PaperReadinessReport` instead, the
    monitor degrades gracefully and only runs the metrics whose inputs
    are available.

    Field semantics:

        * ``total_trades`` — count of closed trades aggregated.
        * ``sessions``    — distinct trading days / paper sessions; ``>= 1``
          when ``total_trades > 0`` so trade-frequency math has a divisor.
        * ``win_rate``    — winning trades / total trades, ``0..1``.
        * ``profit_factor`` — gross_profit / gross_loss, ``>= 0``;
          callers cap at a finite sentinel when no losing trades exist.
        * ``max_drawdown`` — peak-to-trough equity decline as a
          fraction (``0..1+``).
        * ``total_pnl``   — net P&L; carried for context, not a band.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_trades: int = Field(..., ge=0)
    sessions: int = Field(..., ge=0)
    win_rate: float = Field(..., ge=0, le=1)
    profit_factor: float = Field(..., ge=0)
    max_drawdown: float = Field(..., ge=0)
    total_pnl: float


class DeviationMetric(BaseModel):
    """One side-by-side comparison between backtest and live/paper.

    ``deviation_percent`` is the relative deviation in percent
    (``(actual - expected) / abs(expected) * 100``); signed so callers
    can see direction. Severity is the band the diff lands in per the
    metric-specific thresholds in :mod:`constants`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str = Field(..., min_length=1, max_length=64)
    expected: float
    actual: float
    deviation_percent: float
    severity: Severity
    hinglish_message: str = Field(..., min_length=1, max_length=512)


class DeviationReport(BaseModel):
    """Top-level monitor output.

    Decision flags (``should_pause`` / ``should_reduce_size`` /
    ``should_switch_to_paper``) follow the locked status → action map:

        * ``critical`` — pause + paper + reduce
        * ``warning``  — paper + reduce
        * ``watch``    — flags all False (status conveys the concern)
        * ``normal``   — flags all False

    ``auto_kill_switch_signal`` is a *read-only advisory* — this module
    never invokes the actual kill switch. Wiring the boolean into the
    real safety system is a separate future phase by design.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    deviation_score: float = Field(..., ge=0, le=100)
    status: Severity
    deviations: tuple[DeviationMetric, ...] = Field(default_factory=tuple)
    recommended_actions: tuple[str, ...] = Field(default_factory=tuple)
    should_pause: bool
    should_reduce_size: bool
    should_switch_to_paper: bool
    hinglish_summary: str = Field(..., min_length=1, max_length=512)
    auto_kill_switch_signal: bool


__all__ = [
    "DeviationMetric",
    "DeviationReport",
    "LiveTradingStats",
    "Severity",
]
