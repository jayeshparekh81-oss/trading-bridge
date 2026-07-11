"""Exact classic-pivot arithmetic (Module R4)."""

from __future__ import annotations

from levels.pivots import classic_pivots


def test_classic_pivots_exact():
    p = classic_pivots(high=110.0, low=90.0, close=100.0)
    assert p == {
        "PIVOT_P": 100.0,
        "PIVOT_R1": 110.0, "PIVOT_S1": 90.0,
        "PIVOT_R2": 120.0, "PIVOT_S2": 80.0,
        "PIVOT_R3": 130.0, "PIVOT_S3": 70.0,
    }


def test_pivots_asymmetric():
    # H=120 L=90 C=115 -> P=(120+90+115)/3=108.333...
    p = classic_pivots(120.0, 90.0, 115.0)
    assert round(p["PIVOT_P"], 4) == round((120 + 90 + 115) / 3, 4)
    assert p["PIVOT_R1"] == 2 * p["PIVOT_P"] - 90.0
    assert p["PIVOT_S1"] == 2 * p["PIVOT_P"] - 120.0
    assert round(p["PIVOT_R2"], 6) == round(p["PIVOT_P"] + 30.0, 6)
    assert round(p["PIVOT_S2"], 6) == round(p["PIVOT_P"] - 30.0, 6)
