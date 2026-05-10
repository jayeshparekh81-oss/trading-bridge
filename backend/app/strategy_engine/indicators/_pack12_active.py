"""Pack 12 — 12 volatility regime + risk-adjusted + volatility band indicators.

Discovery-time near-collision (handled honestly):

    * ``realized_volatility`` would compute the same numbers as the
      already-active ``historical_volatility`` (annualised stddev
      of log returns). Same Pack-10 lesson — duplicate calc under
      a different id is LOC without signal.
      → substituted with ``parkinson_volatility`` (Michael
        Parkinson's 1980 estimator, uses high-low *range* — about
        5x more efficient than close-to-close stddev when intraday
        range data is available). Distinct mechanism, distinct
        formula, distinct numbers.

Three near-collisions that ARE genuinely different + ship as-is:

    * ``chandelier_exit_long`` (trails from the recent peak high)
      vs ``atr_trailing_stop`` (ratchets from the current close)
      vs the existing ``supertrend`` (switches direction). Three
      mechanically-distinct trailing-stop concepts; all useful.

    * ``supertrend_v2`` extends the existing ``supertrend`` with
      an *adaptive* multiplier: scales 0.7x-1.3x of the base
      ``atr_mult`` based on the volatility regime (calm → tighten,
      extreme → widen). Reduces classic Supertrend whipsaw in
      low-volatility chop while still capturing trends in high-
      vol markets.

NO new Pine importer wiring — none of Pack 12's indicators have
a standard Pine v5 ``ta.*`` equivalent. The cycle indicators are
custom; chandelier / ATR-stop variants are common-knowledge
formulations with no Pine builtin.

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT — schema has no
ADVANCED tier; spec's "ADVANCED" mapped to EXPERT):

    INTERMEDIATE (5) — atr_percent, volatility_ratio,
                       chandelier_exit_long, chandelier_exit_short,
                       atr_trailing_stop
    EXPERT (7)       — volatility_regime, parkinson_volatility,
                       trade_efficiency, ulcer_index, martin_ratio,
                       burke_ratio, supertrend_v2

Honest scope notes:

* ``martin_ratio`` and ``burke_ratio`` return ``+inf`` / ``-inf``
  when their denominators are zero (no drawdowns in the window
  and a positive / negative period return). MFI's 0-100 normalisation
  doesn't apply here — these are unbounded ratios. Caller branches
  on the sentinel; tested.
* ``trade_efficiency`` is *signed* (uses raw ``net``, not
  ``abs(net)``) — preserves direction so trend-following
  strategies get both strength + direction in one number. The
  closely-related Kaufman Efficiency Ratio (used inside
  ``kaufman_ama``) is the unsigned variant.
"""

from __future__ import annotations

from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
    InputSpec,
    InputType,
)

# ─── Volatility Regime (4) ────────────────────────────────────────────


_ATR_PERCENT = IndicatorMetadata(
    id="atr_percent",
    name="ATR %",
    category="Volatility",
    description=(
        "ATR expressed as a percentage of close. Comparable across "
        "symbols + price levels (raw ATR isn't)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ATR % normalised volatility — NIFTY ka 1% ATR aur "
        "RELIANCE ka 1% ATR ek hi scale pe compare ho jaata hai. "
        "Position sizing input ke liye useful."
    ),
    tags=["volatility", "atr"],
    calculation_function="atr_percent",
)


