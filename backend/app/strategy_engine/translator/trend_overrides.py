"""Founder overrides for the 3 trend templates (Queue PP / D2).

Queue BB classified ``supertrend-rider``, ``hull-ma-trend`` and
``triple-ema-crossover`` as FAIL_UNPARSEABLE: their seed ``config_json`` prose
uses visual/UI semantics ("supertrend flips to bullish", "hull colour flips
from red to green / sloping up") and a multi-bar window ("crosses above in the
last 2 bars") that the prose grammar cannot match. Queue BB's aggregate
decision 4 prescribed the fix directly: *rewrite the colour-flip / flip prose to
numeric primitives* (e.g. ``supertrend > close`` → bullish).

Same override-registry mechanism as the divergence overrides (Queue OO / C2):
these hand-written ``StrategyJSON`` dicts are seeded into the translator's
override registry, so ``translate_template`` returns them directly and the prose
parser is skipped. The required indicators (``supertrend`` / ``hull_ma`` / ``ema``)
are all ACTIVE and already dispatched in ``backtest/indicator_runner.py`` — no
engine changes. See ``docs/QUEUE_PP_TRANSLATOR_D2.md`` for design + sign-off.

Mapping (founder-approved, decision 3):
  * supertrend "flips to bullish (close > supertrend)" → ``close crossover
    supertrend_line``; "flips to bearish" → ``close crossunder supertrend_line``.
    The seed's SHORT side (``entry_short``/``exit_short``) is dropped — the
    translator + StrategyJSON are single-side (BUY) in this prototype, same as C2.
  * hull "colour flips to green (sloping up) AND close > hull" → ``close crossover
    hull_ma_21``; "colour flips back to red" → ``close crossunder hull_ma_21``.
  * triple-ema "ema_8 > ema_21 > ema_55 AND ema_8 crosses above ema_21 in the last
    2 bars" → ``ema_8 > ema_21`` ∧ ``ema_21 > ema_55`` ∧ ``ema_8 crossover ema_21``
    (single-bar — the 2-bar window has no schema primitive).

``close`` is declared as ``ema(period=2)`` — the near-raw-price proxy the prose
parser auto-injects for bare ``close`` references (and reused by C2). EMA(1) is
rejected by the registry's ``period >= 2`` rule; EMA(2) is the minimum legal
smoothing and is within the comparison tolerance these crossovers use.
"""

from __future__ import annotations

from typing import Any, Final

_EXECUTION: Final[dict[str, Any]] = {
    "mode": "backtest",
    "order_type": "MARKET",
    "product_type": "INTRADAY",
}

#: ``close`` pseudo-indicator (EMA-2 ≈ raw price), shared by all three templates.
_CLOSE_PSEUDO: Final[dict[str, Any]] = {
    "id": "close",
    "type": "ema",
    "params": {"period": 2, "source": "close"},
}


def _time_gate(start: str, end: str) -> dict[str, Any]:
    return {"type": "time", "op": "between", "value": start, "end": end}


_SUPERTREND_RIDER: Final[dict[str, Any]] = {
    "id": "template:supertrend-rider",
    "name": "Supertrend Rider",
    "mode": "beginner",
    "version": 1,
    "indicators": [
        # Primary output of `supertrend` is the active band level (`line`).
        {"id": "supertrend_10_3", "type": "supertrend", "params": {"period": 10, "multiplier": 3.0}},
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            # Flip to bullish = close crossing above the supertrend band.
            {"type": "indicator", "left": "close", "op": "crossover", "right": "supertrend_10_3"},
            _time_gate("09:15", "15:15"),
        ],
    },
    "exit": {
        "target_percent": 5.0,
        "stop_loss_percent": 2.0,
        "square_off_time": "15:15",
        "indicator_exits": [
            # Flip to bearish = close crossing below the band.
            {"type": "indicator", "left": "close", "op": "crossunder", "right": "supertrend_10_3"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_HULL_MA_TREND: Final[dict[str, Any]] = {
    "id": "template:hull-ma-trend",
    "name": "Hull MA Trend",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {"id": "hull_ma_21", "type": "hull_ma", "params": {"period": 21, "source": "close"}},
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            # Colour flips to green (bullish) = close crossing above the hull line.
            {"type": "indicator", "left": "close", "op": "crossover", "right": "hull_ma_21"},
            _time_gate("09:30", "15:00"),
        ],
    },
    "exit": {
        "target_percent": 4.0,
        "stop_loss_percent": 1.5,
        "square_off_time": "15:00",
        "indicator_exits": [
            # Colour flips back to red = close crossing below the hull line.
            {"type": "indicator", "left": "close", "op": "crossunder", "right": "hull_ma_21"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


_TRIPLE_EMA_CROSSOVER: Final[dict[str, Any]] = {
    "id": "template:triple-ema-crossover",
    "name": "Triple EMA Crossover",
    "mode": "intermediate",
    "version": 1,
    "indicators": [
        {"id": "ema_8", "type": "ema", "params": {"period": 8, "source": "close"}},
        {"id": "ema_21", "type": "ema", "params": {"period": 21, "source": "close"}},
        {"id": "ema_55", "type": "ema", "params": {"period": 55, "source": "close"}},
        _CLOSE_PSEUDO,
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            # Stacked-bullish alignment + the fast/medium crossover trigger.
            {"type": "indicator", "left": "ema_8", "op": ">", "right": "ema_21"},
            {"type": "indicator", "left": "ema_21", "op": ">", "right": "ema_55"},
            {"type": "indicator", "left": "ema_8", "op": "crossover", "right": "ema_21"},
            _time_gate("09:30", "15:00"),
        ],
    },
    "exit": {
        "target_percent": 4.5,
        "stop_loss_percent": 1.5,
        "square_off_time": "15:00",
        "indicator_exits": [
            {"type": "indicator", "left": "ema_8", "op": "crossunder", "right": "ema_21"},
            {"type": "indicator", "left": "close", "op": "<", "right": "ema_55"},
        ],
    },
    "risk": {},
    "execution": _EXECUTION,
}


#: Slug → hand-written StrategyJSON dict. Consumed by the override registry.
TREND_OVERRIDES: Final[dict[str, dict[str, Any]]] = {
    "supertrend-rider": _SUPERTREND_RIDER,
    "hull-ma-trend": _HULL_MA_TREND,
    "triple-ema-crossover": _TRIPLE_EMA_CROSSOVER,
}


def register_trend_overrides() -> None:
    """(Re)register the trend overrides into the in-memory registry.

    The registry is seeded with these at module-load time (see
    ``override_registry``). This re-seeds after a
    :func:`~app.strategy_engine.translator.override_registry.clear_overrides`
    (e.g. test fixtures that reset registry state). The import is local to avoid
    an import cycle — ``override_registry`` imports this module at load time.
    """
    from app.strategy_engine.translator.override_registry import register_override

    for slug, strategy_json in TREND_OVERRIDES.items():
        register_override(slug, strategy_json)


__all__ = ["TREND_OVERRIDES", "register_trend_overrides"]
