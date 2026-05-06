"""Threshold constants for the Market Regime detector.

All units + windows are locked here so the classifier and tests share
a single source of truth. The numbers come from the spec block in
``prompts/master-plan-final.md``; if they ever need to move, *only*
this file should change.

Units:
    * ``ADX_*`` — 0-100 ADX line value (Wilder's DMS).
    * ``MA_SLOPE_*`` — percent change of the 20-period SMA over the
      slope window (default 5 bars).
    * ``RANGE_COMPRESSION_*`` — ratio of the last-window high-low range
      to the previous-window range. ``< 1.0`` means compression.
    * ``ATR_PERCENTILE_*`` — percentile (0-1) of current ATR in the
      ATR distribution computed from the candle history.
    * ``GAP_PCT`` — fraction (e.g. ``0.01`` ≡ 1 %) of previous close.
    * ``DIRECTION_CHANGES_*`` — count of close-to-close sign flips in
      the most recent ``DIRECTION_WINDOW`` bars.
    * ``ABNORMAL_PRICE_MOVE`` — fraction (single-bar move).
"""

from __future__ import annotations

# ─── Window sizes ──────────────────────────────────────────────────────

ADX_PERIOD: int = 14
ATR_PERIOD: int = 14
MA_PERIOD: int = 20
MA_SLOPE_WINDOW: int = 5
RANGE_WINDOW: int = 20
DIRECTION_WINDOW: int = 30

# ─── Trending / sideways thresholds ────────────────────────────────────

ADX_TRENDING_MIN: float = 25.0
ADX_SIDEWAYS_MAX: float = 20.0
MA_SLOPE_TRENDING_MIN_PERCENT: float = 0.5

# ─── Range / compression / breakout ────────────────────────────────────

RANGE_COMPRESSION_SIDEWAYS_MAX: float = 0.7
RANGE_COMPRESSION_BREAKOUT_PRIOR_MAX: float = 0.5
RANGE_EXPANSION_BREAKOUT_MIN: float = 1.5

# ─── Volatility (ATR percentile) ───────────────────────────────────────

ATR_PERCENTILE_HIGH: float = 0.90
ATR_PERCENTILE_LOW: float = 0.20
ATR_PERCENTILE_ABNORMAL: float = 0.99

# ─── Gap detection ─────────────────────────────────────────────────────

GAP_PCT: float = 0.01  # 1 % of previous close

# ─── Choppiness ────────────────────────────────────────────────────────

DIRECTION_CHANGES_CHOPPY_MIN: int = 12

# ─── Abnormal single-bar move ──────────────────────────────────────────

ABNORMAL_PRICE_MOVE: float = 0.05  # 5 % in one bar


__all__ = [
    "ABNORMAL_PRICE_MOVE",
    "ADX_PERIOD",
    "ADX_SIDEWAYS_MAX",
    "ADX_TRENDING_MIN",
    "ATR_PERCENTILE_ABNORMAL",
    "ATR_PERCENTILE_HIGH",
    "ATR_PERCENTILE_LOW",
    "ATR_PERIOD",
    "DIRECTION_CHANGES_CHOPPY_MIN",
    "DIRECTION_WINDOW",
    "GAP_PCT",
    "MA_PERIOD",
    "MA_SLOPE_TRENDING_MIN_PERCENT",
    "MA_SLOPE_WINDOW",
    "RANGE_COMPRESSION_BREAKOUT_PRIOR_MAX",
    "RANGE_COMPRESSION_SIDEWAYS_MAX",
    "RANGE_EXPANSION_BREAKOUT_MIN",
    "RANGE_WINDOW",
]
