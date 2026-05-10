"""Phase 9 — 10 new ACTIVE indicator metadata rows.

Kept in a sibling module so the registry's diff stays a single import +
a tuple spread. ADX and DMI share the same calculation function (one
file, ``calculations/adx.py``) but expose two separate registry ids
because the trading interpretation differs: ADX measures *trend
strength*, DMI exposes the directional pair (+DI, -DI).

Backtest dispatch wiring lives in ``backtest/indicator_runner.py``,
which currently dispatches only the Phase 1 indicators. These ten
entries are registry-correct and have standalone-tested calculations;
threading them through the simulator is a follow-up step.
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

_ADX = IndicatorMetadata(
    id="adx",
    name="ADX",
    category="Trend",
    description=(
        "Average Directional Index (Wilder) — measures trend strength on "
        "a 0-100 scale, agnostic to direction. Built on top of +DI / -DI."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.adx"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ADX above 25 typically indicates a trending market; below 20 "
        "suggests the market is range-bound. Pair with +DI / -DI to "
        "decide direction."
    ),
    tags=["trend", "strength", "wilder"],
    calculation_function="adx",
)

_DMI = IndicatorMetadata(
    id="dmi",
    name="DMI",
    category="Trend",
    description=(
        "Directional Movement Index (Wilder) — exposes the +DI / -DI "
        "pair from the ADX pipeline. +DI > -DI signals an up-move "
        "regime; -DI > +DI signals a down-move regime."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["plus_di", "minus_di"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.dmi"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Look for +DI crossing above -DI as a long signal in a trending "
        "regime (confirm with ADX > 25). Reversal of that crossover is "
        "a common trail-out cue."
    ),
    tags=["trend", "direction", "wilder"],
    calculation_function="adx",
)

_AROON = IndicatorMetadata(
    id="aroon",
    name="Aroon",
    category="Trend",
    description=(
        "Aroon Up / Aroon Down / Aroon Oscillator — measures how recently "
        "the highest high (Up) or lowest low (Down) occurred within the "
        "trailing window. Pegs at 100 / 0 in clean trends."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=25, min=2, max=200),
    ],
    outputs=["aroon_up", "aroon_down", "oscillator"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.aroon"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Aroon Up > 70 with Aroon Down < 30 indicates a strong uptrend. "
        "Crossovers of Up and Down often mark trend changes."
    ),
    tags=["trend", "chande"],
    calculation_function="aroon",
)

_TRIX = IndicatorMetadata(
    id="trix",
    name="TRIX",
    category="Momentum",
    description=(
        "Triple-smoothed EMA momentum, expressed as a percent rate of "
        "change. The triple smoothing strips noise so zero-crossings "
        "of the line cleanly mark trend reversals."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=15, min=2, max=200),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.trix"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "TRIX above zero indicates an uptrend; below zero a downtrend. "
        "Cross of the zero line is the classic entry / exit cue."
    ),
    tags=["momentum", "smoothed", "hutson"],
    calculation_function="trix",
)

_ULTIMATE_OSCILLATOR = IndicatorMetadata(
    id="ultimate_oscillator",
    name="Ultimate Oscillator",
    category="Momentum",
    description=(
        "Williams' Ultimate Oscillator — weighted momentum across three "
        "windows (default 7 / 14 / 28). Output range is 0-100; reduces "
        "false divergences any single window would produce on its own."
    ),
    inputs=[
        InputSpec(name="short_period", type=InputType.NUMBER, default=7, min=2, max=200),
        InputSpec(name="medium_period", type=InputType.NUMBER, default=14, min=2, max=200),
        InputSpec(name="long_period", type=InputType.NUMBER, default=28, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Readings above 70 are overbought; below 30 oversold. Bullish "
        "divergence (price lower-low while UO higher-low) is the "
        "classic Williams entry."
    ),
    tags=["momentum", "oscillator", "williams"],
    calculation_function="ultimate_oscillator",
)

_CMF = IndicatorMetadata(
    id="cmf",
    name="Chaikin Money Flow",
    category="Volume",
    description=(
        "Chaikin Money Flow — volume-weighted close position within the "
        "bar's range, summed over `period` bars. Output range is "
        "approximately -1 (heavy distribution) to +1 (heavy accumulation)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.cmf"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Persistent CMF > 0 indicates buying pressure under price; "
        "persistent CMF < 0 indicates selling pressure even on rallies."
    ),
    tags=["volume", "chaikin"],
    calculation_function="cmf",
)

_FORCE_INDEX = IndicatorMetadata(
    id="force_index",
    name="Force Index",
    category="Volume",
    description=(
        "Elder's Force Index — price change times volume, smoothed by an "
        "EMA of `period` bars. Combines direction and conviction in one "
        "line; sign tracks the dominant short-term flow."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=13, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Force Index above zero with volume expanding is a bullish "
        "confirmation. Persistent negative readings warn that rallies "
        "lack participation."
    ),
    tags=["volume", "elder", "momentum"],
    calculation_function="force_index",
)

_LINEAR_REGRESSION = IndicatorMetadata(
    id="linear_regression",
    name="Linear Regression",
    category="Trend",
    description=(
        "Least-Squares Moving Average (LSMA) — value of the linear "
        "regression line at the most recent bar of the trailing window. "
        "Reacts faster to trend changes than SMA / EMA of the same period."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.linreg"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Use as a lower-lag trend baseline. Price crosses of the "
        "regression line are earlier than SMA / EMA crosses but more "
        "prone to whipsaws in choppy markets."
    ),
    tags=["trend", "regression", "lsma"],
    calculation_function="linear_regression",
)

_PIVOT_POINTS = IndicatorMetadata(
    id="pivot_points",
    name="Pivot Points",
    category="Support/Resistance",
    description=(
        "Classic pivot points (PP, R1, R2, S1, S2) computed from the "
        "previous bar's H/L/C. True session-anchored pivots ship in "
        "Phase 11 with the simulator's session awareness."
    ),
    inputs=[],
    outputs=["pp", "r1", "r2", "s1", "s2"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Pivot levels act as intraday support / resistance. R1 / S1 are "
        "high-probability mean-reversion targets; R2 / S2 mark "
        "follow-through breakouts."
    ),
    tags=["support-resistance", "pivot", "intraday"],
    calculation_function="pivot_points",
)

_ICHIMOKU = IndicatorMetadata(
    id="ichimoku",
    name="Ichimoku (Tenkan + Kijun)",
    category="Trend",
    description=(
        "Basic Ichimoku — Tenkan-sen (9-bar median of extremes) and "
        "Kijun-sen (26-bar median). The full cloud (Senkou A/B + Chikou) "
        "lands in Phase 11 alongside the simulator's session shift."
    ),
    inputs=[
        InputSpec(
            name="tenkan_period", type=InputType.NUMBER, default=9, min=2, max=200
        ),
        InputSpec(
            name="kijun_period", type=InputType.NUMBER, default=26, min=2, max=500
        ),
    ],
    outputs=["tenkan", "kijun"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Tenkan crossing above Kijun is a bullish trigger; below is "
        "bearish. Kijun also acts as a dynamic support / resistance "
        "level once price is on one side of it."
    ),
    tags=["trend", "ichimoku"],
    calculation_function="ichimoku",
)


PHASE9_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _ADX,
    _DMI,
    _AROON,
    _TRIX,
    _ULTIMATE_OSCILLATOR,
    _CMF,
    _FORCE_INDEX,
    _LINEAR_REGRESSION,
    _PIVOT_POINTS,
    _ICHIMOKU,
)


__all__ = ["PHASE9_ACTIVE_INDICATORS"]
