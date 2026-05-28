"""Founder overrides for the 3 divergence templates (Queue OO / C2).

Queue BB classified ``rsi-divergence``, ``macd-divergence`` and
``obv-divergence`` as FAIL_UNPARSEABLE: their seed ``config_json`` prose
describes divergence as a multi-bar swing comparison
("price prints lower low ... AND <indicator> prints higher low"), which the
prose parser cannot grammar-match and which the StrategyJSON schema has no
stateful primitive for. Queue BB's recommendation was "deactivate until
divergence support ships."

Divergence support HAS since shipped: ``rsi_divergence`` / ``macd_divergence``
/ ``obv_divergence`` are registered (``indicators/_pack11_active.py``) and
dispatched in the backtest runner (``backtest/indicator_runner.py``). Each emits
a single per-bar code — ``+1.0`` bullish / ``-1.0`` bearish / ``0.0`` none —
that already encapsulates the multi-bar swing detection. So a single
``IndicatorCondition(left="<x>_divergence", op=">", value=0.0)`` expresses the
whole "price lower-low + indicator higher-low" pattern with NO schema or grammar
stateful support.

These hand-written ``StrategyJSON`` dicts are registered into the translator's
override registry (the "Option Z hybrid" path), so ``translate_template`` returns
them directly and the prose parser is skipped. See
``docs/QUEUE_OO_TRANSLATOR_C2.md`` for the full design + sign-off record.

Fidelity notes (founder-approved simplifications, decision 3):
  * "price lower low + X higher low (bullish divergence)" → ``<x>_divergence > 0``
    (exact — that is literally what the indicator computes).
  * "current candle bullish reversal pattern" → ``CandleCondition(BULLISH)``.
  * "macd line above its signal" → ``macd_line > signal_line`` (declared via the
    ``IndicatorConfig.output`` sub-output field, same mechanism A2 added).
  * % bands ("within 1% of ema_50", "ema_50 - 1%") → plain ``close >/< ema_50``.
  * "rsi crosses below 50" — crossover/crossunder are undefined against a constant
    in the schema, so this exit clause is dropped (SL/TP + the ``rsi > 70`` clause
    and square-off still exit).
  * "macd histogram contracts for 3 consecutive bars" — multi-bar, no primitive;
    dropped (it was an OR-clause; the ``crossunder`` clause + SL/TP cover the exit).

``close`` is declared as ``ema(period=2)`` — the same near-raw-price proxy the
prose parser auto-injects for bare ``close`` references (EMA(1) is rejected by the
registry's ``period >= 2`` rule; EMA(2) is the minimum legal smoothing and is
within the comparison tolerance these templates use).
"""

from __future__ import annotations

from typing import Any, Final

#: Trading-hours gate shared by all three templates (matches the seed
#: ``trading_hours`` 09:30-15:00; ``square_off_time`` mirrors ``end``).
_TIME_GATE: Final[dict[str, Any]] = {
    "type": "time",
    "op": "between",
    "value": "09:30",
    "end": "15:00",
}

_EXECUTION: Final[dict[str, Any]] = {
    "mode": "backtest",
    "order_type": "MARKET",
    "product_type": "INTRADAY",
}


