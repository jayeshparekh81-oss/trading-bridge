"""Pack 6 — 12 volume-flow + advanced-volatility indicators.

All 12 ids are net-new (no coming-soon stubs to override).

Two collisions vs Pack-2-through-5 active set were detected during
discovery and substituted out:

    * ``force_index``        — already active (added Phase 9)
    * ``ultimate_oscillator`` — already active (added Phase 9)

Substitutes shipped in their place: ``twiggs_money_flow`` (a
gap-aware Wilder-smoothed money-flow variant retail traders ask
for on opening-gap days) and ``mass_index`` (Donald Dorsey's
range-envelope reversal detector).

Difficulty split:

    INTERMEDIATE (7) — accumulation_distribution, chaikin_oscillator,
                       price_volume_trend, ease_of_movement,
                       awesome_oscillator, bollinger_bandwidth,
                       bollinger_percent_b
    EXPERT (5)       — twiggs_money_flow, mass_index,
                       elder_ray_bull, elder_ray_bear,
                       choppiness_index

The IndicatorDifficulty enum has BEGINNER / INTERMEDIATE / EXPERT
only — the user spec's "ADVANCED" tier maps to EXPERT here (no
schema change requested in the spec).

Pine importer wires the two real ``ta.*`` equivalents:
``ta.accdist`` → ``accumulation_distribution`` and ``ta.ao`` →
``awesome_oscillator``. The other ten indicators are builder-UI
only — no Pine equivalent to import. (``ta.uo`` exists but
``ultimate_oscillator`` is already active and out of Pack 6 scope.)
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

# ─── Volume Flow (5) ───────────────────────────────────────────────────


_ACCUMULATION_DISTRIBUTION = IndicatorMetadata(
    id="accumulation_distribution",
    name="Accumulation/Distribution Line",
    category="Volume",
    description=(
        "Cumulative running total of money-flow volume — bars with "
        "the close near the high add to the line, bars with the "
        "close near the low subtract from it. Pine: ``ta.accdist``."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.accdist"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "A/D Line dikhata hai paisa kis taraf ja raha hai — chart "
        "trend match kare to confirm, divergence ho to fade ki "
        "warning."
    ),
    tags=["volume", "flow"],
    calculation_function="accumulation_distribution",
)


_CHAIKIN_OSCILLATOR = IndicatorMetadata(
    id="chaikin_oscillator",
    name="Chaikin Oscillator",
    category="Volume",
    description=(
        "Difference between fast + slow EMAs of the A/D line "
        "(default 3 / 10). Zero crossings = momentum shifts in the "
        "underlying flow."
    ),
    inputs=[
        InputSpec(name="fast", type=InputType.NUMBER, default=3, min=2, max=50),
        InputSpec(name="slow", type=InputType.NUMBER, default=10, min=3, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Chaikin Oscillator zero ke upar = accumulation tez, neeche "
        "= distribution tez. Crossover signal entries ke liye use "
        "kar sakte ho."
    ),
    tags=["volume", "oscillator"],
    calculation_function="chaikin_oscillator",
)


_PRICE_VOLUME_TREND = IndicatorMetadata(
    id="price_volume_trend",
    name="Price Volume Trend (PVT)",
    category="Volume",
    description=(
        "Cumulative volume weighted by percentage price change. "
        "Divergence between PVT slope and price slope warns of a "
        "fading move."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "PVT volume + price ka cumulative measure hai. Trending "
        "market mein price ke saath PVT bhi badhna chahiye — agar "
        "nahi badh raha, divergence dekho."
    ),
    tags=["volume", "trend"],
    calculation_function="price_volume_trend",
)


_EASE_OF_MOVEMENT = IndicatorMetadata(
    id="ease_of_movement",
    name="Ease of Movement (EMV)",
    category="Volume",
    description=(
        "Distance the bar's midpoint moved per unit of volume. "
        "High EMV = price moves easily on light volume; low EMV = "
        "heavy volume but little movement."
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
        "Ease of Movement positive + rising = uptrend ko light "
        "volume support kar raha hai (healthy). Negative spikes = "
        "selling pressure dominant."
    ),
    tags=["volume", "movement"],
    calculation_function="ease_of_movement",
)


_TWIGGS_MONEY_FLOW = IndicatorMetadata(
    id="twiggs_money_flow",
    name="Twiggs Money Flow",
    category="Volume",
    description=(
        "Wilder-smoothed money-flow variant that uses true high/low "
        "(close-gap aware). More robust than Chaikin Money Flow on "
        "opening-gap days — useful for Indian retail symbols."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=21, min=5, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Twiggs Money Flow gap-friendly version of Chaikin — "
        "nightly gaps wale stocks pe better signal deta hai. Zero "
        "ke upar = accumulation, neeche = distribution."
    ),
    tags=["volume", "flow", "advanced"],
    calculation_function="twiggs_money_flow",
)


# ─── Momentum / Oscillators (3 — uo collision substituted) ────────────


_MASS_INDEX = IndicatorMetadata(
    id="mass_index",
    name="Mass Index",
    category="Volatility",
    description=(
        "Detects trend reversals by spotting bulges in the bar-"
        "range envelope (Donald Dorsey, 1992). Classic rule: MI "
        "rises above 27 then dips below 26.5 → reversal warning."
    ),
    inputs=[
        InputSpec(
            name="ema_period", type=InputType.NUMBER, default=9, min=2, max=50,
        ),
        InputSpec(
            name="sum_period", type=InputType.NUMBER, default=25, min=5, max=200,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Mass Index range expansion ka detector. 27+ ke baad jab "
        "26.5 se neeche aaye, reversal ka signal — direction price "
        "action se confirm karna padta hai."
    ),
    tags=["volatility", "reversal"],
    calculation_function="mass_index",
)


_AWESOME_OSCILLATOR = IndicatorMetadata(
    id="awesome_oscillator",
    name="Awesome Oscillator (AO)",
    category="Momentum",
    description=(
        "Bill Williams' median-price oscillator: SMA(median, 5) - "
        "SMA(median, 34). Pine equivalent ``ta.ao``."
    ),
    inputs=[
        InputSpec(name="fast", type=InputType.NUMBER, default=5, min=2, max=50),
        InputSpec(name="slow", type=InputType.NUMBER, default=34, min=3, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.ao"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Awesome Oscillator zero crossing = trend change. "
        "Histogram colour-coded UI mein dikhata hai but raw line "
        "trade decisions ke liye sufficient hai."
    ),
    tags=["momentum", "oscillator"],
    calculation_function="awesome_oscillator",
)


_ELDER_RAY_BULL = IndicatorMetadata(
    id="elder_ray_bull",
    name="Elder Ray — Bull Power",
    category="Momentum",
    description=(
        "Distance from the bar's high to a smoothed close EMA "
        "(Alexander Elder, 1989). Positive = buying pressure; "
        "magnitude = strength."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=13, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Bull Power = high - EMA(close). Sustained positive = "
        "bulls control. Bear Power ke saath pair karke trend "
        "strength judge karte hain."
    ),
    tags=["momentum", "elder"],
    calculation_function="elder_ray_bull",
)


_ELDER_RAY_BEAR = IndicatorMetadata(
    id="elder_ray_bear",
    name="Elder Ray — Bear Power",
    category="Momentum",
    description=(
        "Distance from the bar's low to a smoothed close EMA "
        "(Alexander Elder, 1989). Negative = selling pressure; "
        "magnitude = depth of penetration."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=13, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Bear Power = low - EMA(close). Persistent negative = "
        "bears dominant. Bull + Bear divergence = high-conviction "
        "reversal candidate."
    ),
    tags=["momentum", "elder"],
    calculation_function="elder_ray_bear",
)


# ─── Volatility / Trend Strength (3) ──────────────────────────────────


_CHOPPINESS_INDEX = IndicatorMetadata(
    id="choppiness_index",
    name="Choppiness Index",
    category="Volatility",
    description=(
        "Range-bound vs trending classifier (E. W. Dreiss). "
        "Output 0-100. >61.8 → choppy / mean-reverting; <38.8 → "
        "trending. Fibonacci thresholds are operator preference."
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
        "Choppiness Index batata hai market trend mein hai ya "
        "range mein. >61.8 → range-bound (reversion strategies), "
        "<38.8 → trending (momentum strategies)."
    ),
    tags=["volatility", "regime"],
    calculation_function="choppiness_index",
)


_BOLLINGER_BANDWIDTH = IndicatorMetadata(
    id="bollinger_bandwidth",
    name="Bollinger Bandwidth",
    category="Volatility",
    description=(
        "Band width as a percentage of the mid-band. Contracted "
        "bandwidth (a 'squeeze') often precedes a directional "
        "breakout."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="std_dev", type=InputType.NUMBER, default=2.0, min=0.5, max=5.0),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Bollinger Bandwidth volatility regime ka measure. Squeeze "
        "(historical low) ke baad expansion → breakout chance high."
    ),
    tags=["volatility", "bollinger"],
    calculation_function="bollinger_bandwidth",
)


_BOLLINGER_PERCENT_B = IndicatorMetadata(
    id="bollinger_percent_b",
    name="Bollinger %B",
    category="Volatility",
    description=(
        "Where the source price sits within the Bollinger band. "
        "0 = at lower band, 0.5 = at middle, 1.0 = at upper band. "
        "Negative / >1 means price has pierced the band."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="std_dev", type=InputType.NUMBER, default=2.0, min=0.5, max=5.0),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "%B price ka band ke andar position. >1 → upper band "
        "breach (overbought), <0 → lower band breach (oversold). "
        "Mean-reversion strategies ke entries ke liye useful."
    ),
    tags=["volatility", "bollinger", "mean-reversion"],
    calculation_function="bollinger_percent_b",
)


# ─── Aggregate ─────────────────────────────────────────────────────────


PACK6_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _ACCUMULATION_DISTRIBUTION,
    _CHAIKIN_OSCILLATOR,
    _PRICE_VOLUME_TREND,
    _EASE_OF_MOVEMENT,
    _TWIGGS_MONEY_FLOW,
    _MASS_INDEX,
    _AWESOME_OSCILLATOR,
    _ELDER_RAY_BULL,
    _ELDER_RAY_BEAR,
    _CHOPPINESS_INDEX,
    _BOLLINGER_BANDWIDTH,
    _BOLLINGER_PERCENT_B,
)


__all__ = ["PACK6_ACTIVE_INDICATORS"]
