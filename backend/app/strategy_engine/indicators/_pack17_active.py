"""Pack 17 - 12 composite signal + ML-style feature indicators.

All 12 indicators are CUSTOM COMPOSITES that synthesise Pack 2-16
primitives. None have a Pine v5 ``ta.*`` equivalent. Lock test
``test_pack17_has_no_pine_aliases`` pins the contract.

Composition philosophy (carried over from Pack 13's
``divergence_strength_score``): a composite is justified when (a) the
component sum / weighting is itself a tradeable signal-tag (regime-
detection use), and (b) the composite is *distinct* from any existing
active. Two near-duplicates within Pack 17 (breakout_probability_score
vs consolidation_breakout_score) deliberately differ on the volume
component (rising-volume buildup vs low-volume duration); both ship.

Score range conventions (documented per indicator):

    0..100 scores  - trend_quality_score, momentum_quality_score,
                     mean_reversion_score, breakout_probability_score,
                     trend_continuation_score, reversal_likelihood_score,
                     consolidation_breakout_score, exhaustion_score
    Unbounded      - price_velocity, price_acceleration,
                     volume_momentum_ratio
    Centered ratio - range_expansion_score (>0 expanding,
                     <0 contracting, =0 neutral)

NO new Pine importer wiring. Difficulty split: 4 INTERMEDIATE for
the ML primitives (price_velocity / price_acceleration /
volume_momentum_ratio / range_expansion_score), 8 EXPERT for the
composite scores (multi-component synthesis demands operator
understanding of each component).
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

# --- Composite Signals (4) -----------------------------------------


_TREND_QUALITY_SCORE = IndicatorMetadata(
    id="trend_quality_score",
    name="Trend Quality Score",
    category="Composite",
    description=(
        "0..100 composite: ADX strength + price-distance-from-SMA "
        "+ trend-direction consistency over `period` bars. >60 = "
        "trending regime; <30 = ranging."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Trend Quality Score = ADX + price-distance-from-MA + "
        "consistency. >60 strong trend, <30 range. Composite "
        "regime tag, forecast nahi."
    ),
    tags=["composite", "trend"],
    calculation_function="trend_quality_score",
)


_MOMENTUM_QUALITY_SCORE = IndicatorMetadata(
    id="momentum_quality_score",
    name="Momentum Quality Score",
    category="Composite",
    description=(
        "0..100 composite: RSI extremity + MACD-histogram strength "
        "+ ROC sign-consistency. Regime tag for momentum strategies."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Momentum Quality Score = RSI distance-from-50 + MACD hist "
        "+ ROC sign consistency. >70 high-quality momentum."
    ),
    tags=["composite", "momentum"],
    calculation_function="momentum_quality_score",
)


_MEAN_REVERSION_SCORE = IndicatorMetadata(
    id="mean_reversion_score",
    name="Mean Reversion Score",
    category="Composite",
    description=(
        "0..100 composite: Bollinger %B extremity + RSI extremity + "
        "z-score from SMA. Higher = price stretched, mean-reversion "
        "entry more likely to work."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Mean Reversion Score = BB%B + RSI extremity + z-score. "
        ">70 stretched, mean reversion candidate."
    ),
    tags=["composite", "mean-reversion"],
    calculation_function="mean_reversion_score",
)


_BREAKOUT_PROBABILITY_SCORE = IndicatorMetadata(
    id="breakout_probability_score",
    name="Breakout Probability Score",
    category="Composite",
    description=(
        "0..100 composite: bandwidth-compressed vs avg + range-"
        "compressed + volume-rising. Distinct from "
        "consolidation_breakout_score (which weights duration "
        "instead of volume buildup)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=5, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Breakout Probability Score = squeeze + range-tight + "
        "volume rising. >70 watch for breakout."
    ),
    tags=["composite", "breakout"],
    calculation_function="breakout_probability_score",
)


# --- ML-Style Features (4) -----------------------------------------


_PRICE_VELOCITY = IndicatorMetadata(
    id="price_velocity",
    name="Price Velocity",
    category="ML Features",
    description=(
        "First derivative of close: (close - close[period]) / period. "
        "Sign = direction; magnitude = avg per-bar move. Unbounded."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Price Velocity = price ka first derivative. Per-bar move "
        "kitna ho raha hai. ML feature."
    ),
    tags=["ml", "derivative"],
    calculation_function="price_velocity",
)


_PRICE_ACCELERATION = IndicatorMetadata(
    id="price_acceleration",
    name="Price Acceleration",
    category="ML Features",
    description=(
        "Second derivative of close: change in velocity over `period`. "
        "Positive = accelerating; negative = decelerating / reversing."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Price Acceleration = velocity ka derivative. Positive = "
        "speed badh raha hai (strong move), negative = "
        "decelerate (reversal aane wala)."
    ),
    tags=["ml", "derivative"],
    calculation_function="price_acceleration",
)


_VOLUME_MOMENTUM_RATIO = IndicatorMetadata(
    id="volume_momentum_ratio",
    name="Volume Momentum Ratio",
    category="ML Features",
    description=(
        "Volume velocity / |price velocity|. Sign = volume direction; "
        "magnitude = how fast volume is changing relative to price. "
        "Returns None when price velocity is essentially zero."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Volume Momentum Ratio = volume kitna fast badh raha hai "
        "price ke comparison mein. High value = volume surge with "
        "small price move (potential breakout setup)."
    ),
    tags=["ml", "volume"],
    calculation_function="volume_momentum_ratio",
)


_RANGE_EXPANSION_SCORE = IndicatorMetadata(
    id="range_expansion_score",
    name="Range Expansion Score",
    category="ML Features",
    description=(
        "(short-window range / long-window range) - 1. >0 expanding, "
        "<0 contracting, =0 neutral. Centered ratio for breakout / "
        "consolidation context."
    ),
    inputs=[
        InputSpec(name="short", type=InputType.NUMBER, default=5, min=1, max=200),
        InputSpec(name="long", type=InputType.NUMBER, default=20, min=2, max=400),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Range Expansion Score = recent range vs longer-term range. "
        ">0 expanding (volatility rising), <0 contracting "
        "(consolidation)."
    ),
    tags=["ml", "volatility"],
    calculation_function="range_expansion_score",
)


# --- Pattern-Recognition Composites (4) ---------------------------


_TREND_CONTINUATION_SCORE = IndicatorMetadata(
    id="trend_continuation_score",
    name="Trend Continuation Score",
    category="Composite",
    description=(
        "0..100 composite: ADX + close-vs-SMA consistency + MACD "
        "histogram aligned with trend. Different from "
        "trend_quality_score (which weights distance-from-MA "
        "as a strength signal); continuation focuses on momentum-"
        "alignment forecast."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Trend Continuation Score = ADX + consistency + MACD "
        "alignment. >70 = strong continuation candidate."
    ),
    tags=["composite", "trend", "continuation"],
    calculation_function="trend_continuation_score",
)


_REVERSAL_LIKELIHOOD_SCORE = IndicatorMetadata(
    id="reversal_likelihood_score",
    name="Reversal Likelihood Score",
    category="Composite",
    description=(
        "0..100 composite: RSI deeply-extreme + RSI divergence "
        "present + bar range as multiple of ATR. Different from "
        "Pack 13's divergence_strength_score (sum of three "
        "divergence types) - this adds RSI extremity + range "
        "shock to one divergence detector."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Reversal Likelihood Score = RSI extreme + divergence "
        "+ range shock. >70 = reversal worth trading."
    ),
    tags=["composite", "reversal"],
    calculation_function="reversal_likelihood_score",
)


_CONSOLIDATION_BREAKOUT_SCORE = IndicatorMetadata(
    id="consolidation_breakout_score",
    name="Consolidation Breakout Score",
    category="Composite",
    description=(
        "0..100 composite: bandwidth squeeze + range-tightness + "
        "consolidation duration (consecutive bars below avg "
        "bandwidth). Distinct from breakout_probability_score "
        "(which weights volume buildup) - this weights duration."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=5, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Consolidation Breakout Score = squeeze + range-tight + "
        "duration. Lambi consolidation = bigger expected move."
    ),
    tags=["composite", "breakout", "consolidation"],
    calculation_function="consolidation_breakout_score",
)


_EXHAUSTION_SCORE = IndicatorMetadata(
    id="exhaustion_score",
    name="Exhaustion Score",
    category="Composite",
    description=(
        "0..100 composite: RSI deeply-extreme + bar-blowoff "
        "(range vs avg) + price stretched from SMA in ATR units. "
        "Trend-has-gone-too-far-too-fast detector."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Exhaustion Score = RSI deeply extreme + bar blowoff + "
        "stretch from MA. >70 = trend exhausted, fade candidate."
    ),
    tags=["composite", "exhaustion"],
    calculation_function="exhaustion_score",
)


# --- Aggregate -----------------------------------------------------


PACK17_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _TREND_QUALITY_SCORE,
    _MOMENTUM_QUALITY_SCORE,
    _MEAN_REVERSION_SCORE,
    _BREAKOUT_PROBABILITY_SCORE,
    _PRICE_VELOCITY,
    _PRICE_ACCELERATION,
    _VOLUME_MOMENTUM_RATIO,
    _RANGE_EXPANSION_SCORE,
    _TREND_CONTINUATION_SCORE,
    _REVERSAL_LIKELIHOOD_SCORE,
    _CONSOLIDATION_BREAKOUT_SCORE,
    _EXHAUSTION_SCORE,
)


__all__ = ["PACK17_ACTIVE_INDICATORS"]
