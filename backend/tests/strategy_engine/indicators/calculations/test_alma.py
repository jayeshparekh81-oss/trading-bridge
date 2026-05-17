"""ALMA alias tests.

``alma`` is a thin re-export of :func:`arnaud_legoux_ma`. Tests verify:
    * The wrapper matches the underlying calc exactly
    * Default params produce expected ALMA shape
    * All edge cases of arnaud_legoux_ma propagate correctly
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.alma import alma
from app.strategy_engine.indicators.calculations.arnaud_legoux_ma import (
    arnaud_legoux_ma,
)


def test_alma_is_alias_for_arnaud_legoux_ma() -> None:
    """Same input → same output, byte-for-byte."""
    values = [float(i) for i in range(50)]
    assert alma(values) == arnaud_legoux_ma(values)
    assert alma(values, period=14, sigma=4.0, offset=0.5) == arnaud_legoux_ma(
        values, period=14, sigma=4.0, offset=0.5
    )


def test_alma_empty_input_returns_empty() -> None:
    assert alma([]) == []


def test_alma_too_short_returns_empty() -> None:
    assert alma([1.0, 2.0], period=9) == []


def test_alma_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="period"):
        alma([1.0] * 20, period=1)


def test_alma_invalid_sigma_raises() -> None:
    with pytest.raises(ValueError, match="sigma"):
        alma([1.0] * 20, sigma=0)


def test_alma_invalid_offset_raises() -> None:
    with pytest.raises(ValueError, match="offset"):
        alma([1.0] * 20, offset=1.5)


def test_alma_warmup_is_none() -> None:
    """First period-1 indices are None."""
    values = [float(i) for i in range(30)]
    result = alma(values, period=9)
    for v in result[:8]:
        assert v is None
    assert result[8] is not None


def test_alma_output_length_matches_input() -> None:
    values = [float(i) for i in range(50)]
    result = alma(values, period=9)
    assert len(result) == 50


def test_alma_constant_series_yields_constant_alma() -> None:
    values = [42.0] * 30
    result = alma(values, period=9)
    defined = [v for v in result if v is not None]
    assert defined
    assert all(v == pytest.approx(42.0) for v in defined)


def test_alma_smoother_than_input_on_noisy_series() -> None:
    """ALMA's output should have lower std than input on noisy data."""
    import random
    import statistics

    rng = random.Random(7)
    values = [100.0 + rng.gauss(0, 5) for _ in range(60)]
    result = alma(values, period=15, sigma=6.0, offset=0.85)
    defined = [v for v in result if v is not None]
    assert defined
    input_std = statistics.pstdev(values)
    alma_std = statistics.pstdev(defined)
    assert alma_std < input_std


def test_alma_no_nans_no_infs() -> None:
    import random

    rng = random.Random(11)
    values = [100.0 + rng.gauss(0, 2) for _ in range(100)]
    result = alma(values)
    for v in result:
        if v is not None:
            assert not math.isnan(v)
            assert not math.isinf(v)


def test_alma_linear_uptrend_increasing() -> None:
    """On a clean linear uptrend, ALMA output is strictly increasing
    after warmup."""
    values = [float(i) for i in range(30)]
    result = alma(values, period=9)
    defined = [v for v in result if v is not None]
    for a, b in zip(defined, defined[1:], strict=False):
        assert b > a


def test_alma_offset_zero_versus_one_produces_different_outputs() -> None:
    """Different offset choices produce different lines (peak position shifts)."""
    values = [float(i) for i in range(30)]
    a = alma(values, period=9, offset=0.0)
    b = alma(values, period=9, offset=1.0)
    # Find any index where both are defined and compare
    found_diff = False
    for x, y in zip(a, b, strict=True):
        if x is not None and y is not None and abs(x - y) > 1e-9:
            found_diff = True
            break
    assert found_diff, "ALMA outputs identical for offset=0 vs offset=1"
