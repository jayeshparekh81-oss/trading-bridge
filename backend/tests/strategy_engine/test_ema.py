"""EMA calculation tests.

Test convention: SMA-seeded EMA — TradingView ``ta.ema`` parity.
At index ``period - 1`` the value is the simple mean of the first
``period`` inputs; from there on the standard ``alpha = 2 / (period + 1)``
recursion takes over.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.ema import ema


def test_ema_constant_series_is_constant() -> None:
    """EMA of a constant series equals the constant once warmed up.

    Property test: if every ``values[i] == c`` then the SMA seed = c and
    every recursive update stays at c regardless of alpha.
    """
    out = ema([5.0] * 10, 4)
    assert out[:3] == [None, None, None]
    assert out[3:] == [5.0] * 7


def test_ema_seed_is_sma_at_first_defined_position() -> None:
    """At index ``period - 1`` EMA must equal SMA of the first ``period`` values."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = ema(values, 3)
    assert out[2] == sum(values[:3]) / 3  # = 2.0


def test_ema_recursion_known_step() -> None:
    """Hand-computed: alpha = 2/4 = 0.5; seed at idx 2 = (1+2+3)/3 = 2.0;
    next EMA = 0.5*4 + 0.5*2.0 = 3.0; next = 0.5*5 + 0.5*3.0 = 4.0.
    """
    out = ema([1, 2, 3, 4, 5], 3)
    assert out == [None, None, 2.0, 3.0, 4.0]


def test_ema_period_one_is_identity() -> None:
    """alpha = 2/2 = 1, seed = values[0]; recursion just copies."""
    assert ema([1.5, 2.5, 3.5], 1) == [1.5, 2.5, 3.5]


def test_ema_reacts_faster_than_sma_to_a_step() -> None:
    """A step-up at the end should be reflected more by EMA than SMA.

    With period=3 and a sudden jump at position 5, EMA's alpha=0.5 weights
    the new value at 50%, while SMA only mixes 1/3 of it.
    """
    from app.strategy_engine.indicators.calculations.sma import sma

    # Three flat bars then a sudden jump.
    values = [10.0, 10.0, 10.0, 10.0, 10.0, 100.0]
    ema_out = ema(values, 3)
    sma_out = sma(values, 3)
    assert ema_out[-1] is not None and sma_out[-1] is not None
    assert ema_out[-1] > sma_out[-1]


def test_ema_empty_input() -> None:
    assert ema([], 3) == []


def test_ema_period_greater_than_length_returns_empty() -> None:
    assert ema([1, 2], 5) == []


def test_ema_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        ema([1, 2, 3], 0)
    with pytest.raises(ValueError):
        ema([1, 2, 3], -3)
