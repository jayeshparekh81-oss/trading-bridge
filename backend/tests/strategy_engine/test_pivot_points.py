"""Classic pivot points calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.pivot_points import pivot_points


def test_pivot_points_first_bar_is_all_none() -> None:
    """Bar 0 has no prior bar to pivot from — every line is None."""
    pp, r1, r2, s1, s2 = pivot_points([10.0, 12.0], [9.0, 11.0], [9.5, 11.5])
    assert pp[0] is None
    assert r1[0] is None
    assert r2[0] is None
    assert s1[0] is None
    assert s2[0] is None


def test_pivot_points_known_values_match_classic_formula() -> None:
    """Hand-computed: prev H=12, L=10, C=11 → PP=11, R1=12, R2=13, S1=10, S2=9."""
    pp, r1, r2, s1, s2 = pivot_points(
        [12.0, 100.0],
        [10.0, 99.0],
        [11.0, 99.5],
    )
    assert pp[1] == 11.0
    assert r1[1] == 12.0
    assert r2[1] == 13.0
    assert s1[1] == 10.0
    assert s2[1] == 9.0


def test_pivot_points_resistance_lies_above_support() -> None:
    """For any defined bar with a non-zero range, R1 > PP > S1 and R2 > S2."""
    n = 10
    highs = [100.0 + i for i in range(n)]
    lows = [99.0 + i for i in range(n)]
    closes = [99.5 + i for i in range(n)]
    pp, r1, r2, s1, s2 = pivot_points(highs, lows, closes)
    for i in range(1, n):
        assert pp[i] is not None
        assert r1[i] > pp[i]  # type: ignore[operator]
        assert pp[i] > s1[i]  # type: ignore[operator]
        assert r2[i] > pp[i]  # type: ignore[operator]
        assert pp[i] > s2[i]  # type: ignore[operator]


def test_pivot_points_output_length_parity() -> None:
    pp, _, _, _, _ = pivot_points([1.0] * 5, [0.5] * 5, [0.7] * 5)
    assert len(pp) == 5


def test_pivot_points_empty_input() -> None:
    assert pivot_points([], [], []) == ([], [], [], [], [])


def test_pivot_points_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        pivot_points([1.0, 2.0], [1.0], [1.0, 2.0])
