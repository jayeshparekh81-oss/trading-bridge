"""WMA calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.wma import wma


def test_wma_constant_series_is_constant() -> None:
    out = wma([4.0] * 6, 3)
    assert out[:2] == [None, None]
    assert out[2:] == [4.0] * 4


def test_wma_known_window() -> None:
    """WMA([1,2,3], 3) = (1*1 + 2*2 + 3*3) / (1+2+3) = 14 / 6 ~ 2.333..."""
    out = wma([1, 2, 3], 3)
    assert out[0] is None
    assert out[1] is None
    assert out[2] == pytest.approx(14 / 6)


def test_wma_period_one_is_identity() -> None:
    assert wma([1.5, 2.5, 3.5], 1) == [1.5, 2.5, 3.5]


def test_wma_more_recent_values_weigh_more() -> None:
    """For a ramp series, WMA > SMA at every defined index — recency bias."""
    from app.strategy_engine.indicators.calculations.sma import sma

    values = [float(i) for i in range(1, 11)]
    sma_out = sma(values, 4)
    wma_out = wma(values, 4)
    for s, w in zip(sma_out, wma_out, strict=True):
        if s is None or w is None:
            continue
        assert w >= s


def test_wma_empty_input() -> None:
    assert wma([], 3) == []


def test_wma_period_greater_than_length_returns_empty() -> None:
    assert wma([1, 2], 5) == []


def test_wma_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        wma([1, 2, 3], 0)
    with pytest.raises(ValueError):
        wma([1, 2, 3], -1)
