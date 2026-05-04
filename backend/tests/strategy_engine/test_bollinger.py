"""Bollinger Bands calculation tests."""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.bollinger_bands import bollinger_bands
from app.strategy_engine.indicators.calculations.sma import sma


def test_bollinger_constant_series_has_zero_band_width() -> None:
    """Constant series -> stdev = 0 -> upper == middle == lower."""
    values = [10.0] * 8
    upper, middle, lower = bollinger_bands(values, period=4, std_dev=2)
    for u, m, lo in zip(upper, middle, lower, strict=True):
        if m is None:
            assert u is None and lo is None
        else:
            assert u == m == lo == 10.0


def test_bollinger_middle_equals_sma() -> None:
    values = [float(i) for i in range(20)]
    _, middle, _ = bollinger_bands(values, period=5, std_dev=2)
    assert middle == sma(values, 5)


def test_bollinger_band_distance_matches_population_stdev() -> None:
    """Hand-verified: BB([1,2,3,4,5], 5, 2). Pop variance = 2.0; sigma = sqrt(2).

    Middle = 3.0; upper = 3 + 2*sqrt(2); lower = 3 - 2*sqrt(2).
    """
    upper, middle, lower = bollinger_bands([1, 2, 3, 4, 5], period=5, std_dev=2)
    assert middle[-1] == pytest.approx(3.0)
    expected_sigma = math.sqrt(2.0)
    assert upper[-1] == pytest.approx(3.0 + 2 * expected_sigma)
    assert lower[-1] == pytest.approx(3.0 - 2 * expected_sigma)


def test_bollinger_upper_always_above_lower_when_defined() -> None:
    values = [float(i) + (i % 5) for i in range(30)]
    upper, _, lower = bollinger_bands(values, period=5, std_dev=2)
    for u, lo in zip(upper, lower, strict=True):
        if u is None or lo is None:
            continue
        assert u >= lo


def test_bollinger_empty_input() -> None:
    assert bollinger_bands([], period=5) == ([], [], [])


def test_bollinger_period_greater_than_length_returns_empty() -> None:
    assert bollinger_bands([1, 2, 3], period=5) == ([], [], [])


def test_bollinger_rejects_non_positive_std_dev() -> None:
    with pytest.raises(ValueError):
        bollinger_bands([1.0] * 10, period=5, std_dev=0)
    with pytest.raises(ValueError):
        bollinger_bands([1.0] * 10, period=5, std_dev=-1)


def test_bollinger_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        bollinger_bands([1.0] * 10, period=0)
    with pytest.raises(ValueError):
        bollinger_bands([1.0] * 10, period=-3)
