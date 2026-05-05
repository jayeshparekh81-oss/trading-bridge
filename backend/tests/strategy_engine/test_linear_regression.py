"""Linear Regression (LSMA) calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.linear_regression import (
    linear_regression,
)


def test_linreg_perfect_line_recovers_endpoint() -> None:
    """y = 2x + 3 over the window → LSMA at last bar equals 2*(period-1)+3."""
    period = 5
    values = [2.0 * i + 3.0 for i in range(period)]
    out = linear_regression(values, period=period)
    assert out[period - 1] == 2.0 * (period - 1) + 3.0


def test_linreg_constant_series_is_constant() -> None:
    """Slope = 0 → LSMA = mean = constant."""
    out = linear_regression([7.0] * 20, period=14)
    for v in out[13:]:
        assert v == 7.0


def test_linreg_seed_index_and_length_parity() -> None:
    out = linear_regression([float(i) for i in range(20)], period=14)
    assert len(out) == 20
    assert out[12] is None
    assert out[13] is not None


def test_linreg_uptrend_endpoint_above_window_mean() -> None:
    """For a rising window, the LSMA endpoint exceeds the simple mean."""
    period = 10
    values = [float(i) for i in range(period * 2)]
    out = linear_regression(values, period=period)
    sma_last = sum(values[-period:]) / period
    last = out[-1]
    assert last is not None
    assert last > sma_last


def test_linreg_short_input_returns_empty() -> None:
    assert linear_regression([1.0, 2.0], period=5) == []


def test_linreg_empty_input() -> None:
    assert linear_regression([], period=5) == []


def test_linreg_rejects_period_below_two() -> None:
    with pytest.raises(ValueError):
        linear_regression([1.0, 2.0, 3.0], period=1)
    with pytest.raises(ValueError):
        linear_regression([1.0, 2.0, 3.0], period=0)
