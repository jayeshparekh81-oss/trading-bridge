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

    # ─── Pack 4 — S/R + statistical + volatility/range ───────────────────

    if cfg.type in ("std_dev", "variance"):
        # Single-source statistical scalars over a rolling window.
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        values = _extract_source(candles, source)
        return fn(values, period), {}

    if cfg.type == "correlation_coefficient":
        source_a = _coerce_str(params.get("source_a", "close"))
        source_b = _coerce_str(params.get("source_b", "open"))
        period = _coerce_int(params["period"])
        values_a = _extract_source(candles, source_a)
        values_b = _extract_source(candles, source_b)
        return fn(values_a, values_b, period), {}

    if cfg.type == "historical_volatility":
        period = _coerce_int(params["period"])
        annualization = _coerce_int(params["annualization"])
        closes = [c.close for c in candles]
        return fn(closes, period, annualization), {}

    if cfg.type == "true_range":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes), {}

    if cfg.type == "high_low_spread":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes), {}

    if cfg.type == "inside_bar":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows), {}

    if cfg.type == "swing_high":
        left = _coerce_int(params["left_bars"])
        right = _coerce_int(params["right_bars"])
        highs = [c.high for c in candles]
        return fn(highs, left, right), {}

    if cfg.type == "swing_low":
        left = _coerce_int(params["left_bars"])
        right = _coerce_int(params["right_bars"])
        lows = [c.low for c in candles]
        return fn(lows, left, right), {}

    if cfg.type == "camarilla_pivots":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        r3, r4, s3, s4 = fn(highs, lows, closes)
        return r3, {"r3": r3, "r4": r4, "s3": s3, "s4": s4}

    if cfg.type == "woodie_pivots":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        pp, r1, r2, s1, s2 = fn(highs, lows, closes)
        return pp, {"pp": pp, "r1": r1, "r2": r2, "s1": s1, "s2": s2}

    if cfg.type == "regression_channel":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        std_dev = _coerce_float(params["std_dev"])
        values = _extract_source(candles, source)
        middle, upper, lower = fn(values, period, std_dev)
        return middle, {"middle": middle, "upper": upper, "lower": lower}

    # ─── Pack 5 — advanced statistical / risk / performance ─────────────

    if cfg.type in ("percentile_rank", "median_value", "zscore"):
        # Single-source single-line with just (values, period).
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        values = _extract_source(candles, source)
        return fn(values, period), {}

    if cfg.type == "percentile_nearest":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        percentage = _coerce_float(params["percentage"])
        values = _extract_source(candles, source)
        return fn(values, period, percentage), {}

    if cfg.type == "sharpe_ratio":
        period = _coerce_int(params["period"])
        annualization = _coerce_int(params["annualization"])
        risk_free_rate = _coerce_float(params["risk_free_rate"])
        closes = [c.close for c in candles]
        return fn(closes, period, annualization, risk_free_rate), {}

    if cfg.type == "sortino_ratio":
        period = _coerce_int(params["period"])
        annualization = _coerce_int(params["annualization"])
        risk_free_rate = _coerce_float(params["risk_free_rate"])
        target_return = _coerce_float(params["target_return"])
        closes = [c.close for c in candles]
        return (
            fn(closes, period, annualization, risk_free_rate, target_return),
            {},
        )

    if cfg.type == "calmar_ratio":
        period = _coerce_int(params["period"])
        annualization = _coerce_int(params["annualization"])
        closes = [c.close for c in candles]
        return fn(closes, period, annualization), {}

    if cfg.type == "omega_ratio":
        period = _coerce_int(params["period"])
        threshold = _coerce_float(params["threshold"])
        closes = [c.close for c in candles]
        return fn(closes, period, threshold), {}

    if cfg.type in ("max_drawdown_pct", "recovery_factor"):
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "underwater_curve":
        # Cumulative — no period param, runs from the start of the
        # input series.
        closes = [c.close for c in candles]
        return fn(closes), {}

    if cfg.type == "hurst_exponent":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    # ─── Pack 6 — volume flow + advanced volatility ─────────────────────

    if cfg.type == "accumulation_distribution":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes), {}

    if cfg.type == "chaikin_oscillator":
        fast = _coerce_int(params["fast"])
        slow = _coerce_int(params["slow"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, fast, slow), {}

    if cfg.type == "price_volume_trend":
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes), {}

    if cfg.type == "ease_of_movement":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, volumes, period), {}

    if cfg.type == "twiggs_money_flow":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, period), {}

    if cfg.type == "mass_index":
        ema_period = _coerce_int(params["ema_period"])
        sum_period = _coerce_int(params["sum_period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, ema_period, sum_period), {}

    if cfg.type == "awesome_oscillator":
        fast = _coerce_int(params["fast"])
        slow = _coerce_int(params["slow"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, fast, slow), {}

    if cfg.type == "elder_ray_bull":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, closes, period), {}

    if cfg.type == "elder_ray_bear":
        period = _coerce_int(params["period"])
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(lows, closes, period), {}

    if cfg.type == "choppiness_index":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period), {}

    if cfg.type in ("bollinger_bandwidth", "bollinger_percent_b"):
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        std_dev = _coerce_float(params["std_dev"])
        values = _extract_source(candles, source)
        return fn(values, period, std_dev), {}

    # ─── Pack 7 — trend strength + advanced momentum ────────────────────

    if cfg.type in ("aroon_up", "aroon_down", "aroon_oscillator"):
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, period), {}

    if cfg.type in ("vortex_positive", "vortex_negative"):
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period), {}

    if cfg.type == "klinger_volume_oscillator":
        fast = _coerce_int(params["fast"])
        slow = _coerce_int(params["slow"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, fast, slow), {}

    if cfg.type == "detrended_price_oscillator":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "coppock_curve":
        short_p = _coerce_int(params["short_period"])
        long_p = _coerce_int(params["long_period"])
        wma_p = _coerce_int(params["wma_period"])
        closes = [c.close for c in candles]
        return fn(closes, short_p, long_p, wma_p), {}

    if cfg.type == "fisher_transform":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, period), {}

    if cfg.type == "chande_kroll_stop":
        atr_period = _coerce_int(params["atr_period"])
        atr_mult = _coerce_float(params["atr_mult"])
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, atr_period, atr_mult, period), {}

    if cfg.type == "relative_vigor_index":
        period = _coerce_int(params["period"])
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes, period), {}

    if cfg.type == "balance_of_power":
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes), {}

    # ─── Pack 8 — multi-timeframe + specialty + India-specific ──────────

    if cfg.type == "mtf_ema_alignment":
        # ``periods`` arrives as comma-separated string from the
        # registry's STRING InputSpec. Parse to a tuple of ints
        # here so the calc gets clean types.
        raw_periods = _coerce_str(params.get("periods", "20,50,200"))
        periods = tuple(int(p.strip()) for p in raw_periods.split(",") if p.strip())
        closes = [c.close for c in candles]
        return fn(closes, periods), {}

    if cfg.type == "higher_high_lower_low":
        lookback = _coerce_int(params["lookback"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, lookback), {}

    if cfg.type == "swing_failure":
        lookback = _coerce_int(params["lookback"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, lookback), {}

    if cfg.type == "weekly_pivot_close":
        weeks_back = _coerce_int(params["weeks_back"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, lows, closes, timestamps, weeks_back), {}

    if cfg.type == "opening_range_breakout":
        range_minutes = _coerce_int(params["range_minutes"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, lows, closes, timestamps, range_minutes), {}

    if cfg.type == "gap_up_down":
        threshold = _coerce_float(params["threshold_pct"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, closes, threshold), {}

    if cfg.type == "daily_pivot_distance":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, lows, closes, timestamps), {}

    if cfg.type == "nifty_correlation":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "zigzag":
        deviation_pct = _coerce_float(params["deviation_pct"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, deviation_pct), {}

    if cfg.type == "fractal_chaos_bands":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, period), {}

    if cfg.type == "ehlers_fisher":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "mcginley_dynamic":
        period = _coerce_int(params["period"])
        constant = _coerce_float(params["constant"])
        closes = [c.close for c in candles]
        return fn(closes, period, constant), {}

    # ─── Pack 9 — bands + envelopes + advanced MAs ──────────────────────

    if cfg.type in ("envelope_upper", "envelope_lower"):
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        pct = _coerce_float(params["pct"])
        values = _extract_source(candles, source)
        return fn(values, period, pct), {}

    if cfg.type in ("starc_upper", "starc_lower"):
        period = _coerce_int(params["period"])
        atr_period = _coerce_int(params["atr_period"])
        atr_mult = _coerce_float(params["atr_mult"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period, atr_period, atr_mult), {}

    if cfg.type == "price_channel_high":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        return fn(highs, period), {}

    if cfg.type == "price_channel_low":
        period = _coerce_int(params["period"])
        lows = [c.low for c in candles]
        return fn(lows, period), {}

    if cfg.type in ("linear_regression_upper", "linear_regression_lower"):
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        std_mult = _coerce_float(params["std_mult"])
        values = _extract_source(candles, source)
        return fn(values, period, std_mult), {}

    if cfg.type == "arnaud_legoux_ma":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        sigma = _coerce_float(params["sigma"])
        offset = _coerce_float(params["offset"])
        values = _extract_source(candles, source)
        return fn(values, period, sigma, offset), {}

    if cfg.type == "vidya":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        values = _extract_source(candles, source)
        return fn(values, period), {}

    if cfg.type == "zlema":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        values = _extract_source(candles, source)
        return fn(values, period), {}

    if cfg.type == "kaufman_ama":
        source = _coerce_str(params.get("source", "close"))
        period = _coerce_int(params["period"])
        fast = _coerce_int(params["fast"])
        slow = _coerce_int(params["slow"])
        values = _extract_source(candles, source)
        return fn(values, period, fast, slow), {}

    # ─── Pack 10 — volume profile + microstructure + order flow ─────────

    if cfg.type == "volume_weighted_avg_close":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes, period), {}

    if cfg.type == "volume_at_price_high":
        period = _coerce_int(params["period"])
        bins = _coerce_int(params["bins"])
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes, period, bins), {}

    if cfg.type == "volume_breakout":
        period = _coerce_int(params["period"])
        spike_mult = _coerce_float(params["spike_mult"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(opens, closes, volumes, period, spike_mult), {}

    if cfg.type == "positive_volume_index":
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes), {}

    if cfg.type == "true_strength_index":
        long = _coerce_int(params["long"])
        short = _coerce_int(params["short"])
        closes = [c.close for c in candles]
        return fn(closes, long, short), {}

    if cfg.type == "percent_price_oscillator":
        fast = _coerce_int(params["fast"])
        slow = _coerce_int(params["slow"])
        signal = _coerce_int(params["signal"])
        closes = [c.close for c in candles]
        return fn(closes, fast, slow, signal), {}

    if cfg.type == "rate_of_change_volume":
        period = _coerce_int(params["period"])
        volumes = [c.volume for c in candles]
        return fn(volumes, period), {}

    if cfg.type == "negative_volume_index":
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes), {}

    if cfg.type == "money_flow_ratio":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, period), {}

    if cfg.type == "on_balance_volume_ema":
        ema_period = _coerce_int(params["ema_period"])
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes, ema_period), {}

    if cfg.type == "cumulative_volume_delta":
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(opens, closes, volumes), {}

    if cfg.type == "buying_pressure_ratio":
        period = _coerce_int(params["period"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(opens, closes, volumes, period), {}

    # ─── Pack 11 — cycle + divergence + advanced patterns ───────────────

    if cfg.type == "dominant_cycle_period":
        smooth = _coerce_float(params["smooth"])
        closes = [c.close for c in candles]
        return fn(closes, smooth), {}

    if cfg.type in ("mesa_sine_wave", "mesa_sine_lead"):
        alpha = _coerce_float(params["alpha"])
        closes = [c.close for c in candles]
        return fn(closes, alpha), {}

    if cfg.type == "cycle_period_oscillator":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period), {}

    if cfg.type == "rsi_divergence":
        rsi_period = _coerce_int(params["rsi_period"])
        lookback = _coerce_int(params["lookback"])
        closes = [c.close for c in candles]
        return fn(closes, rsi_period, lookback), {}

    if cfg.type == "macd_divergence":
        fast = _coerce_int(params["fast"])
        slow = _coerce_int(params["slow"])
        signal = _coerce_int(params["signal"])
        lookback = _coerce_int(params["lookback"])
        closes = [c.close for c in candles]
        return fn(closes, fast, slow, signal, lookback), {}

    if cfg.type == "obv_divergence":
        lookback = _coerce_int(params["lookback"])
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes, lookback), {}

    if cfg.type == "inside_bar_breakout":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows), {}

    if cfg.type == "outside_bar":
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes), {}

    if cfg.type == "nr7":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows), {}

    if cfg.type == "wide_range_bar":
        lookback = _coerce_int(params["lookback"])
        mult = _coerce_float(params["mult"])
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, highs, lows, closes, lookback, mult), {}

    if cfg.type == "consolidation_score":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, period), {}

    # ─── Pack 12 — volatility regime + risk-adjusted + bands ────────────

    if cfg.type == "atr_percent":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period), {}

    if cfg.type == "volatility_regime":
        lookback = _coerce_int(params["lookback"])
        atr_period = _coerce_int(params["atr_period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, lookback, atr_period), {}

    if cfg.type == "parkinson_volatility":
        period = _coerce_int(params["period"])
        bars_per_year = _coerce_int(params["bars_per_year"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, period, bars_per_year), {}

    if cfg.type == "volatility_ratio":
        short = _coerce_int(params["short"])
        long = _coerce_int(params["long"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, short, long), {}

    if cfg.type == "trade_efficiency":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type in ("ulcer_index", "martin_ratio", "burke_ratio"):
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type in ("chandelier_exit_long", "chandelier_exit_short"):
        period = _coerce_int(params["period"])
        atr_mult = _coerce_float(params["atr_mult"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period, atr_mult), {}

    if cfg.type == "supertrend_v2":
        period = _coerce_int(params["period"])
        atr_mult = _coerce_float(params["atr_mult"])
        volatility_lookback = _coerce_int(params["volatility_lookback"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period, atr_mult, volatility_lookback), {}

    if cfg.type == "atr_trailing_stop":
        atr_period = _coerce_int(params["atr_period"])
        atr_mult = _coerce_float(params["atr_mult"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, atr_period, atr_mult), {}

    # ─── Pack 13 — sentiment + breadth + cross-asset ────────────────────

    if cfg.type == "fear_greed_index":
        lookback = _coerce_int(params["lookback"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, lookback), {}

    if cfg.type == "breadth_thrust":
        period = _coerce_int(params["period"])
        ema_period = _coerce_int(params["ema_period"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, closes, period, ema_period), {}

    if cfg.type == "sentiment_oscillator":
        period = _coerce_int(params["period"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, closes, period), {}

    if cfg.type == "capitulation_signal":
        vol_mult = _coerce_float(params["vol_mult"])
        range_mult = _coerce_float(params["range_mult"])
        lookback = _coerce_int(params["lookback"])
        threshold = _coerce_float(params["close_position_threshold"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(highs, lows, closes, volumes, vol_mult, range_mult, lookback, threshold), {}

    if cfg.type == "tick_index":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "advance_decline_proxy":
        period = _coerce_int(params["period"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, closes, period), {}

    if cfg.type == "mcclellan_oscillator_proxy":
        fast = _coerce_int(params["fast"])
        slow = _coerce_int(params["slow"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        return fn(opens, closes, fast, slow), {}

    if cfg.type == "trin_proxy":
        period = _coerce_int(params["period"])
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(opens, closes, volumes, period), {}

    if cfg.type == "relative_strength_vs_benchmark":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "correlation_with_volume":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes, period), {}

    if cfg.type == "divergence_strength_score":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return fn(closes, volumes, period), {}

    if cfg.type == "trend_consistency_score":
        # ``timeframes`` arrives as comma-separated string from the
        # registry's STRING InputSpec. Parse to a tuple of ints
        # here so the calc gets clean types (same convention as
        # Pack 8's mtf_ema_alignment).
        raw_timeframes = _coerce_str(params.get("timeframes", "10,20,50"))
        timeframes = tuple(
            int(p.strip()) for p in raw_timeframes.split(",") if p.strip()
        )
        closes = [c.close for c in candles]
        return fn(closes, timeframes), {}

    # ─── Pack 14 — statistical + regression + advanced math ─────────────

    if cfg.type in (
        "linear_regression_slope",
        "r_squared",
        "polynomial_regression_2",
        "polynomial_regression_3",
        "exponential_regression",
        "logarithmic_regression",
        "spectral_dominant_period",
        "half_life_mean_reversion",
    ):
        source = _coerce_str(params.get("source", "close"))
        # window-style indicators use ``window`` instead of
        # ``period`` for spectral_dominant_period; the rest use
        # ``period``.
        param_key = "window" if cfg.type == "spectral_dominant_period" else "period"
        period = _coerce_int(params[param_key])
        values = _extract_source(candles, source)
        return fn(values, period), {}

    if cfg.type in ("skewness", "kurtosis"):
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "variance_ratio":
        short = _coerce_int(params["short"])
        long = _coerce_int(params["long"])
        closes = [c.close for c in candles]
        return fn(closes, short, long), {}

    if cfg.type == "autocorrelation":
        period = _coerce_int(params["period"])
        lag = _coerce_int(params["lag"])
        closes = [c.close for c in candles]
        return fn(closes, period, lag), {}

    # ─── Pack 15 — time-based + session + intraday ──────────────────────

    if cfg.type == "day_of_week_signal":
        timestamps = [c.timestamp for c in candles]
        return fn(timestamps), {}

    if cfg.type == "hour_of_day":
        timestamps = [c.timestamp for c in candles]
        return fn(timestamps), {}

    if cfg.type == "minutes_to_close":
        market_close_hour = _coerce_int(params["market_close_hour"])
        market_close_min = _coerce_int(params["market_close_min"])
        timestamps = [c.timestamp for c in candles]
        return fn(timestamps, market_close_hour, market_close_min), {}

    if cfg.type == "is_expiry_week":
        timestamps = [c.timestamp for c in candles]
        return fn(timestamps), {}

    if cfg.type == "session_open_distance":
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(opens, closes, timestamps), {}

    if cfg.type == "session_high_breakout":
        highs = [c.high for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, timestamps), {}

    if cfg.type == "session_low_breakout":
        lows = [c.low for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(lows, timestamps), {}

    if cfg.type == "session_volume_pace":
        lookback_days = _coerce_int(params["lookback_days"])
        volumes = [c.volume for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(volumes, timestamps, lookback_days), {}

    if cfg.type == "first_hour_range":
        minutes = _coerce_int(params["minutes"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, lows, timestamps, minutes), {}

    if cfg.type == "last_hour_momentum":
        minutes = _coerce_int(params["minutes"])
        market_close_hour = _coerce_int(params["market_close_hour"])
        market_close_min = _coerce_int(params["market_close_min"])
        closes = [c.close for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(closes, timestamps, minutes, market_close_hour, market_close_min), {}

    if cfg.type == "lunch_consolidation":
        lunch_start_hour = _coerce_int(params["lunch_start_hour"])
        lunch_end_hour = _coerce_int(params["lunch_end_hour"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, lows, volumes, timestamps, lunch_start_hour, lunch_end_hour), {}

    if cfg.type == "opening_gap_size":
        opens = [c.open for c in candles]
        closes = [c.close for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(opens, closes, timestamps), {}

    # ─── Pack 16 — options-aware + Greeks-proxy ─────────────────────────

    if cfg.type == "iv_proxy_atr":
        atr_period = _coerce_int(params["atr_period"])
        bars_per_year = _coerce_int(params["bars_per_year"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, atr_period, bars_per_year), {}

    if cfg.type in ("iv_rank", "iv_percentile"):
        lookback = _coerce_int(params["lookback"])
        atr_period = _coerce_int(params["atr_period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, lookback, atr_period), {}

    if cfg.type == "vix_correlation":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

    if cfg.type == "atm_strike_distance":
        strike_step = _coerce_float(params["strike_step"])
        closes = [c.close for c in candles]
        return fn(closes, strike_step), {}

    if cfg.type == "round_number_attraction":
        strike_step = _coerce_float(params["strike_step"])
        threshold_pct = _coerce_float(params["threshold_pct"])
        closes = [c.close for c in candles]
        return fn(closes, strike_step, threshold_pct), {}

    if cfg.type == "expiry_day_volatility":
        weekday_target = _coerce_int(params["weekday_target"])
        history_sessions = _coerce_int(params["history_sessions"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, lows, timestamps, weekday_target, history_sessions), {}

    if cfg.type == "monthly_pivot_distance":
        months_back = _coerce_int(params["months_back"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        timestamps = [c.timestamp for c in candles]
        return fn(highs, lows, closes, timestamps, months_back), {}

    if cfg.type == "delta_proxy_directional":
        period = _coerce_int(params["period"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, period), {}

    if cfg.type == "theta_proxy_decay":
        lookback = _coerce_int(params["lookback"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        return fn(highs, lows, lookback), {}

    if cfg.type == "vega_proxy_iv_sensitivity":
        short = _coerce_int(params["short"])
        long = _coerce_int(params["long"])
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        return fn(highs, lows, closes, short, long), {}

    if cfg.type == "gamma_proxy_acceleration":
        period = _coerce_int(params["period"])
        closes = [c.close for c in candles]
        return fn(closes, period), {}

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
