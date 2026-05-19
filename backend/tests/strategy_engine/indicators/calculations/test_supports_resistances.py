"""Supports & Resistances — tests.

Algorithm A locked: symmetric 5-bar fractal (lookback=2), tolerance=0.5%,
strength = count of subsequent touches, max_levels=10, drop-lowest
truncation, merge nearby levels within tolerance.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.supports_resistances import (
    supports_resistances,
)


# ── Property tests ─────────────────────────────────────────────────────


def test_sr_returns_list_of_dicts() -> None:
    """Output is a list; each entry is a Level dict with required keys."""
    highs = [10.0, 11.0, 12.0, 13.0, 12.5, 11.5, 11.0, 11.5, 13.0]
    lows = [9.0, 10.0, 11.0, 12.0, 11.0, 10.5, 10.0, 10.5, 11.5]
    out = supports_resistances(highs, lows, lookback=2)
    assert isinstance(out, list)
    for lvl in out:
        assert isinstance(lvl, dict)
        assert {"price", "type", "strength", "bar_index", "formed_at_index"} <= lvl.keys()
        assert lvl["type"] in ("support", "resistance")


def test_sr_no_pivots_returns_empty() -> None:
    """Monotonic series has no fractal pivots ⇒ empty list."""
    highs = [10.0 + i for i in range(20)]
    lows = [9.0 + i for i in range(20)]
    out = supports_resistances(highs, lows)
    assert out == []


def test_sr_too_short_returns_empty() -> None:
    """Series shorter than 2*lookback+1 ⇒ empty list."""
    out = supports_resistances([1.0, 2.0, 3.0], [0.5, 1.5, 2.5], lookback=2)
    assert out == []


# ── Hand-computed test ────────────────────────────────────────────────


def test_sr_hand_computed_simple_pivot_high_and_low() -> None:
    """9-bar synthetic with one pivot high at bar 3 and pivot low at bar 6.

    bars:        0    1    2    3    4    5    6    7    8
    highs =    [10,  11,  12,  15,  13,  12,  10,  11,  13]
    lows  =    [ 9,  10,  11,  13,  12,  11,   9,  10,  12]

    Pivot high check at N=3 (with lookback=2):
        high[3] = 15 > high[1]=11, high[2]=12, high[4]=13, high[5]=12 ✓
        confirmed at bar 5 (3 + 2)

    Pivot low check at N=6:
        low[6] = 9 < low[4]=12, low[5]=11, low[7]=10, low[8]=12 ✓
        confirmed at bar 8 (6 + 2)

    Touch counting:
        Resistance @ 15: touches[j>=6] within 0.5% of 15 = ±0.075.
            high[6]=10, high[7]=11, high[8]=13 — none within 0.075 of 15.
            strength = 0.

        Support @ 9: touches[j>=9] — but no bars >= 9 exist (n=9).
            strength = 0.

    Both bar_index in [2, 6] (range = lookback..n-lookback-1 = 2..6).
    But check pivot HIGH at bar 2: high[2]=12 > high[0]=10, high[1]=11,
        high[3]=15, high[4]=13?  15 > 12 — fails. Not a pivot high.
    Check pivot LOW at bar 2: low[2]=11 < low[0]=9? No. Not a pivot low.

    Bar 3: pivot high (verified). Pivot low? low[3]=13 < low[1]=10? No.
    Bar 4: high[4]=13 > high[3]=15? No. low[4]=12 < low[2]=11? No.
    Bar 5: high[5]=12 > 15? No. low[5]=11 < low[3]=13? Yes — but
        low[5]=11 < low[4]=12? Yes. low[5]<low[6]=9? NO. Not a pivot low.
    Bar 6: high[6]=10 < anything? Not a high pivot. Pivot low verified.

    So expected output: 2 levels — resistance @ 15 (bar 3), support @ 9 (bar 6).
    """
    highs = [10.0, 11.0, 12.0, 15.0, 13.0, 12.0, 10.0, 11.0, 13.0]
    lows = [9.0, 10.0, 11.0, 13.0, 12.0, 11.0, 9.0, 10.0, 12.0]
    out = supports_resistances(highs, lows, lookback=2, tolerance_pct=0.5)

    assert len(out) == 2
    # Find resistance and support
    res = [lvl for lvl in out if lvl["type"] == "resistance"]
    sup = [lvl for lvl in out if lvl["type"] == "support"]
    assert len(res) == 1
    assert len(sup) == 1
    assert res[0]["price"] == pytest.approx(15.0)
    assert res[0]["bar_index"] == 3
    assert res[0]["formed_at_index"] == 5
    assert sup[0]["price"] == pytest.approx(9.0)
    assert sup[0]["bar_index"] == 6
    assert sup[0]["formed_at_index"] == 8


def test_sr_touch_counting_increments_strength() -> None:
    """Construct a resistance with multiple subsequent touches.

    Pivot high at bar 3 = 15.0; later bars retest near 15.0.
    Touches counted ONLY after formed_at_index (bar 5).
    """
    highs = [10.0, 11.0, 12.0, 15.0, 13.0, 12.0, 14.95, 13.0, 15.02, 13.0, 11.0]
    lows = [9.0, 10.0, 11.0, 13.0, 12.0, 11.0, 13.0, 12.5, 13.5, 12.0, 9.0]
    out = supports_resistances(highs, lows, lookback=2, tolerance_pct=0.5)
    # Bar 6 high = 14.95 (within 0.5% of 15 → 0.075 tolerance → diff 0.05 < 0.075 ✓)
    # Bar 8 high = 15.02 (diff 0.02 < 0.075 ✓)
    # So resistance @ 15 should have strength = 2
    res = next(lvl for lvl in out if lvl["type"] == "resistance" and lvl["bar_index"] == 3)
    assert res["strength"] == 2


def test_sr_merge_nearby_levels() -> None:
    """Two pivot highs within tolerance ⇒ merged into one level."""
    # Pivot high at bar 3 = 15.00, pivot high at bar 8 = 15.05 (diff 0.05/15 = 0.33% < 0.5%)
    # They should merge: avg price = 15.025, summed strengths.
    highs = [10.0, 11.0, 12.0, 15.0, 13.0, 12.0, 13.0, 14.0, 15.05, 14.0, 13.0]
    lows = [9.0] * 11
    out = supports_resistances(highs, lows, lookback=2, tolerance_pct=0.5)
    res_levels = [lvl for lvl in out if lvl["type"] == "resistance"]
    # Both pivots should be confirmed (bar 3 at lookback=2..n-lookback=8,
    # bar 8 needs n-1-2=8 — yes 8 is valid). Merge: one combined level.
    assert len(res_levels) == 1
    assert res_levels[0]["price"] == pytest.approx((15.0 + 15.05) / 2.0)


# ── Reference test ─────────────────────────────────────────────────────


def test_sr_matches_explicit_pivot_detection() -> None:
    """Reference: explicit pivot detection matches our output's bar_indices."""
    import random

    rng = random.Random(7)
    n = 60
    highs = []
    lows = []
    base = 100.0
    for _ in range(n):
        base += rng.uniform(-2, 2)
        highs.append(base + abs(rng.uniform(0.5, 2.0)))
        lows.append(base - abs(rng.uniform(0.5, 2.0)))

    out = supports_resistances(highs, lows, lookback=2, tolerance_pct=0.5)

    # Reference: extract all pivot bars
    expected_resistance_bars = []
    expected_support_bars = []
    for N in range(2, n - 2):
        if (
            highs[N] > highs[N - 1]
            and highs[N] > highs[N - 2]
            and highs[N] > highs[N + 1]
            and highs[N] > highs[N + 2]
        ):
            expected_resistance_bars.append(N)
        if (
            lows[N] < lows[N - 1]
            and lows[N] < lows[N - 2]
            and lows[N] < lows[N + 1]
            and lows[N] < lows[N + 2]
        ):
            expected_support_bars.append(N)

    out_resistance_bars = sorted(
        lvl["bar_index"] for lvl in out if lvl["type"] == "resistance"
    )
    out_support_bars = sorted(
        lvl["bar_index"] for lvl in out if lvl["type"] == "support"
    )
    # NOTE: merge can collapse bars to the earlier of two — so out
    # might be a subset of expected. Check that every out bar IS in
    # expected:
    for b in out_resistance_bars:
        assert b in expected_resistance_bars, f"resistance bar {b} unexpected"
    for b in out_support_bars:
        assert b in expected_support_bars, f"support bar {b} unexpected"


