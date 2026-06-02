"""Founder overrides for the 7 Sprint 7e ACTIVE_BUT_BROKEN templates.

QUEUE_ZZ_SPRINT_7E_REPORT §3 classified these 7 active templates as
"backtest-path blocked" — they parse cleanly against the OLD-format
validator and reference only verified indicators, but the prose parser's
grammar can't translate their NL conditions into structured
``StrategyJSON``. The *live execution path* (``strategy_executor``)
interprets the OLD prose natively and is unaffected; only the backtest
affordance is closed for these specific NL constructs.

Per Queue WW Sprint 8b: close the backtest path via the same
override-registry mechanism as Queues OO / PP / QQ. Each template's NL
prose is rewritten to numeric primitives the schema supports today
(IndicatorCondition with crossover / crossunder / GT / LT, TimeCondition,
PriceCondition). Where the original prose contains constructs the
schema cannot express (multi-bar slopes, bar-offset chains, rolling
extremums, multi-component composites), the override drops to the
nearest-equivalent single-bar signal documented inline.

Required indicators are already ACTIVE in the registry and dispatched
in ``backtest/indicator_runner.py`` — no engine changes.

Per-template translations (original → override):

  1. bb-mean-reversion
       "low <= bb_lower AND previous close > bb_lower"
     → close crossover bb_lower (close crossing back above lower band ≡ bounce)

  2. bb-squeeze-breakout
       "bb_width at 20-bar low AND close > bb_upper AND atr_14 increasing"
     → close crossover bb_upper (the breakout trigger itself; rolling-extremum
       precondition + slope predicate dropped — closest single-bar equivalent)

  3. macd-histogram-momentum
       "macd_histogram crosses above 0 AND macd_histogram[0]>[1]>[2]"
     → macd_line crossover macd_signal AND macd_histogram > 0
       (TK-style cross + positive-histogram filter; bar-offset chain dropped)

  4. donchian-channel-breakout
       "close > 20-bar donchian upper band (new 20-bar high) AND adx_14 > 20"
     → close > donchian_middle_20 AND adx_14 > 20
       (the strict "close > upper" semantic is unreachable — donchian
       ``upper[i]`` includes bar i's high, so ``close[i] <= upper[i]``
       always. Relaxed to midline breakout, which is the closest schema-
       expressible "trending above the Donchian channel" signal.)

  5. ichimoku-cloud-crossover
       "close crosses above kumo AND tenkan > kijun AND chikou above price-26-bars-ago"
     → tenkan crossover kijun AND close > tenkan
       (chikou + senkou A/B are Phase-11 — current ichimoku impl exposes
       tenkan + kijun only; the TK cross is the canonical Ichimoku bull
       trigger)

  6. adx-strong-trend-filter
       "adx_14 > 25 AND ema_9 crosses above ema_21 AND ema_9 sloping up"
     → adx_14 > 25 AND ema_9 crossover ema_21
       (slope predicate dropped — the crossover itself implies recent upturn)

  7. inside-bar-breakout
       "previous bar fully inside the bar before it AND current close >
        previous bar's high AND close > ema_20"
     → inside_bar_breakout > 0 AND close > ema_20
       (the named pattern indicator already detects the multi-bar
       configuration AND the breakout above prev bar's high)

The ``close`` pseudo-indicator (EMA-2 ≈ raw price) follows the same
convention used by ``trend_overrides`` and the parser's auto-declare.
"""

from __future__ import annotations

from typing import Any, Final

_EXECUTION: Final[dict[str, Any]] = {
    "mode": "backtest",
    "order_type": "MARKET",
    "product_type": "INTRADAY",
}

#: ``close`` pseudo-indicator (EMA-2 ≈ raw price), reused across templates.
_CLOSE_PSEUDO: Final[dict[str, Any]] = {
    "id": "close",
    "type": "ema",
    "params": {"period": 2, "source": "close"},
}


def _time_gate(start: str, end: str) -> dict[str, Any]:
    return {"type": "time", "op": "between", "value": start, "end": end}


