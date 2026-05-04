"""Pre-compute every indicator series the strategy declares.

Internal helper for :mod:`app.strategy_engine.backtest.simulator`. We
compute ALL configured indicators ONCE up-front and look up values by
``(indicator_id, bar_index)`` inside the simulator hot loop. This keeps
the simulator O(N) per strategy regardless of how many indicators are
configured.

Each Phase 1 active indicator has a different input signature
(EMA/SMA/WMA/RSI/Volume SMA take ``Sequence[float]`` + period; ATR takes
high/low/close; VWAP/OBV take OHLCV; MACD/Bollinger return tuples). The
dispatcher below knows the shape of each.

**Multi-output indicators (MACD, Bollinger Bands)**: Phase 3 stores the
*primary* output under the strategy's ``IndicatorConfig.id``:

    macd_default        -> macd line  (the "MACD line" itself)
    bb_default          -> middle line (SMA)

Sub-output access via dotted notation (``macd_default.signal``,
``bb_default.upper``) is a Phase 9 expansion — Phase 1's StrategyJSON
cross-reference validator currently rejects it. The simulator emits a
warning when a multi-output indicator is configured to make this
limitation visible.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.registry import (
    INDICATOR_REGISTRY,
    get_calculation_function,
    validate_indicator_params,
)
from app.strategy_engine.schema.ohlcv import Candle, PriceSource
from app.strategy_engine.schema.strategy import IndicatorConfig, StrategyJSON

#: Indicators that Phase 3 stores under their config id with a single
#: list value. Multi-output indicators (MACD, Bollinger) get the primary
#: output under the config id but additionally store sub-outputs under
#: the dotted form for Phase 9 forward-compat.
_MULTI_OUTPUT_INDICATORS: frozenset[str] = frozenset({"macd", "bollinger_bands"})


class IndicatorRunnerError(ValueError):
    """Raised when an indicator config can't be resolved or computed."""


def precompute_indicators(
    candles: Sequence[Candle], strategy: StrategyJSON
) -> tuple[dict[str, list[float | None]], list[str]]:
    """Run every ``strategy.indicators`` row over ``candles``.

    Returns:
        ``(series_by_id, warnings)`` — ``series_by_id`` maps the strategy's
        indicator ids to same-length-as-candles series. ``warnings`` is
        a list of operator-visible notes (e.g. multi-output limitation).

    Raises:
        IndicatorRunnerError: Unknown indicator type, invalid params, or
            insufficient candle count for a configured period.
    """
    series_by_id: dict[str, list[float | None]] = {}
    warnings: list[str] = []

    for cfg in strategy.indicators:
        meta = INDICATOR_REGISTRY.get(cfg.type)
        if meta is None:
            raise IndicatorRunnerError(f"Unknown indicator type: {cfg.type!r}.")

        try:
            params = validate_indicator_params(cfg.type, cfg.params)
        except ValueError as exc:
            raise IndicatorRunnerError(
                f"Invalid params for indicator {cfg.id!r} (type={cfg.type!r}): {exc}"
            ) from exc

        primary, extras = _compute_one(cfg, params, candles)
        series_by_id[cfg.id] = primary

        if extras:
            for suffix, sub_series in extras.items():
                series_by_id[f"{cfg.id}.{suffix}"] = sub_series
            warnings.append(
                f"Indicator {cfg.id!r} (type={cfg.type!r}) is multi-output; "
                "only the primary line is referenced by name. Phase 9 will add "
                "dotted-notation access (e.g. {cfg.id}.signal)."
            )

    return series_by_id, warnings


def _compute_one(
    cfg: IndicatorConfig,
    params: dict[str, object],
    candles: Sequence[Candle],
) -> tuple[list[float | None], dict[str, list[float | None]]]:
    """Dispatch a single config to its calculation. Returns (primary, extras)."""
    fn = get_calculation_function(cfg.type)

    if cfg.type in ("ema", "sma", "wma", "rsi"):
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        values = _extract_source(candles, source)
        primary: list[float | None] = fn(values, period)
        return primary, {}

    if cfg.type == "volume_sma":
        period = _coerce_int(params["period"])
        volumes = [c.volume for c in candles]
        return fn(volumes, period), {}

    if cfg.type == "macd":
        source = _coerce_str(params.get("source", "close"))
        fast = _coerce_int(params["fast_period"])
        slow = _coerce_int(params["slow_period"])
        signal = _coerce_int(params["signal_period"])
        values = _extract_source(candles, source)
        macd_line, signal_line, hist = fn(values, fast, slow, signal)
        return macd_line, {"macd": macd_line, "signal": signal_line, "histogram": hist}

    if cfg.type == "bollinger_bands":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        std_dev = _coerce_float(params["std_dev"])
        values = _extract_source(candles, source)
        upper, middle, lower = fn(values, period, std_dev)
        return middle, {"upper": upper, "middle": middle, "lower": lower}

    if cfg.type == "atr":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period), {}

    if cfg.type == "vwap":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes), {}

    if cfg.type == "obv":
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes), {}

    raise IndicatorRunnerError(  # pragma: no cover — guarded by registry membership
        f"No backtest dispatch for indicator type {cfg.type!r}."
    )


# ─── Helpers ────────────────────────────────────────────────────────────


def _extract_source(candles: Sequence[Candle], source: str) -> list[float]:
    """Pull the requested price series out of the candle list."""
    src = PriceSource(source)
    return [c.price(src) for c in candles]


def _coerce_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IndicatorRunnerError(f"Expected int param; got {type(value).__name__}={value!r}.")
    return value


def _coerce_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IndicatorRunnerError(f"Expected number param; got {type(value).__name__}={value!r}.")
    return float(value)


def _coerce_str(value: object) -> str:
    if not isinstance(value, str):
        raise IndicatorRunnerError(f"Expected str param; got {type(value).__name__}={value!r}.")
    return value


def values_at(series_by_id: dict[str, list[float | None]], index: int) -> dict[str, float | None]:
    """Slice every series at ``index`` into a flat dict for the engines.

    Out-of-range indices raise ``IndexError`` so the simulator's bug
    surfaces immediately rather than silently returning ``None`` values.
    """
    return {name: series[index] for name, series in series_by_id.items()}


__all__ = [
    "IndicatorRunnerError",
    "precompute_indicators",
    "values_at",
]
