"""Founder overrides for the active candle-pattern templates (Queue QQ / E2).

Queue BB classified ``doji-reversal`` and ``engulfing-candle-reversal`` as
FAIL_UNPARSEABLE: their seed prose describes candlestick patterns in free text
("previous bar doji (body < 10% of range)", "current bar bullish engulfing
pattern (...)") that the prose grammar cannot match. The StrategyJSON schema DOES
model these via :class:`~app.strategy_engine.schema.strategy.CandleCondition`
(``doji`` / ``engulfing`` / ``bullish`` / ...), and the entry engine evaluates
them (``engines/candle_pattern.py``) — so the fix is a hand-written override that
uses ``CandleCondition`` + the existing ``rsi`` / ``ema`` indicators.

Same override-registry mechanism as the divergence (C2) + trend (D2) overrides.
No engine changes.

Scope (founder decision 3): only the two ACTIVE templates. ``hammer-hanging-man-
pattern`` is excluded — it is ``is_active=False`` (the clone path 409s before
translation) and references ``auto_support_resistance_20``, which is not a
registered indicator.

Mapping (founder-approved, decision 4):
  * doji "previous bar doji (body<10%)" → ``CandleCondition(DOJI)`` on the current
    bar (the engine's doji is single-bar; the 2-bar confirm + "closes above doji's
    high" prior-bar reference are dropped — no primitive). "price extended below
    ema_50 in last 5 bars" → ``close < ema_50``. Exit "close < doji's low OR
    rsi_14 > 60" → ``rsi_14 > 60`` (+ SL/TP/square-off; the doji-low ref is dropped).
  * engulfing "bullish engulfing pattern" → ``CandleCondition(ENGULFING)`` ∧
    ``CandleCondition(BULLISH)``: the engine's ENGULFING is direction-agnostic
    (covers prior body, opposite directions), so ∧ BULLISH (current close>open)
    pins it to a *bullish* engulfing of a prior bearish bar. Exit "bearish
    engulfing OR close < entry_low" is not expressible as an ``IndicatorCondition``
    (the exit engine ignores candle/price conditions in ``indicator_exits`` in
    Phase 2), so the engulfing template exits on SL/TP/square-off only.

``close`` is declared as ``ema(period=2)`` ≈ raw price (parser convention, reused
in C2/D2). ``CandleCondition`` reads raw OHLC and references no indicator id.
"""

from __future__ import annotations

from typing import Any, Final

_EXECUTION: Final[dict[str, Any]] = {
    "mode": "backtest",
    "order_type": "MARKET",
    "product_type": "INTRADAY",
}

_CLOSE_PSEUDO: Final[dict[str, Any]] = {
    "id": "close",
    "type": "ema",
    "params": {"period": 2, "source": "close"},
}


def _time_gate(start: str, end: str) -> dict[str, Any]:
    return {"type": "time", "op": "between", "value": start, "end": end}


_DOJI_REVERSAL: Final[dict[str, Any]] = {
    "id": "template:doji-reversal",
    "name": "Doji Reversal",
    "mode": "beginner",
    "version": 1,
    "indicators": [
        {"id": "ema_50", "type": "ema", "params": {"period": 50, "source": "close"}},
        {"id": "rsi_14", "type": "rsi", "params": {"period": 14, "source": "close"}},
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "candle", "pattern": "doji"},
            # "extended below ema_50 (downtrend)".
            {"type": "indicator", "left": "close", "op": "<", "right": "ema_50"},
            # Oversold.
            {"type": "indicator", "left": "rsi_14", "op": "<", "value": 35.0},
            _time_gate("09:30", "15:00"),
        ],
    },
    "exit": {
        "target_percent": 2.5,
        "stop_loss_percent": 1.0,
        "square_off_time": "15:00",
        "indicator_exits": [
            # "mean-reversion complete".
            {"type": "indicator", "left": "rsi_14", "op": ">", "value": 60.0},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_ENGULFING_CANDLE_REVERSAL: Final[dict[str, Any]] = {
    "id": "template:engulfing-candle-reversal",
    "name": "Engulfing Candle Reversal",
    "mode": "beginner",
    "version": 1,
    # Trend filter relaxed OFF the entry (founder decision 4, same rationale as
    # C2's obv-divergence): a bullish engulfing reversal is an oversold-bottom
    # pattern, so close sits BELOW the lagging 50-EMA at the signal — strict
    # `close > ema_50` yields ZERO trades. The seed's "OR within 2% of ema_50"
    # was already a loose band with no schema primitive. ema_50/close are unused
    # once dropped, so they are not declared.
    "indicators": [
        {"id": "rsi_14", "type": "rsi", "params": {"period": 14, "source": "close"}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            # Bullish engulfing = engulfing (direction-agnostic) ∧ current bar bullish.
            {"type": "candle", "pattern": "engulfing"},
            {"type": "candle", "pattern": "bullish"},
            {"type": "indicator", "left": "rsi_14", "op": "<", "value": 40.0},
            _time_gate("09:30", "15:00"),
        ],
    },
    "exit": {
        # Seed exit ("bearish engulfing OR close < entry_low") is a candle/price
        # pattern that the Phase-2 exit engine does not evaluate; exit on risk
        # bands + square-off.
        "target_percent": 4.0,
        "stop_loss_percent": 1.5,
        "square_off_time": "15:00",
        "indicator_exits": [],
    },
    "risk": {},
    "execution": _EXECUTION,
}


#: Slug → hand-written StrategyJSON dict. Consumed by the override registry.
CANDLE_OVERRIDES: Final[dict[str, dict[str, Any]]] = {
    "doji-reversal": _DOJI_REVERSAL,
    "engulfing-candle-reversal": _ENGULFING_CANDLE_REVERSAL,
}


def register_candle_overrides() -> None:
    """(Re)register the candle overrides into the in-memory registry.

    Seeded at module-load (see ``override_registry``); this re-seeds after a
    :func:`~app.strategy_engine.translator.override_registry.clear_overrides`
    (test fixtures). Local import avoids an import cycle.
    """
    from app.strategy_engine.translator.override_registry import register_override

    for slug, strategy_json in CANDLE_OVERRIDES.items():
        register_override(slug, strategy_json)


__all__ = ["CANDLE_OVERRIDES", "register_candle_overrides"]
