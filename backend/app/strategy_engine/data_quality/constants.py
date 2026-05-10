"""Locked thresholds for the Data Quality validator.

All values are intentionally tunable in one place — the checks read
them at call time so a constant edit propagates without touching the
check logic. Keep this module dependency-free.
"""

from __future__ import annotations

EXPECTED_TIMEFRAME_TOLERANCE: float = 1.5
"""Multiplier above which an inter-candle gap stops being a no-op and
becomes a quality concern. Inside ``[1.0, 1.5]`` the gap is treated as
on-time even with rounding/clock-drift slack."""

GAP_WARNING_MULTIPLIER: float = 2.0
"""Boundary between time-gap warning and missing-candle critical.
``tolerance < ratio <= warning`` → time-gap (warning); ``ratio >
warning`` → missing-candle (critical). Mutually exclusive ranges so a
single gap event never produces two issues."""

ZERO_VOLUME_THRESHOLD: float = 0.05
"""Maximum fraction (0-1) of zero-volume candles tolerated before the
liquidity warning fires."""

QUALITY_FLOOR_FOR_BACKTEST: float = 40.0
"""Minimum :class:`DataQualityReport.quality_score` below which
``can_backtest`` is forced to ``False`` regardless of issue mix."""

MAX_MISSING_PERCENT: float = 0.10
"""Estimated missing-candle fraction (0-1) above which ``can_backtest``
is forced to ``False``. Computed from the expected-vs-actual candle
count derived from inter-candle gaps."""

CRITICAL_PENALTY: float = 10.0
"""Quality-score deduction per critical issue."""

WARNING_PENALTY: float = 2.0
"""Quality-score deduction per warning issue."""

INFO_PENALTY: float = 0.5
"""Quality-score deduction per info issue."""


__all__ = [
    "CRITICAL_PENALTY",
    "EXPECTED_TIMEFRAME_TOLERANCE",
    "GAP_WARNING_MULTIPLIER",
    "INFO_PENALTY",
    "MAX_MISSING_PERCENT",
    "QUALITY_FLOOR_FOR_BACKTEST",
    "WARNING_PENALTY",
    "ZERO_VOLUME_THRESHOLD",
]
