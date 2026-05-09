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
    n = len(candles)

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
        # Phase 1 calc functions return [] when period > len(candles). Pad to
        # n so values_at() never IndexErrors; downstream None handling is the
        # same as the warmup period.
        series_by_id[cfg.id] = primary if primary else [None] * n

        if extras:
            for suffix, sub_series in extras.items():
                series_by_id[f"{cfg.id}.{suffix}"] = sub_series if sub_series else [None] * n
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

    if cfg.type in ("ema", "sma", "wma", "rsi", "trix", "linear_regression"):
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

    # ─── Phase 9 active indicators ─────────────────────────────────────

    if cfg.type == "adx":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        adx_line, _plus_di, _minus_di = fn(highs, lows, closes, period)
        return adx_line, {}

    if cfg.type == "dmi":
        # Same calculation as ADX (registry meta.calculation_function == "adx");
        # the registry exposes ADX vs DMI as separate indicator ids because
        # operators treat trend strength (ADX) and direction (+DI / -DI) as
        # distinct signals.
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        _adx_line, plus_di, minus_di = fn(highs, lows, closes, period)
        return plus_di, {"plus_di": plus_di, "minus_di": minus_di}

    if cfg.type == "aroon":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        aroon_up, aroon_down, oscillator = fn(highs, lows, period)
        return oscillator, {
            "aroon_up": aroon_up,
            "aroon_down": aroon_down,
            "oscillator": oscillator,
        }

    if cfg.type == "ultimate_oscillator":
        short = _coerce_int(params["short_period"])
        medium = _coerce_int(params["medium_period"])
        long_p = _coerce_int(params["long_period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, short, medium, long_p), {}

    if cfg.type == "cmf":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, period), {}

    if cfg.type == "force_index":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes, period), {}

    if cfg.type == "pivot_points":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        pp, r1, r2, s1, s2 = fn(highs, lows, closes)
        return pp, {"pp": pp, "r1": r1, "r2": r2, "s1": s1, "s2": s2}

    if cfg.type == "ichimoku":
        tenkan_p = _coerce_int(params["tenkan_period"])
        kijun_p = _coerce_int(params["kijun_period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        tenkan, kijun = fn(highs, lows, tenkan_p, kijun_p)
        return tenkan, {"tenkan": tenkan, "kijun": kijun}

    # ─── Pack 2 active indicators (commit 511f591) ───────────────────────

    if cfg.type in ("smma", "dema", "tema", "hull_ma", "chande_momentum", "roc"):
        # Single-source single-line MAs / momentum oscillators.
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        values = _extract_source(candles, source)
        return fn(values, period), {}

    if cfg.type == "vwma":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        values = _extract_source(candles, source)
        volumes = [c.volume for c in candles]
        return fn(values, volumes, period), {}

    if cfg.type == "supertrend":
        period = _coerce_int(params["period"])
        multiplier = _coerce_float(params["multiplier"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        line, direction = fn(highs, lows, closes, period, multiplier)
        return line, {"line": line, "direction": direction}

    if cfg.type == "parabolic_sar":
        step = _coerce_float(params["step"])
        max_step = _coerce_float(params["max_step"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, step, max_step), {}

    if cfg.type in ("cci", "williams_r"):
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period), {}

    if cfg.type == "stochastic":
        k_period = _coerce_int(params["k_period"])
        d_period = _coerce_int(params["d_period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        k_line, d_line = fn(highs, lows, closes, k_period, d_period)
        return k_line, {"k": k_line, "d": d_line}

    if cfg.type == "mfi":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, period), {}

    if cfg.type == "donchian_channel":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        upper, middle, lower = fn(highs, lows, period)
        return middle, {"upper": upper, "middle": middle, "lower": lower}

    if cfg.type == "keltner_channel":
        period = _coerce_int(params["period"])
        multiplier = _coerce_float(params["multiplier"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        upper, middle, lower = fn(highs, lows, closes, period, multiplier)
        return middle, {"upper": upper, "middle": middle, "lower": lower}

    # ─── Pack 3 candlestick pattern detectors (additive) ─────────────────
    #
    # All 12 patterns share the same dispatch shape: extract OHLC,
    # forward params verbatim, return a 0/1 series with no extras.
    # The runner pads ``[]`` returns to ``[None] * n``; the patterns
    # never return ``[]`` for non-empty input but they DO return
    # ``None`` at warm-up bars (e.g. index 0 for 2-bar patterns).

    if cfg.type == "doji":
        body_ratio = _coerce_float(params["body_ratio"])
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes, body_ratio), {}

    if cfg.type in ("hammer", "shooting_star"):
        body_ratio = _coerce_float(params["body_ratio"])
        shadow_ratio = _coerce_float(params["shadow_ratio"])
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes, body_ratio, shadow_ratio), {}

    if cfg.type == "marubozu":
        max_wick_ratio = _coerce_float(params["max_wick_ratio"])
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes, max_wick_ratio), {}

    if cfg.type in (
        "bullish_engulfing",
        "bearish_engulfing",
        "piercing_pattern",
        "dark_cloud_cover",
    ):
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes), {}

    if cfg.type in ("morning_star", "evening_star"):
        small_body_ratio = _coerce_float(params["small_body_ratio"])
        big_body_ratio = _coerce_float(params["big_body_ratio"])
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return (
            fn(opens, highs, lows, closes, small_body_ratio, big_body_ratio),
            {},
        )

    if cfg.type in ("three_white_soldiers", "three_black_crows"):
        min_body_ratio = _coerce_float(params["min_body_ratio"])
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes, min_body_ratio), {}

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
