"""Indicator registry — single source of truth for available indicators.

Every entry is an :class:`IndicatorMetadata` instance. The registry is
populated at import time and is then read-only at runtime. To add a new
indicator: write its calculation function under
:mod:`app.strategy_engine.indicators.calculations` and append a metadata
row here.

Lookup helpers all return defensive copies / read-only views so callers
cannot mutate the registry by accident.

Phase 1 ships 10 active entries:
    EMA, SMA, WMA, RSI, MACD, Bollinger Bands, ATR, VWAP, OBV, Volume SMA.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.strategy_engine.indicators._pack2_active import (
    PACK2_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack3_active import (
    PACK3_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack4_active import (
    PACK4_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack5_active import (
    PACK5_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack6_active import (
    PACK6_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack7_active import (
    PACK7_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack8_active import (
    PACK8_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack9_active import (
    PACK9_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack10_active import (
    PACK10_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack11_active import (
    PACK11_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack12_active import (
    PACK12_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack13_active import (
    PACK13_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack14_active import (
    PACK14_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack15_active import (
    PACK15_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack16_active import (
    PACK16_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack17_active import (
    PACK17_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack18_active import (
    PACK18_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._phase9_active import (
    PHASE9_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._phase9_coming_soon import (
    PHASE9_COMING_SOON_INDICATORS,
)
from app.strategy_engine.indicators._batch1_commission_active import (
    BATCH1_COMMISSION_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack_library_aliases_active import (
    PACK_LIBRARY_ALIASES_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack_completion_wave1_active import (
    PACK_COMPLETION_WAVE1_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators._pack_completion_wave2_active import (
    PACK_COMPLETION_WAVE2_ACTIVE_INDICATORS,
)
from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
    InputSpec,
    InputType,
)


class IndicatorParamError(ValueError):
    """Raised by :func:`validate_indicator_params` when params are invalid."""


# ─── Active indicator metadata (Phase 1: 10 entries) ───────────────────


_EMA = IndicatorMetadata(
    id="ema",
    name="EMA",
    category="Trend",
    description=(
        "Exponential Moving Average — smoothed trend indicator that gives "
        "more weight to recent prices than a simple moving average."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.ema"],
    difficulty=IndicatorDifficulty.BEGINNER,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "EMA helps identify trend direction by smoothing price action. "
        "Price above EMA suggests uptrend; below suggests downtrend."
    ),
    tags=["trend", "moving-average", "beginner"],
    calculation_function="ema",
)

_SMA = IndicatorMetadata(
    id="sma",
    name="SMA",
    category="Trend",
    description=(
        "Simple Moving Average — arithmetic mean of the source price over the last ``period`` bars."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.sma"],
    difficulty=IndicatorDifficulty.BEGINNER,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "SMA shows the average price over a window. Crossovers between a "
        "fast SMA and a slow SMA are a classic trend-change signal."
    ),
    tags=["trend", "moving-average", "beginner"],
    calculation_function="sma",
)

_WMA = IndicatorMetadata(
    id="wma",
    name="WMA",
    category="Trend",
    description=(
        "Weighted Moving Average — linear-weighted mean where the most "
        "recent bar carries the highest weight."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.wma"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "WMA reacts faster than SMA but slower than EMA. Useful when you "
        "want a smoother line that still tracks recent moves."
    ),
    tags=["trend", "moving-average"],
    calculation_function="wma",
)

_RSI = IndicatorMetadata(
    id="rsi",
    name="RSI",
    category="Momentum",
    description=(
        "Relative Strength Index (Wilder) — momentum oscillator that "
        "ranges 0-100. Classic interpretation: >70 overbought, <30 oversold."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.rsi"],
    difficulty=IndicatorDifficulty.BEGINNER,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "RSI measures the speed of price changes. Used to spot momentum "
        "exhaustion (overbought / oversold) and bullish/bearish divergence."
    ),
    tags=["momentum", "oscillator", "beginner"],
    calculation_function="rsi",
)

_MACD = IndicatorMetadata(
    id="macd",
    name="MACD",
    category="Momentum",
    description=(
        "Moving Average Convergence Divergence — difference between fast "
        "and slow EMAs, with a signal-line EMA on top. Three outputs: "
        "macd line, signal line, histogram."
    ),
    inputs=[
        InputSpec(name="fast_period", type=InputType.NUMBER, default=12, min=2, max=200),
        InputSpec(name="slow_period", type=InputType.NUMBER, default=26, min=2, max=500),
        InputSpec(name="signal_period", type=InputType.NUMBER, default=9, min=2, max=200),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["macd", "signal", "histogram"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.macd"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MACD shows trend strength and turning points. The histogram "
        "(macd - signal) flipping sign is a common entry/exit cue."
    ),
    tags=["momentum", "trend"],
    calculation_function="macd",
)

_BOLLINGER = IndicatorMetadata(
    id="bollinger_bands",
    name="Bollinger Bands",
    category="Volatility",
    description=(
        "Bollinger Bands — middle line is an SMA; upper/lower bands are "
        "k standard deviations above/below. Width grows with volatility."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(name="std_dev", type=InputType.NUMBER, default=2.0, min=0.1, max=10),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["upper", "middle", "lower"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.bb"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Bollinger Bands expand in volatile markets and contract in quiet "
        "ones. Price tags of the bands often mean-revert; band squeezes "
        "often precede breakouts."
    ),
    tags=["volatility", "mean-reversion"],
    calculation_function="bollinger_bands",
)

_ATR = IndicatorMetadata(
    id="atr",
    name="ATR",
    category="Volatility",
    description=(
        "Average True Range (Wilder) — average of true range over the "
        "last ``period`` bars. Pure volatility measure, not directional."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=1, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.atr"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ATR sizes risk: a common stop-loss recipe is N x ATR away from "
        "entry. Higher ATR means wider stops are needed."
    ),
    tags=["volatility", "risk-management"],
    calculation_function="atr",
)

_VWAP = IndicatorMetadata(
    id="vwap",
    name="VWAP",
    category="Volume",
    description=(
        "Volume Weighted Average Price — cumulative typical-price x volume "
        "divided by cumulative volume. Heavy intraday reference for "
        "institutional flow."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.vwap"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "VWAP is where the average rupee was traded. Price above VWAP "
        "favours longs; below favours shorts. Common intraday benchmark."
    ),
    tags=["volume", "intraday", "benchmark"],
    calculation_function="vwap",
)

_OBV = IndicatorMetadata(
    id="obv",
    name="OBV",
    category="Volume",
    description=(
        "On-Balance Volume — running sum that adds the bar's volume on up "
        "closes and subtracts it on down closes."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.obv"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "OBV tracks buying vs selling pressure. Divergence between OBV "
        "and price often precedes reversals."
    ),
    tags=["volume", "momentum"],
    calculation_function="obv",
)

_VOLUME_SMA = IndicatorMetadata(
    id="volume_sma",
    name="Volume SMA",
    category="Volume",
    description=(
        "Simple Moving Average of the volume series — used to flag bars "
        "where volume is unusually high or low relative to the recent "
        "average."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.BEGINNER,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Volume SMA is a baseline for 'normal' volume. Bars where current "
        "volume is much higher than the SMA often mark significant moves."
    ),
    tags=["volume", "beginner"],
    calculation_function="volume_sma",
)


#: The registry. Order is preserved (Python dicts are insertion-ordered)
#: so callers iterating for UI display get a deterministic sequence.
#: Phase 1 ships 10 active entries up top; Phase 9 appends 10 more
#: actives + ~85 ``coming_soon`` stubs to reach 100+ total.
INDICATOR_REGISTRY: Mapping[str, IndicatorMetadata] = {
    meta.id: meta
    for meta in (
        _EMA,
        _SMA,
        _WMA,
        _RSI,
        _MACD,
        _BOLLINGER,
        _ATR,
        _VWAP,
        _OBV,
        _VOLUME_SMA,
        *PHASE9_ACTIVE_INDICATORS,
        *PHASE9_COMING_SOON_INDICATORS,
        # Pack 2 splats LAST so its 15 ACTIVE rows override the
        # same-id coming_soon stubs above (Python dict-comp keeps
        # the latest value for duplicate keys).
        *PACK2_ACTIVE_INDICATORS,
        # Pack 3 — 12 candlestick pattern detectors; ids are net-new
        # (no coming_soon stubs to override).
        *PACK3_ACTIVE_INDICATORS,
        # Pack 4 — 12 S/R + statistical + volatility indicators.
        # Mix of net-new ids and coming_soon promotions
        # (std_dev, camarilla_pivots, woodie_pivots,
        # historical_volatility, regression_channel); the splat
        # order means promotions override their stubs.
        *PACK4_ACTIVE_INDICATORS,
        # Pack 5 — 12 advanced statistical / risk / performance
        # indicators (percentile_rank / percentile_nearest /
        # median_value / sharpe_ratio / sortino_ratio /
        # calmar_ratio / omega_ratio / max_drawdown_pct /
        # underwater_curve / recovery_factor / hurst_exponent /
        # zscore). All ids are net-new — no coming_soon overlap.
        *PACK5_ACTIVE_INDICATORS,
        # Pack 6 — 12 volume-flow + advanced-volatility indicators
        # (accumulation_distribution / chaikin_oscillator /
        # price_volume_trend / ease_of_movement / twiggs_money_flow /
        # mass_index / awesome_oscillator / elder_ray_bull /
        # elder_ray_bear / choppiness_index / bollinger_bandwidth /
        # bollinger_percent_b). All ids net-new — collisions on
        # ``force_index`` + ``ultimate_oscillator`` substituted with
        # ``twiggs_money_flow`` + ``mass_index`` during discovery.
        *PACK6_ACTIVE_INDICATORS,
        # Pack 7 — 12 trend-strength + advanced-momentum indicators
        # (aroon_up / aroon_down / aroon_oscillator /
        # vortex_positive / vortex_negative /
        # klinger_volume_oscillator / detrended_price_oscillator /
        # coppock_curve / fisher_transform / chande_kroll_stop /
        # relative_vigor_index / balance_of_power). The Aroon
        # single-line ids project the existing ``aroon`` calc into
        # standalone series; the ``trix`` collision was substituted
        # with ``klinger_volume_oscillator`` during discovery.
        *PACK7_ACTIVE_INDICATORS,
        # Pack 8 — 12 multi-timeframe + specialty + India-specific
        # indicators (mtf_ema_alignment / higher_high_lower_low /
        # swing_failure / weekly_pivot_close /
        # opening_range_breakout / gap_up_down /
        # daily_pivot_distance / nifty_correlation / zigzag /
        # fractal_chaos_bands / ehlers_fisher / mcginley_dynamic).
        # All ids net-new — no collisions detected. Two indicators
        # ship with documented caveats: ``nifty_correlation`` is a
        # Phase-1 stub pending data-provider wiring, and
        # ``opening_range_breakout`` requires intraday timestamps
        # (returns all-None on daily-or-larger candles).
        *PACK8_ACTIVE_INDICATORS,
        # Pack 9 — 12 bands + envelopes + advanced moving averages
        # (envelope_upper / envelope_lower / starc_upper /
        # starc_lower / price_channel_high / price_channel_low /
        # linear_regression_upper / linear_regression_lower /
        # arnaud_legoux_ma / vidya / zlema / kaufman_ama). The
        # ``tema`` and ``hull_ma`` collisions were substituted
        # with ``arnaud_legoux_ma`` + ``vidya`` during discovery.
        # ``ta.highest`` / ``ta.lowest`` Pine wirings rewired
        # from the stale "donchian coming_soon" note to the new
        # ``price_channel_high`` / ``price_channel_low`` actives.
        *PACK9_ACTIVE_INDICATORS,
        # Pack 10 — 12 volume profile + microstructure + order
        # flow indicators (volume_weighted_avg_close /
        # volume_at_price_high / volume_breakout /
        # positive_volume_index / true_strength_index /
        # percent_price_oscillator / rate_of_change_volume /
        # negative_volume_index / money_flow_ratio /
        # on_balance_volume_ema / cumulative_volume_delta /
        # buying_pressure_ratio). The
        # ``accumulation_distribution_index`` near-collision was
        # substituted with ``positive_volume_index`` (companion
        # to NVI). Pine wires for ``ta.tsi`` + ``ta.ppo``.
        *PACK10_ACTIVE_INDICATORS,
        # Pack 11 — 12 cycle + divergence + advanced pattern
        # indicators (dominant_cycle_period / mesa_sine_wave /
        # mesa_sine_lead / cycle_period_oscillator /
        # rsi_divergence / macd_divergence / obv_divergence /
        # inside_bar_breakout / outside_bar / nr7 /
        # wide_range_bar / consolidation_score). All ids net-new.
        # NO Pine wiring — none of Pack 11's indicators have a
        # standard Pine v5 ta.* equivalent (custom Hilbert /
        # divergence / pattern formulations).
        *PACK11_ACTIVE_INDICATORS,
        # Pack 12 — 12 volatility regime + risk-adjusted +
        # volatility band indicators (atr_percent /
        # volatility_regime / parkinson_volatility /
        # volatility_ratio / trade_efficiency / ulcer_index /
        # martin_ratio / burke_ratio / chandelier_exit_long /
        # chandelier_exit_short / supertrend_v2 /
        # atr_trailing_stop). The ``realized_volatility`` near-
        # collision (same calc as the existing
        # ``historical_volatility``) was substituted with
        # ``parkinson_volatility`` (distinct high-low-range
        # estimator) during discovery. NO Pine wiring — all custom
        # / composite formulations.
        *PACK12_ACTIVE_INDICATORS,
        # Pack 13 — 12 sentiment + breadth + cross-asset
        # indicators (fear_greed_index / breadth_thrust /
        # sentiment_oscillator / capitulation_signal /
        # tick_index / advance_decline_proxy /
        # mcclellan_oscillator_proxy / trin_proxy /
        # relative_strength_vs_benchmark (STUB) /
        # correlation_with_volume / divergence_strength_score /
        # trend_consistency_score). The ``bull_bear_power``
        # naming overlap (Elder's Bull Power / Bear Power
        # already in Pack 6) was substituted with Zweig's
        # ``breadth_thrust``. ``relative_strength_vs_benchmark``
        # is a Phase-1 stub — Phase 2 wires the benchmark series
        # fetch. NO Pine wiring — all custom / proxy formulations.
        *PACK13_ACTIVE_INDICATORS,
        # Pack 14 — 12 statistical + regression + advanced math
        # indicators (linear_regression_slope / r_squared /
        # skewness / kurtosis / polynomial_regression_2 /
        # polynomial_regression_3 / exponential_regression /
        # logarithmic_regression / variance_ratio /
        # autocorrelation / spectral_dominant_period /
        # half_life_mean_reversion). All ids net-new.
        # ``linear_regression_slope`` projects the existing
        # ``linear_regression`` calc (same pattern as Pack 7's
        # aroon_up/down/oscillator on the existing aroon).
        # ``spectral_dominant_period`` (FFT) coexists with Pack
        # 11's ``dominant_cycle_period`` (Hilbert) — different
        # mechanism, complementary signal. NO Pine wiring — all
        # custom / specialty formulations.
        *PACK14_ACTIVE_INDICATORS,
        # Pack 15 — 12 time-based + session + intraday indicators
        # (day_of_week_signal / hour_of_day / minutes_to_close /
        # is_expiry_week / session_open_distance /
        # session_high_breakout / session_low_breakout /
        # session_volume_pace / first_hour_range /
        # last_hour_momentum / lunch_consolidation /
        # opening_gap_size). All ids net-new. Pack 15's
        # ``opening_gap_size`` (continuous %) coexists with Pack
        # 8's ``gap_up_down`` (discrete classifier). All Pack 15
        # indicators are frequency-aware — return all-None on
        # daily-or-larger candle frequencies (where intraday
        # context doesn't apply). NO Pine wiring — all custom
        # timestamp-aware formulations (Pine has time helpers as
        # reserved variables, not as ta.* functions).
        *PACK15_ACTIVE_INDICATORS,
        # Pack 16 - 12 options-aware + Greeks-PROXY indicators
        # (iv_proxy_atr / iv_rank / iv_percentile /
        # vix_correlation (STUB) / atm_strike_distance /
        # round_number_attraction / expiry_day_volatility /
        # monthly_pivot_distance / delta_proxy_directional /
        # theta_proxy_decay / vega_proxy_iv_sensitivity /
        # gamma_proxy_acceleration). The spec's
        # ``weekly_pivot_distance`` near-collision (same calc as
        # Pack 8's weekly_pivot_close) was substituted with
        # ``monthly_pivot_distance``. ALL Greeks are PRICE-
        # DERIVED PROXIES, not Black-Scholes; documented loudly.
        # vix_correlation is a Phase-1 stub. NO Pine wiring -
        # all custom proxies.
        *PACK16_ACTIVE_INDICATORS,
        # Pack 17 - 12 composite-signal + ML-style feature
        # indicators (trend_quality_score / momentum_quality_score
        # / mean_reversion_score / breakout_probability_score /
        # price_velocity / price_acceleration /
        # volume_momentum_ratio / range_expansion_score /
        # trend_continuation_score / reversal_likelihood_score /
        # consolidation_breakout_score / exhaustion_score). All
        # composites synthesise Pack 2-16 primitives. Score
        # outputs in documented ranges (0..100, unbounded, or
        # centered ratio) per indicator. NO new Pine wiring -
        # all custom composites; lock test
        # ``test_pack17_has_no_pine_aliases`` pins the contract.
        *PACK17_ACTIVE_INDICATORS,
        # Pack 18 - 15 final indicators. MILESTONE: hits 230
        # active. 14 net-new + 1 promotion (ttm_squeeze, was
        # COMING_SOON in Phase 9 - splat-after-coming-soon
        # pattern, same as Pack 4 std_dev / camarilla_pivots
        # promotions). Two honest stubs:
        # nse_bse_arbitrage_proxy (HAS_DUAL_EXCHANGE=False) and
        # nifty_50_relative_position (HAS_SYMBOL_CONTEXT=False) -
        # both ship as all-None until Phase 2 data-provider
        # wiring lands. One Pine alias added: ta.mom ->
        # momentum_oscillator (only verified Pine v5 ta.* in
        # this pack); lock test pins the contract.
        *PACK18_ACTIVE_INDICATORS,
        # Batch-1 commission promotions (May 18). Splatted LAST so the
        # dict-comprehension's "later splat wins" rule promotes the
        # following ids from COMING_SOON to ACTIVE:
        #   heikin_ashi (was COMING_SOON in _phase9_coming_soon)
        #   alma        (was COMING_SOON; calc aliases to arnaud_legoux_ma)
        #   kama        (was COMING_SOON in _phase9_coming_soon)
        # Plus two net-new ids:
        #   pivot_swing             — wraps swing_high + swing_low
        #   fibonacci_retracement   — retracement levels per bar
        *BATCH1_COMMISSION_ACTIVE_INDICATORS,
        # Library-canonical alias pack — surfaces 6 existing backend
        # indicators under their retail-canonical slugs (CMO, KVO, PPO,
        # HMA, Momentum, Comparative RS) so the strategy builder finds
        # the same compute under either id. Ids are NET-NEW (no
        # collisions with existing entries).
        *PACK_LIBRARY_ALIASES_ACTIVE_INDICATORS,
        # Indicator-completion Wave 1 — new implementations closing
        # the gap between frontend library content and backend compute.
        # All ids NET-NEW; no collisions.
        *PACK_COMPLETION_WAVE1_ACTIVE_INDICATORS,
        # Indicator-completion Wave 2 + 3 — medium/high-complexity
        # implementations from the locked variants in the reference doc.
        *PACK_COMPLETION_WAVE2_ACTIVE_INDICATORS,
    )
}


# ─── Lookup helpers ────────────────────────────────────────────────────


def get_indicator_by_id(indicator_id: str) -> IndicatorMetadata | None:
    """Return the metadata for ``indicator_id``, or ``None`` if absent."""
    return INDICATOR_REGISTRY.get(indicator_id)


def get_indicators_by_category(category: str) -> list[IndicatorMetadata]:
    """All indicators in a given category. Case-insensitive match."""
    target = category.strip().lower()
    return [meta for meta in INDICATOR_REGISTRY.values() if meta.category.lower() == target]


def get_active_indicators() -> list[IndicatorMetadata]:
    """All indicators with ``status == ACTIVE`` — usable in execution paths."""
    return [meta for meta in INDICATOR_REGISTRY.values() if meta.status is IndicatorStatus.ACTIVE]


def get_beginner_recommended_indicators() -> list[IndicatorMetadata]:
    """Active + beginner-difficulty subset — what the guided builder shows."""
    return [
        meta
        for meta in INDICATOR_REGISTRY.values()
        if (
            meta.status is IndicatorStatus.ACTIVE
            and meta.difficulty is IndicatorDifficulty.BEGINNER
        )
    ]


def list_categories() -> list[str]:
    """Sorted unique category names across the registry."""
    return sorted({meta.category for meta in INDICATOR_REGISTRY.values()})


# ─── Param validation ─────────────────────────────────────────────────


_VALID_PRICE_SOURCES: frozenset[str] = frozenset(
    {"open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4"}
)


def validate_indicator_params(indicator_id: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """Validate + normalise ``params`` against the registry's :class:`InputSpec`.

    Args:
        indicator_id: Registry id (``"ema"``, ``"rsi"``, ...).
        params: Caller-supplied parameter dict (typically from the
            strategy JSON's ``IndicatorConfig.params``).

    Returns:
        A new dict with validated values. Defaults are filled in for
        missing keys; provided values are coerced (int → float for
        NUMBER inputs that take floats, etc.).

    Raises:
        IndicatorParamError: Unknown indicator id, unknown param name,
            value out of range, or wrong type. Error message names the
            offending key.
    """
    meta = INDICATOR_REGISTRY.get(indicator_id)
    if meta is None:
        raise IndicatorParamError(f"Unknown indicator id: {indicator_id!r}.")

    spec_by_name = {spec.name: spec for spec in meta.inputs}

    unknown = set(params) - set(spec_by_name)
    if unknown:
        raise IndicatorParamError(
            f"Unknown param(s) {sorted(unknown)} for indicator {indicator_id!r}. "
            f"Allowed: {sorted(spec_by_name)}."
        )

    resolved: dict[str, Any] = {}
    for name, spec in spec_by_name.items():
        value = params.get(name, spec.default)
        resolved[name] = _coerce_and_check(indicator_id, spec, value)
    return resolved


def _coerce_and_check(indicator_id: str, spec: InputSpec, value: Any) -> Any:
    """Type-check ``value`` against ``spec`` and apply min/max bounds.

    Booleans are NOT accepted in NUMBER fields even though Python treats
    ``bool`` as ``int`` — that quirk frequently masks UI bugs and would
    let ``period=True`` slip through.
    """
    if spec.type is InputType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise IndicatorParamError(
                f"Param {spec.name!r} of indicator {indicator_id!r} must be a "
                f"number; got {type(value).__name__} = {value!r}."
            )
        numeric = float(value)
        if spec.min is not None and numeric < spec.min:
            raise IndicatorParamError(
                f"Param {spec.name!r} of indicator {indicator_id!r} must be "
                f">= {spec.min}; got {value!r}."
            )
        if spec.max is not None and numeric > spec.max:
            raise IndicatorParamError(
                f"Param {spec.name!r} of indicator {indicator_id!r} must be "
                f"<= {spec.max}; got {value!r}."
            )
        # Preserve int when the user passed int (lets callers depend on
        # period being int in calculation code).
        return value if isinstance(value, int) else numeric

    if spec.type is InputType.SOURCE:
        if not isinstance(value, str) or value not in _VALID_PRICE_SOURCES:
            raise IndicatorParamError(
                f"Param {spec.name!r} of indicator {indicator_id!r} must be one "
                f"of {sorted(_VALID_PRICE_SOURCES)}; got {value!r}."
            )
        return value

    if spec.type is InputType.BOOLEAN:
        if not isinstance(value, bool):
            raise IndicatorParamError(
                f"Param {spec.name!r} of indicator {indicator_id!r} must be "
                f"bool; got {type(value).__name__}."
            )
        return value

    if spec.type is InputType.STRING:
        if not isinstance(value, str):
            raise IndicatorParamError(
                f"Param {spec.name!r} of indicator {indicator_id!r} must be "
                f"str; got {type(value).__name__}."
            )
        return value

    raise IndicatorParamError(  # pragma: no cover - unreachable if InputType complete
        f"Unhandled InputType {spec.type!r} for param {spec.name!r}."
    )


def get_calculation_function(indicator_id: str) -> Callable[..., Any]:
    """Resolve the registry's ``calculation_function`` name to a callable.

    Late-binds the import so the registry module itself does not depend
    on the calculations sub-package at import time. Coming-soon entries
    (``calculation_function is None``) raise.
    """
    meta = INDICATOR_REGISTRY.get(indicator_id)
    if meta is None:
        raise IndicatorParamError(f"Unknown indicator id: {indicator_id!r}.")
    if meta.calculation_function is None:
        raise IndicatorParamError(
            f"Indicator {indicator_id!r} is {meta.status.value} and has no calculation function."
        )
    from importlib import import_module

    module = import_module(
        f"app.strategy_engine.indicators.calculations.{meta.calculation_function}"
    )
    fn = getattr(module, meta.calculation_function, None)
    if fn is None or not callable(fn):
        raise IndicatorParamError(
            f"Calculation module for {indicator_id!r} does not expose a "
            f"callable named {meta.calculation_function!r}."
        )
    return fn  # type: ignore[no-any-return]


__all__ = [
    "INDICATOR_REGISTRY",
    "IndicatorParamError",
    "get_active_indicators",
    "get_beginner_recommended_indicators",
    "get_calculation_function",
    "get_indicator_by_id",
    "get_indicators_by_category",
    "list_categories",
    "validate_indicator_params",
]
