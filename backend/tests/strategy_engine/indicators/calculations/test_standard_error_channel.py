"""Standard Error Channel — tests.

Locked variant: OLS regression line + bands using SEE
(divides by ``length - 2``). Distinct from raw-stdev channel.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.standard_error_channel import (
    standard_error_channel,
)


# ── Property tests ─────────────────────────────────────────────────────


def test_sec_returns_triple_of_three_lists() -> None:
    closes = [100.0 + i for i in range(30)]
    line, upper, lower = standard_error_channel(closes, length=20)
    assert len(line) == 30
    assert len(upper) == 30
    assert len(lower) == 30


def test_sec_warmup_is_none() -> None:
    closes = [100.0 + i for i in range(30)]
    line, upper, lower = standard_error_channel(closes, length=20)
    for i in range(19):
        assert line[i] is None
        assert upper[i] is None
        assert lower[i] is None


def test_sec_upper_ge_line_ge_lower() -> None:
    import random

    rng = random.Random(5)
    closes = [100.0 + rng.uniform(-5, 5) for _ in range(40)]
    line, upper, lower = standard_error_channel(closes, length=20)
    for i in range(19, 40):
        assert upper[i] >= line[i]
        assert line[i] >= lower[i]


# ── Hand-computed tests ────────────────────────────────────────────────


def test_sec_hand_computed_perfectly_linear() -> None:
    """Perfectly linear series ⇒ residuals all zero ⇒ SEE = 0 ⇒ bands = line.

    closes = [10, 11, 12, 13, 14], length=5, multiplier=2.
    x = [0,1,2,3,4], y_mean=12, x_mean=2
    b = sum((x-2)(y-12)) / sum((x-2)²) = 10 / 10 = 1.0
    a = 12 - 1.0*2 = 10
    y_hat = [10, 11, 12, 13, 14] — exact fit
    SEE = sqrt(0 / 3) = 0
    line[4] = 10 + 1.0*4 = 14
    upper = lower = 14
    """
    line, upper, lower = standard_error_channel(
        [10.0, 11.0, 12.0, 13.0, 14.0], length=5, multiplier=2.0
    )
    assert line[4] == pytest.approx(14.0, abs=1e-12)
    assert upper[4] == pytest.approx(14.0, abs=1e-12)
    assert lower[4] == pytest.approx(14.0, abs=1e-12)


def test_sec_hand_computed_mixed() -> None:
    """closes=[10, 12, 11, 14, 13], length=5, multiplier=2.

    x_mean=2, y_mean=12.
    b = sum((x-2)(y-12)) / 10
      = (-2)(-2) + (-1)(0) + (0)(-1) + (1)(2) + (2)(1)
      = 4 + 0 + 0 + 2 + 2 = 8
    b = 0.8
    a = 12 - 0.8*2 = 10.4

    y_hat = [10.4, 11.2, 12.0, 12.8, 13.6]
    residuals = [-0.4, 0.8, -1.0, 1.2, -0.6]
    sum sq = 0.16 + 0.64 + 1.0 + 1.44 + 0.36 = 3.6
    SEE = sqrt(3.6 / 3) = sqrt(1.2)

    line[4] = 10.4 + 0.8*4 = 13.6
    upper   = 13.6 + 2.0*sqrt(1.2)
    lower   = 13.6 - 2.0*sqrt(1.2)
    """
    line, upper, lower = standard_error_channel(
        [10.0, 12.0, 11.0, 14.0, 13.0], length=5, multiplier=2.0
    )
    see = math.sqrt(1.2)
    assert line[4] == pytest.approx(13.6, abs=1e-12)
    assert upper[4] == pytest.approx(13.6 + 2.0 * see, abs=1e-12)
    assert lower[4] == pytest.approx(13.6 - 2.0 * see, abs=1e-12)


# ── Reference test ─────────────────────────────────────────────────────


def test_sec_matches_explicit_recomputation() -> None:
    """Reference: explicit OLS + SEE recomputation."""
    import random

    rng = random.Random(91)
    n = 60
    length = 20
    multiplier = 2.0
    closes = [100.0 + rng.uniform(-5, 5) for _ in range(n)]

    line, upper, lower = standard_error_channel(closes, length=length, multiplier=multiplier)

    x_vals = list(range(length))
    x_mean = (length - 1) / 2.0
    x_var = sum((xi - x_mean) ** 2 for xi in x_vals)

    for t in range(length - 1, n):
        w = closes[t - length + 1 : t + 1]
        y_mean = sum(w) / length
        cov = sum((x_vals[i] - x_mean) * (w[i] - y_mean) for i in range(length))
        b = cov / x_var
        a = y_mean - b * x_mean
        y_hat = [a + b * x for x in x_vals]
        ssq = sum((w[i] - y_hat[i]) ** 2 for i in range(length))
        see = math.sqrt(ssq / (length - 2))
        expected_line = a + b * (length - 1)
        assert line[t] == pytest.approx(expected_line, abs=1e-9), f"line@{t}"
        assert upper[t] == pytest.approx(expected_line + multiplier * see, abs=1e-9), f"upper@{t}"
        assert lower[t] == pytest.approx(expected_line - multiplier * see, abs=1e-9), f"lower@{t}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_sec_empty_input() -> None:
    line, upper, lower = standard_error_channel([])
    assert (line, upper, lower) == ([], [], [])


def test_sec_length_greater_than_n_returns_all_none() -> None:
    line, upper, lower = standard_error_channel([1.0, 2.0, 3.0], length=10)
    assert line == [None, None, None]
    assert upper == [None, None, None]
    assert lower == [None, None, None]


def test_sec_length_less_than_three_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        standard_error_channel([1.0] * 10, length=2)
    with pytest.raises(ValueError, match="length"):
        standard_error_channel([1.0] * 10, length=1)


def test_sec_negative_multiplier_raises() -> None:
    with pytest.raises(ValueError, match="multiplier"):
        standard_error_channel([1.0] * 30, length=20, multiplier=-1.0)


def test_sec_constant_series_zero_see() -> None:
    """Constant series ⇒ b=0, line=mean, residuals=0, SEE=0."""
    line, upper, lower = standard_error_channel([5.0] * 10, length=5, multiplier=2.0)
    for i in range(4, 10):
        assert line[i] == pytest.approx(5.0, abs=1e-12)
        assert upper[i] == pytest.approx(5.0, abs=1e-12)
        assert lower[i] == pytest.approx(5.0, abs=1e-12)