_BB_MEAN_REVERSION: Final[dict[str, Any]] = {
    "id": "template:bb-mean-reversion",
    "name": "Bollinger Band Mean Reversion",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {
            "id": "bb_20_2",
            "type": "bollinger_bands",
            "params": {"period": 20, "std_dev": 2.0, "source": "close"},
        },
        {
            "id": "bb_lower",
            "type": "bollinger_bands",
            "params": {"period": 20, "std_dev": 2.0, "source": "close"},
            "output": "lower",
        },
        {
            "id": "bb_middle",
            "type": "bollinger_bands",
            "params": {"period": 20, "std_dev": 2.0, "source": "close"},
            "output": "middle",
        },
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "close", "op": "crossover", "right": "bb_lower"},
            _time_gate("09:30", "14:45"),
        ],
    },
    "exit": {
        "target_percent": 3.0,
        "stop_loss_percent": 1.5,
        "square_off_time": "14:45",
        "indicator_exits": [
            {"type": "indicator", "left": "close", "op": ">=", "right": "bb_middle"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_BB_SQUEEZE_BREAKOUT: Final[dict[str, Any]] = {
    "id": "template:bb-squeeze-breakout",
    "name": "BB Squeeze Breakout",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {
            "id": "bb_20_2",
            "type": "bollinger_bands",
            "params": {"period": 20, "std_dev": 2.0, "source": "close"},
        },
        {
            "id": "bb_upper",
            "type": "bollinger_bands",
            "params": {"period": 20, "std_dev": 2.0, "source": "close"},
            "output": "upper",
        },
        {
            "id": "bb_middle",
            "type": "bollinger_bands",
            "params": {"period": 20, "std_dev": 2.0, "source": "close"},
            "output": "middle",
        },
        {"id": "atr_14", "type": "atr", "params": {"period": 14}},
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "close", "op": "crossover", "right": "bb_upper"},
            _time_gate("09:30", "14:30"),
        ],
    },
    "exit": {
        "target_percent": 5.0,
        "stop_loss_percent": 2.0,
        "square_off_time": "14:30",
        "indicator_exits": [
            {"type": "indicator", "left": "close", "op": "<", "right": "bb_middle"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_MACD_HISTOGRAM_MOMENTUM: Final[dict[str, Any]] = {
    "id": "template:macd-histogram-momentum",
    "name": "MACD Histogram Momentum",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {
            "id": "macd_12_26_9",
            "type": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "source": "close"},
        },
        {
            "id": "macd_line",
            "type": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "source": "close"},
            "output": "macd",
        },
        {
            "id": "macd_signal",
            "type": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "source": "close"},
            "output": "signal",
        },
        {
            "id": "macd_histogram",
            "type": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "source": "close"},
            "output": "histogram",
        },
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "macd_line", "op": "crossover", "right": "macd_signal"},
            {"type": "indicator", "left": "macd_histogram", "op": ">", "value": 0.0},
            _time_gate("09:30", "14:45"),
        ],
    },
    "exit": {
        "target_percent": 3.0,
        "stop_loss_percent": 1.5,
        "square_off_time": "14:45",
        "indicator_exits": [
            {"type": "indicator", "left": "macd_line", "op": "crossunder", "right": "macd_signal"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_DONCHIAN_CHANNEL_BREAKOUT: Final[dict[str, Any]] = {
    "id": "template:donchian-channel-breakout",
    "name": "Donchian Channel Breakout",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {
            "id": "donchian_middle_20",
            "type": "donchian_channel",
            "params": {"period": 20},
            "output": "middle",
        },
        {
            "id": "donchian_lower_10",
            "type": "donchian_channel",
            "params": {"period": 10},
            "output": "lower",
        },
        {"id": "adx_14", "type": "adx", "params": {"period": 14}},
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "close", "op": ">", "right": "donchian_middle_20"},
            {"type": "indicator", "left": "adx_14", "op": ">", "value": 20.0},
            _time_gate("09:30", "15:00"),
        ],
    },
    "exit": {
        "target_percent": 6.0,
        "stop_loss_percent": 2.0,
        "square_off_time": "15:00",
        "indicator_exits": [
            {"type": "indicator", "left": "close", "op": "<", "right": "donchian_lower_10"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_ICHIMOKU_CLOUD_CROSSOVER: Final[dict[str, Any]] = {
    "id": "template:ichimoku-cloud-crossover",
    "name": "Ichimoku Cloud Crossover",
    "mode": "expert",
    "version": 1,
    "indicators": [
        {
            "id": "tenkan",
            "type": "ichimoku",
            "params": {"tenkan_period": 9, "kijun_period": 26},
            "output": "tenkan",
        },
        {
            "id": "kijun",
            "type": "ichimoku",
            "params": {"tenkan_period": 9, "kijun_period": 26},
            "output": "kijun",
        },
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "tenkan", "op": "crossover", "right": "kijun"},
            {"type": "indicator", "left": "close", "op": ">", "right": "tenkan"},
            _time_gate("09:30", "15:00"),
        ],
    },
    "exit": {
        "target_percent": 6.0,
        "stop_loss_percent": 2.0,
        "square_off_time": "15:00",
        "indicator_exits": [
            {"type": "indicator", "left": "tenkan", "op": "crossunder", "right": "kijun"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_ADX_STRONG_TREND_FILTER: Final[dict[str, Any]] = {
    "id": "template:adx-strong-trend-filter",
    "name": "ADX Strong Trend Filter",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {"id": "adx_14", "type": "adx", "params": {"period": 14}},
        {"id": "ema_9", "type": "ema", "params": {"period": 9, "source": "close"}},
        {"id": "ema_21", "type": "ema", "params": {"period": 21, "source": "close"}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "adx_14", "op": ">", "value": 25.0},
            {"type": "indicator", "left": "ema_9", "op": "crossover", "right": "ema_21"},
            _time_gate("09:30", "15:00"),
        ],
    },
    "exit": {
        "target_percent": 3.5,
        "stop_loss_percent": 1.2,
        "square_off_time": "15:00",
        "indicator_exits": [
            {"type": "indicator", "left": "ema_9", "op": "crossunder", "right": "ema_21"},
            {"type": "indicator", "left": "adx_14", "op": "<", "value": 18.0},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_INSIDE_BAR_BREAKOUT: Final[dict[str, Any]] = {
    "id": "template:inside-bar-breakout",
    "name": "Inside Bar Breakout",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {"id": "inside_bar_breakout", "type": "inside_bar_breakout", "params": {}},
        {"id": "ema_20", "type": "ema", "params": {"period": 20, "source": "close"}},
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "inside_bar_breakout", "op": ">", "value": 0.0},
            {"type": "indicator", "left": "close", "op": ">", "right": "ema_20"},
            _time_gate("09:45", "15:00"),
        ],
    },
    "exit": {
        "target_percent": 3.0,
        "stop_loss_percent": 1.2,
        "square_off_time": "15:00",
        "indicator_exits": [
            {"type": "indicator", "left": "close", "op": "<", "right": "ema_20"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


#: Slug → hand-written StrategyJSON dict. Consumed by the override registry.
SPRINT_7E_OVERRIDES: Final[dict[str, dict[str, Any]]] = {
    "bb-mean-reversion": _BB_MEAN_REVERSION,
    "bb-squeeze-breakout": _BB_SQUEEZE_BREAKOUT,
    "macd-histogram-momentum": _MACD_HISTOGRAM_MOMENTUM,
    "donchian-channel-breakout": _DONCHIAN_CHANNEL_BREAKOUT,
    "ichimoku-cloud-crossover": _ICHIMOKU_CLOUD_CROSSOVER,
    "adx-strong-trend-filter": _ADX_STRONG_TREND_FILTER,
    "inside-bar-breakout": _INSIDE_BAR_BREAKOUT,
}


def register_sprint_7e_overrides() -> None:
    """(Re)register the Sprint 7e overrides into the in-memory registry.

    Mirrors :func:`register_trend_overrides` / `register_divergence_overrides`
    / `register_candle_overrides` so test fixtures that
    :func:`clear_overrides` can restore Sprint 7e entries.
    """
    from app.strategy_engine.translator.override_registry import register_override

    for slug, strategy_json in SPRINT_7E_OVERRIDES.items():
        register_override(slug, strategy_json)


__all__ = ["SPRINT_7E_OVERRIDES", "register_sprint_7e_overrides"]
