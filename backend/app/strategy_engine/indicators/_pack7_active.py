"""Pack 7 — 12 trend-strength + advanced-momentum indicators.

Discovery-time collisions vs Pack-2-through-6:

    * ``trix``  — already active (Phase 9 / Pack 2 era)
      → substituted with ``klinger_volume_oscillator`` (Stephen
        Klinger's volume-weighted momentum oscillator; rare in
        the existing pack mix)
    * ``aroon`` — already active. The three Pack-7 single-line
      projections (``aroon_up`` / ``aroon_down`` /
      ``aroon_oscillator``) are NEW ids; they project the
      existing :func:`aroon` calc into stand-alone series so
      strategies don't have to thread the multi-output dispatch
      (Phase-9 limitation) to reference one line.

Difficulty split (BEGINNER / INTERMEDIATE / EXPERT — schema has
no ADVANCED tier; spec's "ADVANCED" maps to EXPERT):

    INTERMEDIATE (8) — aroon_up, aroon_down, aroon_oscillator,
                       vortex_positive, vortex_negative,
                       detrended_price_oscillator,
                       coppock_curve, balance_of_power
    EXPERT (4)       — klinger_volume_oscillator, fisher_transform,
                       chande_kroll_stop, relative_vigor_index

Pine importer wires the one *new* real ``ta.*`` equivalent:

    * ``ta.vortex`` → ``vortex_positive`` (the negative line is a
      separate registry config; the Pine parser doesn't unpack
      tuples)

``ta.aroon`` and ``ta.trix`` are already wired to the pre-existing
``aroon`` / ``trix`` actives — out of Pack 7's scope to re-wire.
``ta.dpo``, ``ta.fisher`` etc. don't exist in stock Pine v5.
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

# ─── Trend Strength (5) ───────────────────────────────────────────────


_AROON_UP = IndicatorMetadata(
    id="aroon_up",
    name="Aroon Up",
    category="Trend",
    description=(
        "Single-line projection of the Aroon Up component "
        "(Tushar Chande, 1995). 0-100 — values near 100 mean "
        "the highest high inside the window happened recently."
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
        "Aroon Up batata hai recent high kab aaya. 70+ rising = "
        "strong uptrend; 30 ke neeche = trend kamzor."
    ),
    tags=["trend", "aroon"],
    calculation_function="aroon_up",
)


_AROON_DOWN = IndicatorMetadata(
    id="aroon_down",
    name="Aroon Down",
    category="Trend",
    description=(
        "Single-line projection of the Aroon Down component. "
        "Mirror of Aroon Up — high values mean the lowest low "
        "inside the window happened recently."
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
        "Aroon Down recent low ka recency batata hai. 70+ rising = "
        "strong downtrend; Aroon Up + Down crossing = trend change."
    ),
    tags=["trend", "aroon"],
    calculation_function="aroon_down",
)


_AROON_OSCILLATOR = IndicatorMetadata(
    id="aroon_oscillator",
    name="Aroon Oscillator",
    category="Trend",
    description=(
        "Aroon Up minus Aroon Down. Range -100 to +100. "
        "Sustained > 0 → uptrend; sustained < 0 → downtrend; "
        "oscillation around zero → range-bound."
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
        "Aroon Oscillator zero ke upar = uptrend dominant, neeche "
        "= downtrend. Range-bound markets mein zero ke aas-paas "
        "oscillate karta hai."
    ),
    tags=["trend", "aroon", "oscillator"],
    calculation_function="aroon_oscillator",
)


_VORTEX_POSITIVE = IndicatorMetadata(
    id="vortex_positive",
    name="Vortex VI+",
    category="Trend",
    description=(
        "Positive vortex line (Botes & Siepman, 2009). Rising VI+ "
        "with falling VI- = uptrend confirmation. Pine: ``ta.vortex``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.vortex"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "VI+ above VI- = bulls in control. Crossover (VI+ above "
        "VI-) classic long entry signal."
    ),
    tags=["trend", "vortex"],
    calculation_function="vortex_positive",
)


_VORTEX_NEGATIVE = IndicatorMetadata(
    id="vortex_negative",
    name="Vortex VI-",
    category="Trend",
    description=(
        "Negative vortex line. Pair with VI+ for crossover signals."
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
        "VI- above VI+ = bears in control. VI- crossing above "
        "VI+ = short / exit-long signal."
    ),
    tags=["trend", "vortex"],
    calculation_function="vortex_negative",
)


# ─── Advanced Momentum (4 — trix collision substituted) ──────────────


_KLINGER_VOLUME_OSCILLATOR = IndicatorMetadata(
    id="klinger_volume_oscillator",
    name="Klinger Volume Oscillator",
    category="Volume",
    description=(
        "Volume-weighted momentum oscillator (Stephen Klinger, "
        "1997). Difference of fast/slow EMAs of a volume-force "
        "series. Default fast/slow = 34 / 55."
    ),
    inputs=[
        InputSpec(name="fast", type=InputType.NUMBER, default=34, min=2, max=200),
        InputSpec(name="slow", type=InputType.NUMBER, default=55, min=3, max=400),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "KVO volume + price action ka combined momentum dikhata "
        "hai. Zero crossover = trend change. Divergence price "
        "se = upcoming reversal warning."
    ),
    tags=["volume", "momentum"],
    calculation_function="klinger_volume_oscillator",
)


_DETRENDED_PRICE_OSCILLATOR = IndicatorMetadata(
    id="detrended_price_oscillator",
    name="Detrended Price Oscillator (DPO)",
    category="Momentum",
    description=(
        "Removes the lagging trend component to expose price "
        "cycles. Not real-time — uses a forward shift; useful "
        "for spotting historical cycle highs / lows."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "DPO trend ko hata ke sirf cycle dikhata hai. Cycle "
        "highs / lows identify karne ke liye useful — note: real-"
        "time signals ke liye nahi (forward-shifted)."
    ),
    tags=["momentum", "cycle"],
    calculation_function="detrended_price_oscillator",
)


_COPPOCK_CURVE = IndicatorMetadata(
    id="coppock_curve",
    name="Coppock Curve",
    category="Momentum",
    description=(
        "Long-term momentum (Edwin Coppock, 1962). Designed for "
        "monthly-bar equity-index data — flags major regime "
        "changes when crossing zero."
    ),
    inputs=[
        InputSpec(
            name="short_period", type=InputType.NUMBER, default=11, min=2, max=200,
        ),
        InputSpec(
            name="long_period", type=InputType.NUMBER, default=14, min=3, max=400,
        ),
        InputSpec(
            name="wma_period", type=InputType.NUMBER, default=10, min=2, max=200,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Coppock Curve long-term regime indicator. Zero ke neeche "
        "se cross-up = bullish regime start (monthly charts pe "
        "best work karta hai)."
    ),
    tags=["momentum", "long-term"],
    calculation_function="coppock_curve",
)


_FISHER_TRANSFORM = IndicatorMetadata(
    id="fisher_transform",
    name="Fisher Transform",
    category="Momentum",
    description=(
        "Maps price into a near-Gaussian distribution (John "
        "Ehlers, 2002). Sharp turns line up with reversal points "
        "in the underlying."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=9, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Fisher Transform extreme moves ko statistical outlier "
        "banata hai — sharp turns turn-around signal dete hain. "
        "Crossover with prior bar = entry trigger."
    ),
    tags=["momentum", "ehlers", "advanced"],
    calculation_function="fisher_transform",
)


# ─── Oscillators (3) ─────────────────────────────────────────────────


_CHANDE_KROLL_STOP = IndicatorMetadata(
    id="chande_kroll_stop",
    name="Chande Kroll Stop",
    category="Volatility",
    description=(
        "Volatility-aware trailing-stop curve (long side). "
        "Tushar Chande & Stanley Kroll, 1995."
    ),
    inputs=[
        InputSpec(
            name="atr_period", type=InputType.NUMBER, default=10, min=2, max=200,
        ),
        InputSpec(
            name="atr_mult", type=InputType.NUMBER, default=1.0, min=0.1, max=10.0,
        ),
        InputSpec(
            name="period", type=InputType.NUMBER, default=9, min=2, max=200,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Chande Kroll Stop ATR-based trailing stop. Long position "
        "ke liye stop level deta hai — close iske niche jaaye to "
        "exit signal."
    ),
    tags=["volatility", "stop"],
    calculation_function="chande_kroll_stop",
)


_RELATIVE_VIGOR_INDEX = IndicatorMetadata(
    id="relative_vigor_index",
    name="Relative Vigor Index (RVI)",
    category="Momentum",
    description=(
        "John Ehlers' close-open vs high-low ratio. Range "
        "approximately ``[-1, +1]``."
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
        "RVI close-open ko high-low se compare karta hai — bars "
        "decisively close ho rahe hain ya weak. Positive + rising "
        "= bullish vigor."
    ),
    tags=["momentum", "ehlers"],
    calculation_function="relative_vigor_index",
)


_BALANCE_OF_POWER = IndicatorMetadata(
    id="balance_of_power",
    name="Balance of Power (BoP)",
    category="Momentum",
    description=(
        "Per-bar measure of session control (Igor Livshin). "
        "``(close - open) / (high - low)``. Range ``[-1, +1]``."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "BoP per-bar dikhata hai bulls ya bears ne session "
        "control kiya. Sustained positive = buyers dominate; "
        "negative = sellers."
    ),
    tags=["momentum", "session"],
    calculation_function="balance_of_power",
)


# ─── Aggregate ─────────────────────────────────────────────────────────


PACK7_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _AROON_UP,
    _AROON_DOWN,
    _AROON_OSCILLATOR,
    _VORTEX_POSITIVE,
    _VORTEX_NEGATIVE,
    _KLINGER_VOLUME_OSCILLATOR,
    _DETRENDED_PRICE_OSCILLATOR,
    _COPPOCK_CURVE,
    _FISHER_TRANSFORM,
    _CHANDE_KROLL_STOP,
    _RELATIVE_VIGOR_INDEX,
    _BALANCE_OF_POWER,
)


__all__ = ["PACK7_ACTIVE_INDICATORS"]
