"""Threshold constants for the Broker Execution Guard.

Locked at module scope so the orchestrator + checks share a single
source of truth, and tests can pin behaviour against named bounds
rather than magic numbers.

Units:
    * ``MIN_TRUTH_SCORE_FOR_LIVE`` and ``MIN_TRUST_SCORE_FOR_LIVE`` —
      0-100 integer scores from the Phase 6 / Phase 4 engines.
    * ``HIGH_DRAWDOWN_WARNING`` — *fraction* (0.0-1.0+) matching
      :attr:`BacktestResult.max_drawdown`. ``0.25`` means "warn when
      historical drawdown exceeded 25 %".
    * ``LOW_TRADE_COUNT_WARNING`` — minimum sample size below which the
      backtest's stats are considered noisy.
    * ``RECOMMENDED_PAPER_SESSIONS`` — informational target; not a hard
      gate (paper-readiness has its own minimum at the engine layer).
"""

from __future__ import annotations

MIN_TRUTH_SCORE_FOR_LIVE: int = 55
MIN_TRUST_SCORE_FOR_LIVE: int = 70
HIGH_DRAWDOWN_WARNING: float = 0.25
LOW_TRADE_COUNT_WARNING: int = 30
RECOMMENDED_PAPER_SESSIONS: int = 14


__all__ = [
    "HIGH_DRAWDOWN_WARNING",
    "LOW_TRADE_COUNT_WARNING",
    "MIN_TRUST_SCORE_FOR_LIVE",
    "MIN_TRUTH_SCORE_FOR_LIVE",
    "RECOMMENDED_PAPER_SESSIONS",
]
