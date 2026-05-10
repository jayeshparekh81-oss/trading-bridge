"""SMA calculation tests.

Test vectors are mathematical-property assertions (not canonical from a
named source) since SMA is unambiguous. The constant-series identity
``SMA([c]*n, k) == [None]*(k-1) + [c]*(n-k+1)`` is the strongest property
test we can write — it would fail under any rolling-sum bug.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.sma import sma


def test_sma_basic_window() -> None:
    """Hand-computed window: SMA([1..5], 3) = [None, None, 2, 3, 4]."""
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_period_one_is_identity() -> None:
    assert sma([1.5, 2.5, 3.5], 1) == [1.5, 2.5, 3.5]


def test_sma_constant_series() -> None:
    """SMA of constant series equals the constant for every defined position."""
    out = sma([7.0] * 10, 4)
    assert out[:3] == [None, None, None]
    assert out[3:] == [7.0] * 7


def test_sma_empty_input() -> None:
    assert sma([], 3) == []


def test_sma_period_greater_than_length_returns_empty() -> None:
    assert sma([1, 2], 5) == []


def test_sma_period_equal_to_length() -> None:
    """At ``period == len(values)`` we emit one defined SMA at the last position."""
    out = sma([1, 2, 3, 4], 4)
    assert out == [None, None, None, 2.5]


def test_sma_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        sma([1, 2, 3], 0)
    with pytest.raises(ValueError):
        sma([1, 2, 3], -1)


def test_sma_rejects_bool_period() -> None:
    """``True`` is an ``int`` in Python's type system, so mypy considers
    ``period=True`` valid; we still reject it at runtime to avoid
    surprising "everyone's a 1-period SMA" bugs.
    """
    with pytest.raises(ValueError):
        sma([1, 2, 3], True)


def test_sma_output_length_matches_input_length() -> None:
    values = list(range(20))
    out = sma(values, 5)
    assert len(out) == len(values)