_VOLATILITY_REGIME = IndicatorMetadata(
    id="volatility_regime",
    name="Volatility Regime",
    category="Volatility",
    description=(
        "Calm (0) / Normal (1) / Elevated (2) / Extreme (3) "
        "classifier based on ATR-percent quartiles over the "
        "trailing window."
    ),
    inputs=[
        InputSpec(
            name="lookback", type=InputType.NUMBER, default=100, min=4, max=1000,
        ),
        InputSpec(
            name="atr_period", type=InputType.NUMBER, default=14, min=2, max=200,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Volatility Regime market ko 4 buckets mein classify "
        "karta hai. 0=Calm (mean-reversion strategies), 3=Extreme "
        "(stay flat or wide stops). Strategy switching ke liye."
    ),
    tags=["volatility", "regime"],
    calculation_function="volatility_regime",
)


_PARKINSON_VOLATILITY = IndicatorMetadata(
    id="parkinson_volatility",
    name="Parkinson Volatility",
    category="Volatility",
    description=(
        "Annualised volatility from bar high-low *range* "
        "(Parkinson, 1980). About 5x more efficient than "
        "close-to-close stddev (the standard "
        "``historical_volatility``) when intraday range info is "
        "available."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(
            name="bars_per_year", type=InputType.NUMBER,
            default=252, min=1, max=525600,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Parkinson Volatility high-low range use karta hai (close-"
        "to-close ki jagah). Statistically zyada efficient — "
        "intraday range information capture karta hai."
    ),
    tags=["volatility", "estimator"],
    calculation_function="parkinson_volatility",
)


_VOLATILITY_RATIO = IndicatorMetadata(
    id="volatility_ratio",
    name="Volatility Ratio (Short/Long ATR)",
    category="Volatility",
    description=(
        "Short-term ATR divided by long-term ATR. > 1 = short-"
        "term volatility elevated relative to baseline (regime "
        "change brewing); < 1 = calm relative to baseline."
    ),
    inputs=[
        InputSpec(name="short", type=InputType.NUMBER, default=5, min=2, max=200),
        InputSpec(name="long", type=InputType.NUMBER, default=20, min=3, max=400),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Volatility Ratio short/long ATR ratio. >1.5 = short-term "
        "spike (regime change), <0.7 = unusual calm (squeeze pre-"
        "breakout)."
    ),
    tags=["volatility", "ratio"],
    calculation_function="volatility_ratio",
)


# ─── Risk-Adjusted (4) ────────────────────────────────────────────────


_TRADE_EFFICIENCY = IndicatorMetadata(
    id="trade_efficiency",
    name="Trade Efficiency (Signed)",
    category="Statistical",
    description=(
        "Signed efficiency ratio: window's net close-to-close "
        "change / total path length. Range -1..+1. Direction "
        "preserved (Kaufman's Efficiency Ratio is unsigned)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Trade Efficiency window mein net move kitna direct hua "
        "vs choppy. +1 = clean uptrend, -1 = clean downtrend, "
        "near 0 = chop / wandering."
    ),
    tags=["statistical", "efficiency"],
    calculation_function="trade_efficiency",
)


_ULCER_INDEX = IndicatorMetadata(
    id="ulcer_index",
    name="Ulcer Index",
    category="Risk",
    description=(
        "Pessimistic drawdown measure (Peter Martin, 1987). "
        "Penalises both depth + duration of drawdowns inside the "
        "window. Higher UI = more painful drawdowns."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Ulcer Index drawdown ka pain quantify karta hai — depth "
        "+ duration dono. High UI = strategy painful tha. Sharpe "
        "se zyada honest pain measure."
    ),
    tags=["risk", "drawdown"],
    calculation_function="ulcer_index",
)


_MARTIN_RATIO = IndicatorMetadata(
    id="martin_ratio",
    name="Martin Ratio",
    category="Risk",
    description=(
        "Period return / Ulcer Index (Peter Martin, 1987). "
        "Risk-adjusted return using drawdown pain (Ulcer) "
        "instead of stddev (Sharpe) or downside stddev (Sortino)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Martin Ratio Sharpe ki tarah risk-adjusted return — "
        "lekin denominator stddev ki jagah Ulcer Index hota hai. "
        "Trader ke pain ke close measure."
    ),
    tags=["risk", "ratio"],
    calculation_function="martin_ratio",
)


_BURKE_RATIO = IndicatorMetadata(
    id="burke_ratio",
    name="Burke Ratio",
    category="Risk",
    description=(
        "Period return / sqrt(sum of squared drawdowns). "
        "Sortino-family — penalises drawdowns quadratically so "
        "big ones dominate the score."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Burke Ratio drawdowns ko quadratically penalise karta "
        "hai — big drawdown disproportionately hurt score. "
        "Tail-risk-sensitive strategies ke liye."
    ),
    tags=["risk", "ratio"],
    calculation_function="burke_ratio",
)


# ─── Volatility Bands (4) ─────────────────────────────────────────────


_CHANDELIER_EXIT_LONG = IndicatorMetadata(
    id="chandelier_exit_long",
    name="Chandelier Exit — Long",
    category="Volatility",
    description=(
        "Long-side trailing stop ``max(high, period) - atr_mult "
        "* ATR``. Trails from the recent peak high (Charles Le "
        "Beau)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=22, min=2, max=200),
        InputSpec(
            name="atr_mult", type=InputType.NUMBER, default=3.0, min=0.1, max=10.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Chandelier Exit Long = recent peak se ATR-multiple "
        "neeche trailing stop. Profit-locking ke liye classic "
        "long-side exit."
    ),
    tags=["stop", "atr"],
    calculation_function="chandelier_exit_long",
)


_CHANDELIER_EXIT_SHORT = IndicatorMetadata(
    id="chandelier_exit_short",
    name="Chandelier Exit — Short",
    category="Volatility",
    description=(
        "Short-side trailing stop ``min(low, period) + atr_mult "
        "* ATR``. Mirror of the long-side Chandelier."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=22, min=2, max=200),
        InputSpec(
            name="atr_mult", type=InputType.NUMBER, default=3.0, min=0.1, max=10.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Chandelier Exit Short = recent low se ATR-multiple upar "
        "trailing stop. Short positions ke liye classic exit."
    ),
    tags=["stop", "atr"],
    calculation_function="chandelier_exit_short",
)


_SUPERTREND_V2 = IndicatorMetadata(
    id="supertrend_v2",
    name="Supertrend V2 (Adaptive)",
    category="Trend",
    description=(
        "Modified Supertrend with adaptive multiplier scaled "
        "0.7x-1.3x of base by current volatility regime. "
        "Reduces whipsaw in low-vol chop, still captures high-"
        "vol trends. Distinct from the existing fixed-mult "
        "``supertrend``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=2, max=200),
        InputSpec(
            name="atr_mult", type=InputType.NUMBER, default=3.0, min=0.1, max=10.0,
        ),
        InputSpec(
            name="volatility_lookback", type=InputType.NUMBER,
            default=100, min=4, max=1000,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Supertrend V2 = original Supertrend + adaptive multiplier. "
        "Calm market mein bands tight (less whipsaw), extreme vol "
        "mein bands wide (room to breathe)."
    ),
    tags=["trend", "stop", "adaptive"],
    calculation_function="supertrend_v2",
)


_ATR_TRAILING_STOP = IndicatorMetadata(
    id="atr_trailing_stop",
    name="ATR Trailing Stop",
    category="Volatility",
    description=(
        "Generic long-side trailing stop ``close - mult * ATR`` "
        "ratcheted up only. Distinct from Chandelier (peak-"
        "referenced) and Supertrend (direction-switching)."
    ),
    inputs=[
        InputSpec(
            name="atr_period", type=InputType.NUMBER, default=14, min=2, max=200,
        ),
        InputSpec(
            name="atr_mult", type=InputType.NUMBER, default=2.0, min=0.1, max=10.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ATR Trailing Stop = current close se ATR-multiple "
        "neeche, bas upar move karta hai (ratchet). Simple long-"
        "side trailing exit."
    ),
    tags=["stop", "atr"],
    calculation_function="atr_trailing_stop",
)


# ─── Aggregate ─────────────────────────────────────────────────────────


PACK12_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _ATR_PERCENT,
    _VOLATILITY_REGIME,
    _PARKINSON_VOLATILITY,
    _VOLATILITY_RATIO,
    _TRADE_EFFICIENCY,
    _ULCER_INDEX,
    _MARTIN_RATIO,
    _BURKE_RATIO,
    _CHANDELIER_EXIT_LONG,
    _CHANDELIER_EXIT_SHORT,
    _SUPERTREND_V2,
    _ATR_TRAILING_STOP,
)


__all__ = ["PACK12_ACTIVE_INDICATORS"]
