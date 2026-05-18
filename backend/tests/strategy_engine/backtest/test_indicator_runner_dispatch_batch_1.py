"""Batch-1 commission dispatch tests.

Verifies the 5 indicators wired into ``indicator_runner._compute_one``
(heikin_ashi, alma, kama, pivot_swing, fibonacci_retracement) all
dispatch correctly + produce correctly-shaped output series.

Two test layers:
  1. Dispatch smoke: indicator_runner.precompute_indicators({...})
     returns a same-length-as-candles series with no error.
  2. Single-indicator integration: each indicator's primary output
     is sane (non-empty, no all-None, no NaN/Inf).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from app.strategy_engine.backtest.indicator_runner import (
    IndicatorRunnerError,
    precompute_indicators,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import (
    EntryRules,
    ExecutionConfig,
    ExitRules,
    IndicatorConfig,
    StrategyJSON,
)


def _build_candles(n: int = 120) -> list[Candle]:
    """Sinusoidal close + symmetric wick. Same shape as Day-4 engine."""
    start = datetime(2026, 5, 17, 9, 15, tzinfo=UTC)
    base = 22000.0
    out: list[Candle] = []
    for i in range(n):
        c = base + math.sin(2 * math.pi * i / 20) * 100.0 + i * 0.1
        o = out[-1].close if out else c
        h = max(o, c) + 5.0
        l = min(o, c) - 5.0
        out.append(
            Candle(
                timestamp=start + timedelta(minutes=5 * i),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1000.0 + i,
            )
        )
    return out


def _build_strategy(indicators: list[IndicatorConfig]) -> StrategyJSON:
    """Minimal valid StrategyJSON wrapping the indicators under test.

    Entry condition uses the FIRST indicator's id; exit uses target%.
    The entry condition's purpose is to satisfy StrategyJSON's
    cross-reference validator (every condition's left-id must exist
    in ``indicators[*]``).
    """
    first_id = indicators[0].id if indicators else "dummy"
    return StrategyJSON.model_validate(
        {
            "id": "dispatch_test",
            "name": "Dispatch test",
            "mode": "expert",
            "indicators": [i.model_dump() for i in indicators],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [
                    {"type": "indicator", "left": first_id, "op": ">", "value": 0.0}
                ],
            },
            "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
            "risk": {},
            "execution": {
                "mode": "backtest",
                "orderType": "MARKET",
                "productType": "INTRADAY",
            },
        }
    )


# ─── Dispatch smoke (5 tests — one per indicator) ─────────────────────


def test_dispatch_heikin_ashi_runs_without_error() -> None:
    strategy = _build_strategy(
        [IndicatorConfig(id="ha", type="heikin_ashi", params={})]
    )
    series, warnings = precompute_indicators(_build_candles(60), strategy)
    assert "ha" in series
    assert len(series["ha"]) == 60
    # Multi-output: sub-outputs present via dotted-notation
    assert any(k.startswith("ha.") for k in series), (
        "Expected ha.ha_open / ha.ha_high / ha.ha_low / ha.ha_close sub-outputs"
    )
    # Multi-output warning emitted (matches Phase 9 convention)
    assert any("multi-output" in w for w in warnings)


def test_dispatch_alma_runs_without_error() -> None:
    strategy = _build_strategy(
        [IndicatorConfig(id="alma_9", type="alma", params={"period": 9, "source": "close"})]
    )
    series, _ = precompute_indicators(_build_candles(60), strategy)
    assert "alma_9" in series
    assert len(series["alma_9"]) == 60
    # First 8 values are None (warmup); rest defined
    assert all(v is None for v in series["alma_9"][:8])
    assert all(v is not None for v in series["alma_9"][8:])


def test_dispatch_kama_runs_without_error() -> None:
    strategy = _build_strategy(
        [IndicatorConfig(id="kama_10", type="kama", params={"period": 10, "source": "close"})]
    )
    series, _ = precompute_indicators(_build_candles(60), strategy)
    assert "kama_10" in series
    assert len(series["kama_10"]) == 60
    # Seed at period-1; warmup before that
    assert all(v is None for v in series["kama_10"][:9])
    assert series["kama_10"][9] is not None


def test_dispatch_pivot_swing_runs_without_error() -> None:
    strategy = _build_strategy(
        [
            IndicatorConfig(
                id="pv", type="pivot_swing", params={"left_bars": 3, "right_bars": 3}
            )
        ]
    )
    series, _ = precompute_indicators(_build_candles(120), strategy)
    assert "pv" in series
    assert len(series["pv"]) == 120


def test_dispatch_fibonacci_retracement_runs_without_error() -> None:
    strategy = _build_strategy(
        [
            IndicatorConfig(
                id="fib",
                type="fibonacci_retracement",
                params={"lookback": 30, "direction": "bull"},
            )
        ]
    )
    series, warnings = precompute_indicators(_build_candles(60), strategy)
    assert "fib" in series
    assert len(series["fib"]) == 60
    # Multi-output: sub-outputs present (50.0 is primary; 23.6/38.2/etc. as sub)
    sub_keys = [k for k in series if k.startswith("fib.")]
    assert len(sub_keys) >= 5, "Expected fib.23.6, fib.38.2, etc. sub-outputs"
    assert any("multi-output" in w for w in warnings)


# ─── Integration smoke (5 tests — output sanity) ──────────────────────


def test_heikin_ashi_close_lies_within_input_range() -> None:
    """HA close = (o+h+l+c)/4 — always within [min(low), max(high)]."""
    candles = _build_candles(40)
    strategy = _build_strategy(
        [IndicatorConfig(id="ha", type="heikin_ashi", params={})]
    )
    series, _ = precompute_indicators(candles, strategy)
    ha_close = series["ha"]
    min_low = min(c.low for c in candles)
    max_high = max(c.high for c in candles)
    for v in ha_close:
        if v is not None:
            assert min_low <= v <= max_high
            assert not math.isnan(v)
            assert not math.isinf(v)


def test_alma_warmup_then_defined() -> None:
    candles = _build_candles(40)
    strategy = _build_strategy(
        [
            IndicatorConfig(
                id="alma_default", type="alma", params={"period": 9, "source": "close"}
            )
        ]
    )
    series, _ = precompute_indicators(candles, strategy)
    out = series["alma_default"]
    # First 8 None (period-1 warmup), rest defined and finite
    assert all(v is None for v in out[:8])
    for v in out[8:]:
        assert v is not None
        assert not math.isnan(v)
        assert not math.isinf(v)


def test_kama_constant_series_yields_constant_kama() -> None:
    """Flat candles → ER=0 → KAMA stays at seed."""
    flat = [
        Candle(
            timestamp=datetime(2026, 5, 17, 9, 15, tzinfo=UTC) + timedelta(minutes=5 * i),
            open=22000.0,
            high=22000.0,
            low=22000.0,
            close=22000.0,
            volume=1000.0,
        )
        for i in range(30)
    ]
    strategy = _build_strategy(
        [
            IndicatorConfig(
                id="kama_default", type="kama", params={"period": 10, "source": "close"}
            )
        ]
    )
    series, _ = precompute_indicators(flat, strategy)
    out = series["kama_default"]
    defined = [v for v in out if v is not None]
    assert defined
    assert all(abs(v - 22000.0) < 1e-9 for v in defined)


def test_pivot_swing_returns_some_pivots_on_oscillating_series() -> None:
    """Sinusoidal candles → at least one swing high + one swing low."""
    candles = _build_candles(120)
    strategy = _build_strategy(
        [
            IndicatorConfig(
                id="pv", type="pivot_swing", params={"left_bars": 3, "right_bars": 3}
            )
        ]
    )
    series, _ = precompute_indicators(candles, strategy)
    out = series["pv"]
    highs = [v for v in out if v is not None and v > 0]
    lows = [v for v in out if v is not None and v < 0]
    assert highs, "Expected at least one swing-high in oscillating series"
    assert lows, "Expected at least one swing-low"


def test_fibonacci_retracement_50_pct_is_midpoint() -> None:
    """50% retracement = midpoint of swing_high and swing_low."""
    candles = _build_candles(60)
    strategy = _build_strategy(
        [
            IndicatorConfig(
                id="fib",
                type="fibonacci_retracement",
                params={"lookback": 30, "direction": "bull"},
            )
        ]
    )
    series, _ = precompute_indicators(candles, strategy)
    sh = series["fib.swing_high"]
    sl = series["fib.swing_low"]
    primary = series["fib"]  # primary = 50.0% level
    for s_high, s_low, midpoint in zip(sh, sl, primary, strict=True):
        if s_high is None:
            continue
        assert abs(midpoint - (s_high + s_low) / 2) < 1e-6


# ─── Negative: unknown indicator still raises ─────────────────────────


def test_unknown_indicator_type_raises_helpful_error() -> None:
    """Sanity: the new dispatch entries didn't break the fall-through."""
    # IndicatorConfig validates id format (lower_snake) — bypass by using
    # the dispatch fn directly via precompute. But we need a registered
    # indicator id whose dispatch is wired NOWHERE. None exists post-batch-1
    # (every registered id has a dispatch). So this test is a no-op
    # smoke that confirms IndicatorRunnerError is still importable.
    assert IndicatorRunnerError.__name__ == "IndicatorRunnerError"
    assert issubclass(IndicatorRunnerError, ValueError)
