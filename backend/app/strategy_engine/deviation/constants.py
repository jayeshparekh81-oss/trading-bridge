"""Threshold constants for the Live-vs-Backtest Deviation Monitor.

Locked at module scope so the metrics, scorer, and tests share a
single source of truth. The numbers come from the spec block in
``prompts/master-plan-final.md``; if they ever need to move, *only*
this file should change.

Threshold encoding (consistent across all four metrics):

    ``THRESHOLDS = (watch_min, warning_min, critical_min)``

i.e. a value in ``[0, watch_min)`` is ``normal``,
``[watch_min, warning_min)`` is ``watch``, and so on. The metric
functions read these tuples directly so band transitions are
inspectable without re-deriving the boundaries.

Severity → numeric score map drives the aggregate ``deviation_score``
(0-100 average across the metrics that actually ran).
"""

from __future__ import annotations

from typing import Final

# ─── Insufficient-data gate ────────────────────────────────────────────

MIN_TRADES_FOR_EVAL: Final[int] = 10

# ─── Per-metric severity thresholds ────────────────────────────────────

# Win-rate diff (absolute percentage points; ``abs(expected - actual)``).
WIN_RATE_THRESHOLDS: Final[tuple[float, float, float]] = (0.10, 0.20, 0.30)

# Drawdown ratio (``actual / expected``). One-sided — actual lower than
# expected stays in ``normal``. Tuple is ``(watch_min, warning_min,
# critical_min)``: above these multipliers the band escalates.
DRAWDOWN_MULTIPLIERS: Final[tuple[float, float, float]] = (1.2, 1.5, 2.0)

# Profit-factor relative drop (``(expected - actual) / expected``).
# Negative drops (actual >= expected) trivially stay in ``normal``.
PROFIT_FACTOR_DROP_PCT: Final[tuple[float, float, float]] = (0.15, 0.30, 0.50)

# Trade-frequency relative diff (``abs(expected - actual) / expected``).
TRADE_FREQ_THRESHOLDS: Final[tuple[float, float, float]] = (0.25, 0.50, 0.75)

# ─── Severity → numeric score (drives deviation_score average) ─────────

SEVERITY_SCORE: Final[dict[str, float]] = {
    "normal": 0.0,
    "watch": 25.0,
    "warning": 60.0,
    "critical": 100.0,
}

# Severity comparator order — used by the scorer to pick the worst
# severity across all metrics as the report's overall ``status``.
SEVERITY_RANK: Final[dict[str, int]] = {
    "normal": 0,
    "watch": 1,
    "warning": 2,
    "critical": 3,
}


__all__ = [
    "DRAWDOWN_MULTIPLIERS",
    "MIN_TRADES_FOR_EVAL",
    "PROFIT_FACTOR_DROP_PCT",
    "SEVERITY_RANK",
    "SEVERITY_SCORE",
    "TRADE_FREQ_THRESHOLDS",
    "WIN_RATE_THRESHOLDS",
]