_RSI_DIVERGENCE: Final[dict[str, Any]] = {
    "id": "template:rsi-divergence",
    "name": "RSI Divergence",
    "mode": "expert",
    "version": 1,
    "indicators": [
        # The divergence detector owns the multi-bar swing logic; +1 = bullish.
        {"id": "rsi_div", "type": "rsi_divergence", "params": {"rsi_period": 14, "lookback": 20}},
        # rsi_14 for the overbought exit clause.
        {"id": "rsi_14", "type": "rsi", "params": {"period": 14, "source": "close"}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "rsi_div", "op": ">", "value": 0.0},
            {"type": "candle", "pattern": "bullish"},
            _TIME_GATE,
        ],
    },
    "exit": {
        "target_percent": 4.5,
        "stop_loss_percent": 1.5,
        "square_off_time": "15:00",
        "indicator_exits": [
            {"type": "indicator", "left": "rsi_14", "op": ">", "value": 70.0},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_MACD_DIVERGENCE: Final[dict[str, Any]] = {
    "id": "template:macd-divergence",
    "name": "MACD Divergence",
    "mode": "expert",
    "version": 1,
    "indicators": [
        {
            "id": "macd_div",
            "type": "macd_divergence",
            "params": {"fast": 12, "slow": 26, "signal": 9, "lookback": 25},
        },
        # macd line + signal line as sub-outputs of two macd instances
        # (IndicatorConfig.output selects the emitted series — A2's mechanism).
        {
            "id": "macd_line",
            "type": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "source": "close"},
            "output": "macd",
        },
        {
            "id": "signal_line",
            "type": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "source": "close"},
            "output": "signal",
        },
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "macd_div", "op": ">", "value": 0.0},
            {"type": "indicator", "left": "macd_line", "op": ">", "right": "signal_line"},
            _TIME_GATE,
        ],
    },
    "exit": {
        "target_percent": 4.5,
        "stop_loss_percent": 1.5,
        "square_off_time": "15:00",
        "indicator_exits": [
            {"type": "indicator", "left": "macd_line", "op": "crossunder", "right": "signal_line"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_OBV_DIVERGENCE: Final[dict[str, Any]] = {
    "id": "template:obv-divergence",
    "name": "OBV Divergence",
    "mode": "expert",
    "version": 1,
    "indicators": [
        {"id": "obv_div", "type": "obv_divergence", "params": {"lookback": 25}},
        {"id": "ema_50", "type": "ema", "params": {"period": 50, "source": "close"}},
        # close pseudo-indicator = EMA(2) ≈ raw price (parser's own convention).
        {"id": "close", "type": "ema", "params": {"period": 2, "source": "close"}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        # Trend filter relaxed off the ENTRY (founder decision 3): the seed's
        # "close > ema_50 OR close within 1% of ema_50" is a deliberately loose
        # band, and a *fresh price low* (required for the divergence) structurally
        # cannot sit above the lagging 50-EMA — strict `close > ema_50` yields ZERO
        # trades. The divergence signal is the entry; trend-awareness is retained on
        # the EXIT (`close < ema_50` below). `% within` has no schema primitive.
        "conditions": [
            {"type": "indicator", "left": "obv_div", "op": ">", "value": 0.0},
            _TIME_GATE,
        ],
    },
    "exit": {
        "target_percent": 5.0,
        "stop_loss_percent": 1.8,
        "square_off_time": "15:00",
        "indicator_exits": [
            # Bearish divergence emerging (price higher-high, OBV lower-high).
            {"type": "indicator", "left": "obv_div", "op": "<", "value": 0.0},
            # Trend break.
            {"type": "indicator", "left": "close", "op": "<", "right": "ema_50"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


#: Slug → hand-written StrategyJSON dict. Consumed by the override registry.
DIVERGENCE_OVERRIDES: Final[dict[str, dict[str, Any]]] = {
    "rsi-divergence": _RSI_DIVERGENCE,
    "macd-divergence": _MACD_DIVERGENCE,
    "obv-divergence": _OBV_DIVERGENCE,
}


def register_divergence_overrides() -> None:
    """(Re)register the divergence overrides into the in-memory registry.

    The registry is seeded with these at module-load time (see
    ``override_registry``). This helper re-seeds after a
    :func:`~app.strategy_engine.translator.override_registry.clear_overrides`
    — e.g. inside test fixtures that reset registry state per test. The import
    is local to avoid an import cycle (``override_registry`` imports this
    module at load time to seed ``_OVERRIDES``).
    """
    from app.strategy_engine.translator.override_registry import register_override

    for slug, strategy_json in DIVERGENCE_OVERRIDES.items():
        register_override(slug, strategy_json)


__all__ = ["DIVERGENCE_OVERRIDES", "register_divergence_overrides"]
