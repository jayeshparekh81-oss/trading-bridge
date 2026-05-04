"""ATR calculation tests.

ATR is unambiguous given Wilder's TR + recursive smoothing definition.
We assert against hand-computed values for a 5-bar fixture and check
edge cases (mismatched input lengths, period > n, etc.).
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.atr import atr
from tests.strategy_engine.fixtures.ohlcv_sample import CLOSES, HIGHS, LOWS


def test_atr_period_two_known_values() -> None:
    """Hand-computed for the fixture (period=2):

    TR sequence:
        TR[0] = 10 - 9   = 1.0   (no prior close)
        TR[1] = max(11-9.5, |11-9.5|, |9.5-9.5|) = 1.5
        TR[2] = max(12.5-11, |12.5-11|, |11-11|) = 1.5
        TR[3] = max(12-10.5, |12-12|, |10.5-12|) = 1.5
        TR[4] = max(13-12, |13-11|, |12-11|) = 2.0

    Seed at idx 1: mean(TR[0..1]) = 1.25
    idx 2: (1.25*1 + 1.5)/2  = 1.375
    idx 3: (1.375*1 + 1.5)/2 = 1.4375
    idx 4: (1.4375*1 + 2.0)/2 = 1.71875
    """
    out = atr(HIGHS, LOWS, CLOSES, period=2)
    assert out == [
        None,
        pytest.approx(1.25),
        pytest.approx(1.375),
        pytest.approx(1.4375),
        pytest.approx(1.71875),
    ]


def test_atr_warmup_at_period_minus_one() -> None:
    out = atr(HIGHS, LOWS, CLOSES, period=3)
    assert out[0] is None
    assert out[1] is None
    assert out[2] is not None


def test_atr_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        atr([1.0, 2.0], [1.0], [1.0, 2.0], period=2)


def test_atr_empty_input() -> None:
    assert atr([], [], [], period=14) == []


def test_atr_period_greater_than_length_returns_empty() -> None:
    assert atr([1.0, 2.0], [0.5, 1.5], [0.7, 1.2], period=14) == []


def test_atr_constant_bar_yields_constant_atr() -> None:
    """Every bar is the same OHLC -> TR = high - low constant -> ATR same."""
    n = 10
    h = [100.0] * n
    lo = [99.0] * n
    c = [99.5] * n
    out = atr(h, lo, c, period=4)
    assert all(v is None for v in out[:3])
    for v in out[3:]:
        assert v == pytest.approx(1.0)


def test_atr_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        atr(HIGHS, LOWS, CLOSES, period=0)
