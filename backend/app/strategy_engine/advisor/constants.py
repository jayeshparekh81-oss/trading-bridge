"""Locked thresholds for the advisor + doctor.

Like Phase 4 / Phase 6, every magic number lives here so a future
re-tuning of the advisor's rule book is one diff away. Values that
mirror Phase 6's truth thresholds are imported, not redeclared.
"""

from __future__ import annotations

from typing import Final

#: Indicator-coverage rules.
#: A strategy with only one *category* of indicator (e.g. only trend
#: indicators) gets nudged toward adding a confirmation indicator.
TREND_INDICATOR_TYPES: Final[frozenset[str]] = frozenset(
    {"ema", "sma", "wma", "vwap"}
)
MOMENTUM_INDICATOR_TYPES: Final[frozenset[str]] = frozenset(
    {"rsi", "macd"}
)
VOLATILITY_INDICATOR_TYPES: Final[frozenset[str]] = frozenset(
    {"bollinger_bands", "atr"}
)
VOLUME_INDICATOR_TYPES: Final[frozenset[str]] = frozenset(
    {"obv", "volume_sma"}
)

#: Above this count the advisor flags "indicator overload" — too many
#: signals tend to over-fit and produce conflicting entries.
INDICATOR_OVERLOAD_THRESHOLD: Final[int] = 5

#: Trust score below this gets a "paper trade extensively" recommendation.
LOW_TRUST_SCORE_THRESHOLD: Final[int] = 70

#: Truth score below this kills any live-trading recommendation. The
#: advisor will recommend paper trading instead.
POOR_TRUTH_SCORE_THRESHOLD: Final[int] = 55

#: Truth score at or above which the advisor considers live trading
#: (paper-trade-first recommendation always also fires below this).
LIVE_READY_TRUTH_SCORE: Final[int] = 85

#: Drawdown above which the advisor recommends reducing position size.
HIGH_DRAWDOWN_ADVISORY_THRESHOLD: Final[float] = 0.30


__all__ = [
    "HIGH_DRAWDOWN_ADVISORY_THRESHOLD",
    "INDICATOR_OVERLOAD_THRESHOLD",
    "LIVE_READY_TRUTH_SCORE",
    "LOW_TRUST_SCORE_THRESHOLD",
    "MOMENTUM_INDICATOR_TYPES",
    "POOR_TRUTH_SCORE_THRESHOLD",
    "TREND_INDICATOR_TYPES",
    "VOLATILITY_INDICATOR_TYPES",
    "VOLUME_INDICATOR_TYPES",
]
