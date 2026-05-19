"""Library-alias pack — surface existing backend indicators under the
canonical slugs used by ``frontend/src/lib/indicators/content/``.

Six retail-canonical names (CMO, KVO, PPO, HMA, Momentum, Comparative
RS) already have backend implementations under technical / library
names. This pack adds registry entries that resolve the canonical
slugs to the existing ``calculation_function`` so that the strategy
builder can find them without a frontend slug rewrite.

These entries are strictly ADDITIVE — they coexist with the existing
technical-named entries in their respective packs. No existing entry
is modified.

Coverage (matching ``frontend/src/lib/indicators/content/<slug>.ts``):

    chande_momentum_oscillator   → calc ``chande_momentum``
    comparative_relative_strength → calc ``relative_strength_vs_benchmark``
    hma                          → calc ``hull_ma``
    klinger_oscillator           → calc ``klinger_volume_oscillator``
    momentum                     → calc ``momentum_oscillator``
    price_oscillator             → calc ``percent_price_oscillator``

The 4 remaining library-only slugs that require composition or
output-extraction (``dmi_plus``, ``dmi_minus``, ``elder_ray_bull_bear``,
``linear_regression_channel``) live in wrapper calc files +
companion registry entries in the indicator-completion wave-1 pack
because they need actual code, not just a registry mapping.
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


_CHANDE_MOMENTUM_OSCILLATOR_ALIAS = IndicatorMetadata(
    id="chande_momentum_oscillator",
    name="Chande Momentum Oscillator",
    category="Momentum",
    description=(
        "Chande Momentum Oscillator (Chande, 1995) — like RSI but uses "
        "raw sums of up vs down moves; reacts faster. Canonical retail "
        "name; same compute as the technical-named ``chande_momentum`` "
        "indicator."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=9, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.cmo"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "CMO -100 se +100 range mein oscillate karta. Zero ke through "
        "cross momentum shift mark karte; ±50 readings strong move flag "
        "karte. RSI se faster react karta but noisier."
    ),
    tags=["momentum", "oscillator", "library-canonical"],
    calculation_function="chande_momentum",
)


_COMPARATIVE_RELATIVE_STRENGTH_ALIAS = IndicatorMetadata(
    id="comparative_relative_strength",
    name="Comparative Relative Strength",
    category="Momentum",
    description=(
        "Comparative Relative Strength — ratio of one instrument's price "
        "to a benchmark's. Direction shows relative outperformance; "
        "absolute level is a normalised ratio. Used for sector rotation "
        "and pair-trading. Canonical retail name; same compute as "
        "``relative_strength_vs_benchmark``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "CRS dikhata ek instrument apne benchmark se kaisa perform kar "
        "raha. Rising CRS = outperformance; falling = underperformance. "
        "Sector rotation + pair-trading ke liye useful."
    ),
    tags=["momentum", "relative-strength", "library-canonical"],
    calculation_function="relative_strength_vs_benchmark",
)


_HMA_ALIAS = IndicatorMetadata(
    id="hma",
    name="HMA (Hull Moving Average)",
    category="Trend",
    description=(
        "Hull Moving Average (Alan Hull) — weighted-MA construction that "
        "is both smoother and faster than EMA at the same period. "
        "Canonical retail name; same compute as ``hull_ma``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.hma"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "HMA EMA se smoother aur faster dono — trends ko closely track "
        "karta aur chop mein whipsaws kam dikhata. Cost: math complex, "
        "compute slightly heavier."
    ),
    tags=["trend", "moving-average", "library-canonical"],
    calculation_function="hull_ma",
)


_KLINGER_OSCILLATOR_ALIAS = IndicatorMetadata(
    id="klinger_oscillator",
    name="Klinger Oscillator",
    category="Volume",
    description=(
        "Klinger Volume Oscillator (Stephen Klinger) — volume-weighted "
        "momentum oscillator combining trend direction with cumulative "
        "volume movement. Canonical retail name; same compute as "
        "``klinger_volume_oscillator``."
    ),
    inputs=[
        InputSpec(name="fast_period", type=InputType.NUMBER, default=34, min=2, max=500),
        InputSpec(name="slow_period", type=InputType.NUMBER, default=55, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "KVO long-term vs short-term money flow compare karta. Signal-line "
        "cross + divergence pe institutional accumulation/distribution "
        "phases flag karta — F&O cash equity pe sabse useful."
    ),
    tags=["volume", "oscillator", "library-canonical"],
    calculation_function="klinger_volume_oscillator",
)


_MOMENTUM_ALIAS = IndicatorMetadata(
    id="momentum",
    name="Momentum",
    category="Momentum",
    description=(
        "Momentum oscillator — ``close[i] - close[i - period]``. Direction "
        "of the line shows price-direction strength; sign shows trend "
        "bias. Canonical retail name; same compute as "
        "``momentum_oscillator``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.mom"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Sabse simple momentum read — current close minus N-bars-ago "
        "close. Positive = uptrend, negative = downtrend, zero-line "
        "cross = trend-bias shift. Interpretation needs context — "
        "intermediate."
    ),
    tags=["momentum", "library-canonical"],
    calculation_function="momentum_oscillator",
)


_PRICE_OSCILLATOR_ALIAS = IndicatorMetadata(
    id="price_oscillator",
    name="Price Oscillator (PPO)",
    category="Momentum",
    description=(
        "Percentage Price Oscillator — MACD's percentage cousin. "
        "``(EMA(fast) - EMA(slow)) / EMA(slow) × 100``. Scale-invariant "
        "across instruments at different price levels. Canonical retail "
        "name; same compute as ``percent_price_oscillator``."
    ),
    inputs=[
        InputSpec(name="fast", type=InputType.NUMBER, default=12, min=2, max=500),
        InputSpec(name="slow", type=InputType.NUMBER, default=26, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.ppo"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "PPO MACD ki tarah cross + divergence trade hota but percentage "
        "scale mein. Cross-stock momentum scans pe MACD se zyada "
        "comparable kyunki normalized hota."
    ),
    tags=["momentum", "oscillator", "library-canonical"],
    calculation_function="percent_price_oscillator",
)


PACK_LIBRARY_ALIASES_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _CHANDE_MOMENTUM_OSCILLATOR_ALIAS,
    _COMPARATIVE_RELATIVE_STRENGTH_ALIAS,
    _HMA_ALIAS,
    _KLINGER_OSCILLATOR_ALIAS,
    _MOMENTUM_ALIAS,
    _PRICE_OSCILLATOR_ALIAS,
)


__all__ = ["PACK_LIBRARY_ALIASES_ACTIVE_INDICATORS"]
