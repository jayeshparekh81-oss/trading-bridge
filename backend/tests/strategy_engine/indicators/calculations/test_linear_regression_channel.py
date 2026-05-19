"""Linear Regression Channel — tests.

Locked variant: regression line + RAW stdev bands (divides by n, NOT
n-2 like SEE). Distinct from standard_error_channel.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.linear_regression_channel import (
    linear_regression_channel,
)
from app.strategy_engine.indicators.calculations.standard_error_channel import (
    standard_error_channel,
)


def test_lrc_returns_triple() -> None:
    closes = [100.0 + i for i in range(30)]
    line, upper, lower = linear_regression_channel(closes, length=20)
    assert len(line) == 30
    assert len(upper) == 30
    assert len(lower) == 30


def test_lrc_perfectly_linear_zero_bands() -> None:
    """Perfectly linear closes ⇒ residuals = 0 ⇒ bands = line."""
    closes = [10.0, 11.0, 12.0, 13.0, 14.0]
    line, upper, lower = linear_regression_channel(closes, length=5, multiplier=2.0)
    assert line[4] == pytest.approx(14.0, abs=1e-12)
    assert upper[4] == pytest.approx(14.0, abs=1e-12)
    assert lower[4] == pytest.approx(14.0, abs=1e-12)


def test_lrc_uses_raw_stdev_not_see() -> None:
    """Verify LRC bands are NARROWER than SEC bands by the factor
    sqrt((n-2)/n).

    For closes=[10,12,11,14,13], length=5:
        residuals sum-of-squares = 3.6 (verified in test_sec hand-computed)
        SEC SEE = sqrt(3.6 / 3) = sqrt(1.2)
        LRC raw_std = sqrt(3.6 / 5) = sqrt(0.72)
        ratio = sqrt(0.72/1.2) = sqrt(0.6) = sqrt(3/5)
    """
    closes = [10.0, 12.0, 11.0, 14.0, 13.0]
    lrc_line, lrc_upper, _ = linear_regression_channel(closes, length=5, multiplier=2.0)
    sec_line, sec_upper, _ = standard_error_channel(closes, length=5, multiplier=2.0)

    assert lrc_line[4] == pytest.approx(sec_line[4], abs=1e-12)
    # LRC upper - line should be narrower than SEC upper - line
    lrc_width = lrc_upper[4] - lrc_line[4]
    sec_width = sec_upper[4] - sec_line[4]
    assert lrc_width < sec_width

    # Specific check: lrc_width = 2 * sqrt(3.6 / 5) = 2 * sqrt(0.72)
    expected_lrc_width = 2.0 * math.sqrt(3.6 / 5.0)
    assert lrc_width == pytest.approx(expected_lrc_width, abs=1e-12)


def test_lrc_hand_computed() -> None:
    """closes = [10, 12, 11, 14, 13], length=5, multiplier=2.0.

    From SEC test:
      b = 0.8, a = 10.4, residuals = [-0.4, 0.8, -1.0, 1.2, -0.6]
      sum sq = 3.6
      raw_std = sqrt(3.6 / 5) = sqrt(0.72)
      line[4] = 13.6
      upper   = 13.6 + 2 * sqrt(0.72)
      lower   = 13.6 - 2 * sqrt(0.72)
    """
    line, upper, lower = linear_regression_channel(
        [10.0, 12.0, 11.0, 14.0, 13.0], length=5, multiplier=2.0
    )
    raw_std = math.sqrt(3.6 / 5.0)
    assert line[4] == pytest.approx(13.6, abs=1e-12)
    assert upper[4] == pytest.approx(13.6 + 2.0 * raw_std, abs=1e-12)
    assert lower[4] == pytest.approx(13.6 - 2.0 * raw_std, abs=1e-12)


def test_lrc_empty_input() -> None:
    assert linear_regression_channel([]) == ([], [], [])


def test_lrc_length_greater_than_n() -> None:
    line, upper, lower = linear_regression_channel([1.0, 2.0, 3.0], length=10)
    assert line == [None, None, None]
    assert upper == [None, None, None]
    assert lower == [None, None, None]


def test_lrc_invalid_length_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        linear_regression_channel([1.0] * 10, length=1)


def test_lrc_negative_multiplier_raises() -> None:
    with pytest.raises(ValueError, match="multiplier"):
        linear_regression_channel([1.0] * 30, multiplier=-1.0)
