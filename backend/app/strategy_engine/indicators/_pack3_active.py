"""Pack 3 — 12 candlestick pattern detectors as active indicators.

Each row registers a pattern as a real indicator the dispatcher
emits as a 0.0 / 1.0 series (1.0 at the bar where the pattern is
detected; 0.0 otherwise; ``None`` for the warm-up bars where the
pattern's lookback can't be evaluated).

Patterns ship under a fresh ``Pattern`` category so they're
discoverable separately from Trend / Momentum / Volume in the
builder UI. Every entry is INTERMEDIATE difficulty — there's an
existing ``test_beginner_recommended_subset`` lock that pins the
exact set of beginner-recommended ids to ``{ema, sma, rsi,
volume_sma}``; promoting any pattern there would trip it.

Pine importer: TradingView's standard ``ta.*`` namespace does NOT
ship built-in candlestick pattern detectors (no ``ta.doji`` /
``ta.hammer`` / ``ta.engulfing``), so Pack 3 deliberately skips the
Pine wiring — adding these names to ``SUPPORTED_TA_INDICATORS``
would invent recognition for nonexistent calls. Users author
pattern conditions through the builder UI.
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

# ─── Single-bar patterns (4) ───────────────────────────────────────────


_DOJI = IndicatorMetadata(
    id="doji",
    name="Doji",
    category="Pattern",
    description=(
        "Doji — open and close are nearly equal. Body must sit within "
        "``body_ratio`` of the bar's full range. Signals indecision; "
        "context (uptrend / downtrend) determines reversal vs continuation."
    ),
    inputs=[
        InputSpec(name="body_ratio", type=InputType.NUMBER, default=0.1, min=0.001, max=1.0),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Doji means market couldn't decide kis taraf jaana hai. After "
        "a strong uptrend or downtrend yeh pattern reversal warning "
        "hota hai — confirmation ke liye next candle dekho."
    ),
    tags=["pattern", "single-bar", "reversal"],
    calculation_function="doji",
)

_HAMMER = IndicatorMetadata(
    id="hammer",
    name="Hammer",
    category="Pattern",
    description=(
        "Hammer — single-bar bullish reversal hint. Small body in the "
        "upper third of the range, long lower wick (>= ``shadow_ratio``), "
        "short upper wick. Direction-agnostic — body colour can be "
        "either way."
    ),
    inputs=[
        InputSpec(name="body_ratio", type=InputType.NUMBER, default=0.3, min=0.05, max=0.5),
        InputSpec(name="shadow_ratio", type=InputType.NUMBER, default=0.6, min=0.4, max=0.95),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Hammer downtrend ke baad bullish reversal ka classic signal. "
        "Long lower wick dikhata hai sellers ne push kiya tha but "
        "buyers ne wapas le liya."
    ),
    tags=["pattern", "single-bar", "bullish-reversal"],
    calculation_function="hammer",
)

_SHOOTING_STAR = IndicatorMetadata(
    id="shooting_star",
    name="Shooting Star",
    category="Pattern",
    description=(
        "Shooting Star — single-bar bearish reversal hint. Mirror of "
        "Hammer: small body in the lower third, long upper wick "
        "(>= ``shadow_ratio``), short lower wick."
    ),
    inputs=[
        InputSpec(name="body_ratio", type=InputType.NUMBER, default=0.3, min=0.05, max=0.5),
        InputSpec(name="shadow_ratio", type=InputType.NUMBER, default=0.6, min=0.4, max=0.95),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Shooting Star uptrend ke baad bearish reversal ka warning. "
        "Buyers ne push kiya but sellers ne neeche dhakel diya — "
        "weakness sign."
    ),
    tags=["pattern", "single-bar", "bearish-reversal"],
    calculation_function="shooting_star",
)

_MARUBOZU = IndicatorMetadata(
    id="marubozu",
    name="Marubozu",
    category="Pattern",
    description=(
        "Marubozu — solid candle with no (or near-zero) wicks. "
        "Direction-agnostic; both bullish (open=low, close=high) and "
        "bearish (open=high, close=low) marubozu detected."
    ),
    inputs=[
        InputSpec(
            name="max_wick_ratio", type=InputType.NUMBER, default=0.05, min=0.001, max=0.4
        ),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Marubozu strong conviction candle hai — buyers ya sellers ne "
        "open se close tak control rakha. Trend ki strength confirm "
        "karne ke liye useful."
    ),
    tags=["pattern", "single-bar", "trend"],
    calculation_function="marubozu",
)

# ─── Two-bar patterns (4) ──────────────────────────────────────────────


_BULLISH_ENGULFING = IndicatorMetadata(
    id="bullish_engulfing",
    name="Bullish Engulfing",
    category="Pattern",
    description=(
        "Bullish Engulfing — bar i-1 closes bearish, bar i closes "
        "bullish and its body fully covers bar i-1's body."
    ),
    inputs=[],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Bullish Engulfing classic reversal — bears ka prior bar puri "
        "tarah engulf ho gaya bulls ke ek bade green candle se."
    ),
    tags=["pattern", "two-bar", "bullish-reversal"],
    calculation_function="bullish_engulfing",
)

_BEARISH_ENGULFING = IndicatorMetadata(
    id="bearish_engulfing",
    name="Bearish Engulfing",
    category="Pattern",
    description=(
        "Bearish Engulfing — mirror of bullish engulfing. Bar i-1 "
        "bullish, bar i bearish and engulfs prior body."
    ),
    inputs=[],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Bearish Engulfing uptrend ki top mein dikhe to strong sell "
        "signal — bulls ko bears ne ek bar mein khaa liya."
    ),
    tags=["pattern", "two-bar", "bearish-reversal"],
    calculation_function="bearish_engulfing",
)

_PIERCING_PATTERN = IndicatorMetadata(
    id="piercing_pattern",
    name="Piercing Pattern",
    category="Pattern",
    description=(
        "Piercing Pattern — softer cousin of bullish engulfing. Bar i "
        "gaps down, then closes above bar i-1's mid-body but below "
        "bar i-1's open (so it doesn't fully engulf)."
    ),
    inputs=[],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Piercing Pattern half-engulfing reversal hai — bulls ne bear "
        "candle ke 50%+ ko recover kiya, full nahi. Confirmation ke "
        "liye next bar dekho."
    ),
    tags=["pattern", "two-bar", "bullish-reversal"],
    calculation_function="piercing_pattern",
)

_DARK_CLOUD_COVER = IndicatorMetadata(
    id="dark_cloud_cover",
    name="Dark Cloud Cover",
    category="Pattern",
    description=(
        "Dark Cloud Cover — mirror of piercing pattern. Bar i gaps "
        "up, then closes below bar i-1's mid-body but above bar i-1's "
        "open."
    ),
    inputs=[],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Dark Cloud Cover bearish reversal hint — bulls ne high banayi "
        "aur bears ne 50%+ wapas le liya, weakness ka sign."
    ),
    tags=["pattern", "two-bar", "bearish-reversal"],
    calculation_function="dark_cloud_cover",
)

# ─── Three-bar patterns (4) ────────────────────────────────────────────


_MORNING_STAR = IndicatorMetadata(
    id="morning_star",
    name="Morning Star",
    category="Pattern",
    description=(
        "Morning Star — three-bar bullish reversal. Long bearish "
        "candle, then a small-body 'star' (gapped below the bearish "
        "body), then a bullish candle that closes above the first "
        "bar's mid-body."
    ),
    inputs=[
        InputSpec(name="small_body_ratio", type=InputType.NUMBER, default=0.3, min=0.05, max=0.5),
        InputSpec(name="big_body_ratio", type=InputType.NUMBER, default=0.5, min=0.2, max=0.9),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Morning Star strong reversal pattern hai bottom mein. Pehla "
        "bearish bar selling pressure dikhata hai, doosra small-body "
        "star indecision, teesra bullish bar trend ka shift confirm "
        "karta hai."
    ),
    tags=["pattern", "three-bar", "bullish-reversal"],
    calculation_function="morning_star",
)

_EVENING_STAR = IndicatorMetadata(
    id="evening_star",
    name="Evening Star",
    category="Pattern",
    description=(
        "Evening Star — mirror of morning star. Long bullish candle, "
        "small-body star gapped above, then a bearish candle closing "
        "below the first bar's mid-body."
    ),
    inputs=[
        InputSpec(name="small_body_ratio", type=InputType.NUMBER, default=0.3, min=0.05, max=0.5),
        InputSpec(name="big_body_ratio", type=InputType.NUMBER, default=0.5, min=0.2, max=0.9),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Evening Star top reversal — strong uptrend ke baad small-body "
        "indecision phir bearish confirmation. Sell signal."
    ),
    tags=["pattern", "three-bar", "bearish-reversal"],
    calculation_function="evening_star",
)

_THREE_WHITE_SOLDIERS = IndicatorMetadata(
    id="three_white_soldiers",
    name="Three White Soldiers",
    category="Pattern",
    description=(
        "Three White Soldiers — three consecutive bullish candles, "
        "each closing higher and opening within the prior body. "
        "Continuation / breakout signal."
    ),
    inputs=[
        InputSpec(name="min_body_ratio", type=InputType.NUMBER, default=0.5, min=0.2, max=0.9),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Three White Soldiers strong bullish continuation pattern. "
        "Range / sideways consolidation ke baad dikhe to breakout "
        "confirmation."
    ),
    tags=["pattern", "three-bar", "bullish-continuation"],
    calculation_function="three_white_soldiers",
)

_THREE_BLACK_CROWS = IndicatorMetadata(
    id="three_black_crows",
    name="Three Black Crows",
    category="Pattern",
    description=(
        "Three Black Crows — three consecutive bearish candles, each "
        "closing lower and opening within the prior body. Bearish "
        "continuation / breakdown signal."
    ),
    inputs=[
        InputSpec(name="min_body_ratio", type=InputType.NUMBER, default=0.5, min=0.2, max=0.9),
    ],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Three Black Crows strong bearish breakdown — bulls ka "
        "control khatam, bears consistent push kar rahe hain. Stop "
        "loss tight rakho."
    ),
    tags=["pattern", "three-bar", "bearish-continuation"],
    calculation_function="three_black_crows",
)

# ─── Aggregate ─────────────────────────────────────────────────────────


PACK3_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _DOJI,
    _HAMMER,
    _SHOOTING_STAR,
    _MARUBOZU,
    _BULLISH_ENGULFING,
    _BEARISH_ENGULFING,
    _PIERCING_PATTERN,
    _DARK_CLOUD_COVER,
    _MORNING_STAR,
    _EVENING_STAR,
    _THREE_WHITE_SOLDIERS,
    _THREE_BLACK_CROWS,
)


__all__ = ["PACK3_ACTIVE_INDICATORS"]
