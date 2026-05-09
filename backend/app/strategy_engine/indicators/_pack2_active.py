"""Pack 2 — 15 indicators promoted from ``coming_soon`` to ``active``.

Each row mirrors the same id that lives in
:mod:`_phase9_coming_soon`, but with ``status = ACTIVE`` and a real
``calculation_function`` pointing into
:mod:`app.strategy_engine.indicators.calculations`.

The registry's dict comprehension splats this tuple AFTER the
coming-soon stubs, so for any duplicate id the active row wins
(later inserts override earlier inserts in a Python dict comp).

Keep edits to this file purely additive — Phase 1-12 production
code outside the registry is not modified by Pack 2.
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

# ─── Trend (7) ─────────────────────────────────────────────────────────


_VWMA = IndicatorMetadata(
    id="vwma",
    name="VWMA",
    category="Trend",
    description=(
        "Volume Weighted Moving Average — average price weighted by "
        "the bar's volume. Reacts more strongly to high-volume bars "
        "than a plain SMA."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.vwma"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "VWMA tracks where the *traded* money concentrated, not just "
        "where price went. Useful for confirming trend strength when "
        "volume is meaningful."
    ),
    tags=["trend", "moving-average", "volume"],
    calculation_function="vwma",
)

_SUPERTREND = IndicatorMetadata(
    id="supertrend",
    name="Supertrend",
    category="Trend",
    description=(
        "Supertrend — ATR-driven band tracker. Outputs the active "
        "support/resistance line plus a ±1 direction flag."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=1, max=200),
        InputSpec(
            name="multiplier", type=InputType.NUMBER, default=3.0, min=0.1, max=20
        ),
    ],
    outputs=["line", "direction"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.supertrend"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Supertrend gives you a single trailing line with a clear "
        "flip signal — popular for Indian intraday systems because "
        "it cuts noise on choppy days."
    ),
    tags=["trend", "atr", "intraday"],
    calculation_function="supertrend",
)

_PARABOLIC_SAR = IndicatorMetadata(
    id="parabolic_sar",
    name="Parabolic SAR",
    category="Trend",
    description=(
        "Parabolic Stop-And-Reverse (Wilder, 1978) — accelerating "
        "trailing dot that flips when price crosses it."
    ),
    inputs=[
        InputSpec(
            name="step", type=InputType.NUMBER, default=0.02, min=0.001, max=1.0
        ),
        InputSpec(
            name="max_step", type=InputType.NUMBER, default=0.2, min=0.01, max=2.0
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.sar"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "PSAR is best in trending markets — chops up in sideways "
        "ranges. Common as a trailing-stop driver paired with a "
        "trend filter."
    ),
    tags=["trend", "stop-loss", "wilder"],
    calculation_function="parabolic_sar",
)

_SMMA = IndicatorMetadata(
    id="smma",
    name="SMMA",
    category="Trend",
    description=(
        "Smoothed Moving Average / Wilder's RMA — EMA-equivalent with "
        "alpha = 1/period. Used internally by RSI / ATR / ADX."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.rma"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "SMMA reacts slowly, which is why Wilder used it as a "
        "smoothing kernel. Good for noise-sensitive crossovers."
    ),
    tags=["trend", "moving-average", "wilder"],
    calculation_function="smma",
)

_DEMA = IndicatorMetadata(
    id="dema",
    name="DEMA",
    category="Trend",
    description=(
        "Double Exponential Moving Average (Mulloy, 1994) — reacts "
        "faster than EMA at the cost of a bit more noise."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.dema"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "DEMA tracks turns earlier than a single EMA. Good when you "
        "need a more responsive trend line for short timeframes."
    ),
    tags=["trend", "moving-average"],
    calculation_function="dema",
)

_TEMA = IndicatorMetadata(
    id="tema",
    name="TEMA",
    category="Trend",
    description=(
        "Triple Exponential Moving Average (Mulloy, 1994) — even "
        "faster than DEMA; built on three nested EMAs."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.tema"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "TEMA reacts fastest of the EMA family but introduces more "
        "whipsaw — pair with a slower filter on noisy timeframes."
    ),
    tags=["trend", "moving-average"],
    calculation_function="tema",
)

_HULL_MA = IndicatorMetadata(
    id="hull_ma",
    name="Hull MA",
    category="Trend",
    description=(
        "Hull Moving Average (Alan Hull, 2005) — combines two WMAs "
        "and a sqrt-period smoother. Fast yet smooth."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=4, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.hma"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Hull MA is a favourite on Indian intraday charts — it hugs "
        "trend without the lag of slower MAs."
    ),
    tags=["trend", "moving-average", "intraday"],
    calculation_function="hull_ma",
)

# ─── Momentum (5) ──────────────────────────────────────────────────────


_CCI = IndicatorMetadata(
    id="cci",
    name="CCI",
    category="Momentum",
    description=(
        "Commodity Channel Index (Lambert, 1980) — typical-price "
        "deviation from its mean, scaled by mean absolute deviation."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.cci"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "CCI > +100 = strong upside momentum; < -100 = strong "
        "downside. Often used for breakouts plus mean-reversion."
    ),
    tags=["momentum", "oscillator"],
    calculation_function="cci",
)

_WILLIAMS_R = IndicatorMetadata(
    id="williams_r",
    name="Williams %R",
    category="Momentum",
    description=(
        "Williams %R (Larry Williams) — close's position within the "
        "last ``period`` high-low range, scaled to ``[-100, 0]``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.wpr"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "%R > -20 overbought; < -80 oversold. Mirrors Stochastic %K "
        "on a different scale; same idea, different range."
    ),
    tags=["momentum", "oscillator"],
    calculation_function="williams_r",
)

_CHANDE_MOMENTUM = IndicatorMetadata(
    id="chande_momentum",
    name="CMO",
    category="Momentum",
    description=(
        "Chande Momentum Oscillator (Chande, 1995) — like RSI but "
        "uses raw sums of up vs down moves; reacts faster."
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
        "CMO ranges -100 to +100. Crosses through 0 mark momentum "
        "shifts; ±50 readings flag strong moves."
    ),
    tags=["momentum", "oscillator"],
    calculation_function="chande_momentum",
)

_STOCHASTIC = IndicatorMetadata(
    id="stochastic",
    name="Stochastic",
    category="Momentum",
    description=(
        "Stochastic Oscillator (George Lane) — close's position "
        "within the last ``k_period`` range, with a smoothed signal."
    ),
    inputs=[
        InputSpec(name="k_period", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(name="d_period", type=InputType.NUMBER, default=3, min=1, max=100),
    ],
    outputs=["k", "d"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.stoch"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Stochastic > 80 / < 20 flag overbought/oversold; %K crossing "
        "%D is the classic entry/exit cue."
    ),
    tags=["momentum", "oscillator"],
    calculation_function="stochastic",
)

_ROC = IndicatorMetadata(
    id="roc",
    name="ROC",
    category="Momentum",
    description=(
        "Rate of Change — percentage change of close vs ``period`` "
        "bars ago. Pure momentum."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=9, min=1, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.roc"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ROC tells you how strong the recent move is in % terms. "
        "Crossing zero is a simple momentum-flip cue."
    ),
    tags=["momentum"],
    calculation_function="roc",
)

# ─── Volume (1) ────────────────────────────────────────────────────────


_MFI = IndicatorMetadata(
    id="mfi",
    name="MFI",
    category="Volume",
    description=(
        "Money Flow Index — volume-weighted RSI. Reads 0-100; > 80 "
        "and < 20 are the classic overbought/oversold thresholds."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.mfi"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MFI combines price and volume — divergence between MFI and "
        "price often warns of weakening trends before it shows up "
        "on price alone."
    ),
    tags=["momentum", "volume"],
    calculation_function="mfi",
)

# ─── Channels (2) ──────────────────────────────────────────────────────


_DONCHIAN_CHANNEL = IndicatorMetadata(
    id="donchian_channel",
    name="Donchian Channel",
    category="Volatility",
    description=(
        "Donchian Channel — highest high / lowest low over the last "
        "``period`` bars, with the midline at their average. The "
        "original turtle-trader breakout signal."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["upper", "middle", "lower"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.donchian"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Price tagging the upper band = breakout long signal; "
        "tagging the lower band = breakout short. Simple and robust "
        "for trending markets."
    ),
    tags=["volatility", "breakout", "channels"],
    calculation_function="donchian_channel",
)

_KELTNER_CHANNEL = IndicatorMetadata(
    id="keltner_channel",
    name="Keltner Channel",
    category="Volatility",
    description=(
        "Keltner Channel — EMA midline plus/minus ``multiplier`` x "
        "ATR. Volatility-aware envelope, smoother than Bollinger."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(
            name="multiplier", type=InputType.NUMBER, default=2.0, min=0.1, max=10
        ),
    ],
    outputs=["upper", "middle", "lower"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.kc"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Bollinger Bands inside Keltner Channels = TTM-Squeeze setup, "
        "a classic volatility-compression breakout pattern."
    ),
    tags=["volatility", "channels", "atr"],
    calculation_function="keltner_channel",
)

# ─── Aggregate ─────────────────────────────────────────────────────────


PACK2_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _VWMA,
    _SUPERTREND,
    _PARABOLIC_SAR,
    _SMMA,
    _DEMA,
    _TEMA,
    _HULL_MA,
    _CCI,
    _WILLIAMS_R,
    _CHANDE_MOMENTUM,
    _STOCHASTIC,
    _ROC,
    _MFI,
    _DONCHIAN_CHANNEL,
    _KELTNER_CHANNEL,
)


__all__ = ["PACK2_ACTIVE_INDICATORS"]
