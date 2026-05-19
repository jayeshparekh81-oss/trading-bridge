"""Elder Ray Bull/Bear composite — tests.

elder_ray_bull_bear is a wrapper that calls both elder_ray_bull and
elder_ray_bear and returns a (bull, bear) tuple.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.elder_ray_bull_bear import (
    elder_ray_bull_bear,
)
from app.strategy_engine.indicators.calculations.elder_ray_bull import elder_ray_bull
from app.strategy_engine.indicators.calculations.elder_ray_bear import elder_ray_bear


def test_er_returns_tuple_matching_pair() -> None:
    """Composite output == (elder_ray_bull(...), elder_ray_bear(...))."""
    import random

    rng = random.Random(7)
    n = 30
    closes = [100.0 + rng.uniform(-2, 2) for _ in range(n)]
    highs = [c + abs(rng.uniform(0.1, 1.0)) for c in closes]
    lows = [c - abs(rng.uniform(0.1, 1.0)) for c in closes]

    out_bull, out_bear = elder_ray_bull_bear(highs, lows, closes, period=13)
    expected_bull = elder_ray_bull(highs, closes, period=13)
    expected_bear = elder_ray_bear(lows, closes, period=13)

    assert out_bull == expected_bull
    assert out_bear == expected_bear


def test_er_in_uptrend_bull_positive_bear_can_be_pos_or_neg() -> None:
    """Pure uptrend: bull_power > 0; bear_power undefined sign."""
    n = 30
    closes = [100.0 + i for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    bull, bear = elder_ray_bull_bear(highs, lows, closes, period=13)
    # Past warm-up, bull should be positive (high > EMA in uptrend)
    for i in range(13, n):
        if bull[i] is not None:
            assert bull[i] > 0


def test_er_empty_input() -> None:
    bull, bear = elder_ray_bull_bear([], [], [])
    assert bull == []
    assert bear == []


def test_er_invalid_period_raises() -> None:
    with pytest.raises(ValueError):
        elder_ray_bull_bear([1.0] * 20, [0.5] * 20, [0.7] * 20, period=0)


def test_er_constant_series_zero_pair() -> None:
    """Constant H/L/C ⇒ EMA = c ⇒ bull = h - c = 0; bear = l - c = 0."""
    n = 20
    highs = [10.0] * n
    lows = [10.0] * n
    closes = [10.0] * n
    bull, bear = elder_ray_bull_bear(highs, lows, closes, period=5)
    for i in range(4, n):
        assert bull[i] == pytest.approx(0.0, abs=1e-12)
        assert bear[i] == pytest.approx(0.0, abs=1e-12)
