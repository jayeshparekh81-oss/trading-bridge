"""OBV calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.obv import obv


def test_obv_first_value_is_zero() -> None:
    """Granville's OBV starts at zero by convention."""
    out = obv([10.0, 11.0, 10.5], [100.0, 200.0, 150.0])
    assert out[0] == 0.0


def test_obv_up_close_adds_volume() -> None:
    """OBV([10, 11], [100, 200]) -> [0, 200] (close went up so add volume)."""
    out = obv([10.0, 11.0], [100.0, 200.0])
    assert out == [0.0, 200.0]


def test_obv_down_close_subtracts_volume() -> None:
    out = obv([10.0, 9.0], [100.0, 150.0])
    assert out == [0.0, -150.0]


def test_obv_flat_close_keeps_running_total() -> None:
    out = obv([10.0, 10.0, 10.0], [100.0, 200.0, 300.0])
    assert out == [0.0, 0.0, 0.0]


def test_obv_known_sequence() -> None:
    """Hand-traced: closes=[10,11,10.5,11.5,11.5], vols=[100,200,150,300,50].

    i=0: OBV=0
    i=1: 11>10 -> +200 -> 200
    i=2: 10.5<11 -> -150 -> 50
    i=3: 11.5>10.5 -> +300 -> 350
    i=4: 11.5==11.5 -> unchanged -> 350
    """
    out = obv(
        [10.0, 11.0, 10.5, 11.5, 11.5],
        [100.0, 200.0, 150.0, 300.0, 50.0],
    )
    assert out == [0.0, 200.0, 50.0, 350.0, 350.0]


def test_obv_empty_input() -> None:
    assert obv([], []) == []


def test_obv_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        obv([1.0, 2.0], [100.0])


def test_obv_output_length_matches_input_length() -> None:
    out = obv([float(i) for i in range(20)], [100.0] * 20)
    assert len(out) == 20
