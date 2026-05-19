"""Standard Deviation calculation tests.

Test convention: TradingView ``ta.stdev`` parity — POPULATION variance
(divisor ``period``), not sample variance. The first defined position
is at index ``period - 1``; positions before that are ``None``.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.standard_deviation import (
    standard_deviation,
)


# ── Property test ──────────────────────────────────────────────────────


def test_standard_deviation_constant_series_is_zero() -> None:
    """Stdev of a constant series equals zero at every defined position."""
    out = standard_deviation([5.0] * 10, period=4)
    assert out[:3] == [None, None, None]
    assert out[3:] == [0.0] * 7


def test_standard_deviation_output_length_matches_input() -> None:
    """Output length equals input length; warm-up is None-filled."""
    out = standard_deviation([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], period=3)
    assert len(out) == 6
    assert out[0] is None
    assert out[1] is None
    # remaining values are non-None floats
    for v in out[2:]:
        assert isinstance(v, float)


# ── Hand-computed test ─────────────────────────────────────────────────


def test_standard_deviation_hand_computed_period_3() -> None:
    """Hand-computed for values=[1,2,3,4,5], period=3.

    Each window of 3 consecutive integers has values offset by 1:
        window [1,2,3]: mean=2, var=((1-2)²+(2-2)²+(3-2)²)/3 = 2/3, std=√(2/3)
        window [2,3,4]: mean=3, var=2/3, std=√(2/3)
        window [3,4,5]: mean=4, var=2/3, std=√(2/3)
    Expected: [None, None, √(2/3), √(2/3), √(2/3)]
    """
    expected_std = math.sqrt(2.0 / 3.0)
    out = standard_deviation([1, 2, 3, 4, 5], period=3)
    assert out[0] is None
    assert out[1] is None
    assert out[2] == pytest.approx(expected_std, abs=1e-12)
    assert out[3] == pytest.approx(expected_std, abs=1e-12)
    assert out[4] == pytest.approx(expected_std, abs=1e-12)


def test_standard_deviation_hand_computed_population_not_sample() -> None:
    """Verify divisor is N (population), not N-1 (sample).

    For values=[2,4,4,4,5,5,7,9] (classic textbook stdev example),
    period=8: mean=5; squared-deviations sum = 9+1+1+1+0+0+4+16 = 32;
    population var = 32/8 = 4; population std = 2.0
    Sample std (Bessel-corrected) would be √(32/7) ≈ 2.138, NOT 2.0.
    """
    out = standard_deviation([2, 4, 4, 4, 5, 5, 7, 9], period=8)
    assert out[7] == pytest.approx(2.0, abs=1e-12)


# ── Reference test (no talib; use numpy/statistics as reference) ───────


def test_standard_deviation_matches_statistics_pstdev() -> None:
    """Compare against Python stdlib statistics.pstdev for many windows.

    statistics.pstdev computes population standard deviation, matching
    TradingView's ta.stdev and our implementation.
    """
    import statistics
    import random

    rng = random.Random(42)
    values = [rng.uniform(-100, 100) for _ in range(50)]
    period = 14
    out = standard_deviation(values, period=period)

    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        expected = statistics.pstdev(window)
        assert out[i] == pytest.approx(expected, abs=1e-10), (
            f"Mismatch at i={i}: got {out[i]}, expected {expected}"
        )


# ── Edge case tests ────────────────────────────────────────────────────


def test_standard_deviation_empty_input() -> None:
    assert standard_deviation([], period=14) == []


def test_standard_deviation_period_greater_than_length() -> None:
    assert standard_deviation([1.0, 2.0, 3.0], period=10) == []


def test_standard_deviation_period_one_is_always_zero() -> None:
    """Period 1 ⇒ single-value window ⇒ variance = 0 ⇒ std = 0."""
    out = standard_deviation([1.5, 2.5, 3.5, 4.5], period=1)
    assert out == [0.0, 0.0, 0.0, 0.0]


def test_standard_deviation_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="period"):
        standard_deviation([1.0, 2.0, 3.0], period=0)
    with pytest.raises(ValueError, match="period"):
        standard_deviation([1.0, 2.0, 3.0], period=-5)


def test_standard_deviation_all_zeros() -> None:
    out = standard_deviation([0.0] * 10, period=5)
    assert out[:4] == [None] * 4
    assert out[4:] == [0.0] * 6


def test_standard_deviation_large_numbers_no_catastrophic_cancellation() -> None:
    """Very large numbers should not produce negative variance via cancellation.

    The implementation guards with ``if var < 0.0: var = 0.0`` for this case.
    """
    # All same large value — true variance is 0; rolling-sum approach
    # could produce tiny negative via floating-point cancellation.
    out = standard_deviation([1e9] * 20, period=14)
    for v in out[13:]:
        assert v == 0.0
