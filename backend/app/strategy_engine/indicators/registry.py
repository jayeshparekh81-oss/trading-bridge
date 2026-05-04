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