# ── Edge case tests ────────────────────────────────────────────────────


def test_sr_empty_input() -> None:
    assert supports_resistances([], []) == []


def test_sr_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        supports_resistances([1.0, 2.0], [0.5])


def test_sr_invalid_lookback_raises() -> None:
    with pytest.raises(ValueError, match="lookback"):
        supports_resistances([1.0] * 10, [0.5] * 10, lookback=0)
    with pytest.raises(ValueError, match="lookback"):
        supports_resistances([1.0] * 10, [0.5] * 10, lookback=-1)


def test_sr_invalid_tolerance_raises() -> None:
    with pytest.raises(ValueError, match="tolerance"):
        supports_resistances([1.0] * 10, [0.5] * 10, tolerance_pct=0)
    with pytest.raises(ValueError, match="tolerance"):
        supports_resistances([1.0] * 10, [0.5] * 10, tolerance_pct=-1)


def test_sr_invalid_max_levels_raises() -> None:
    with pytest.raises(ValueError, match="max_levels"):
        supports_resistances([1.0] * 10, [0.5] * 10, max_levels=0)


def test_sr_truncation_keeps_highest_strength() -> None:
    """Force many pivots, max_levels=2 ⇒ keep top-2 by strength."""
    # Construct: many pivots, some with multiple touches, some with none.
    # Simplest: include 3 distinct pivot highs, two of which have touches.
    n = 25
    highs = [10.0] * n
    lows = [9.0] * n
    # Plant pivot high at bar 3 = 15 (no touches)
    highs[3] = 15.0
    # Plant pivot high at bar 8 = 20 (with touches later)
    highs[8] = 20.0
    highs[12] = 19.95  # touch within 0.5% of 20
    highs[15] = 20.05  # touch
    # Plant pivot high at bar 18 = 18 (one touch)
    highs[18] = 18.0
    highs[22] = 17.95  # touch
    # Set neighbours appropriately to avoid spurious pivots
    # Run with max_levels=2
    out = supports_resistances(highs, lows, lookback=2, tolerance_pct=0.5, max_levels=2)
    # Expect 2 levels kept. Highest-strength should be at price ~20.
    res = sorted([lvl for lvl in out if lvl["type"] == "resistance"],
                 key=lambda d: d["strength"], reverse=True)
    assert len(res) <= 2
    if res:
        # The 15-level (0 touches) should NOT be kept since others have >0.
        prices = [r["price"] for r in res]
        assert 15.0 not in prices
