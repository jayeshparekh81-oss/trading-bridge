"""Williams VIX Fix calculation tests.

Test convention: Larry Williams' VIX Fix formula —
``((highest_high[period] - low[today]) / highest_high[period]) * 100``.
First defined position at index ``period - 1``.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.williams_vix_fix import (
    williams_vix_fix,
)


# ── Property tests ─────────────────────────────────────────────────────


def test_wvf_output_length_matches_input() -> None:
    """Output length = input length; first ``period-1`` are None."""
    highs = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    lows = [9.0, 10.0, 11.0, 12.0, 13.0, 11.0]
    out = williams_vix_fix(highs, lows, period=4)
    assert len(out) == 6
    assert out[0] is None
    assert out[1] is None
    assert out[2] is None


def test_wvf_output_always_non_negative() -> None:
    """WVF is non-negative because rolling_high >= low[i] always."""
    highs = [100.0, 102.0, 95.0, 110.0, 105.0, 99.0, 88.0, 92.0, 101.0, 99.0]
    lows = [98.0, 100.0, 90.0, 104.0, 102.0, 95.0, 80.0, 88.0, 95.0, 96.0]
    out = williams_vix_fix(highs, lows, period=5)
    for v in out:
        if v is not None:
            assert v >= 0.0


def test_wvf_constant_series_is_zero() -> None:
    """Constant highs == constant lows ⇒ WVF = 0 (no range)."""
    highs = [50.0] * 10
    lows = [50.0] * 10
    out = williams_vix_fix(highs, lows, period=5)
    assert out[:4] == [None] * 4
    for v in out[4:]:
        assert v == 0.0


# ── Hand-computed tests ────────────────────────────────────────────────


def test_wvf_hand_computed_simple_period_4() -> None:
    """Hand-computed for period=4:
    highs = [10, 11, 12, 13, 14, 15]
    lows  = [9,  10, 11, 12, 13, 11]

    i=3 (window highs[0..3]=[10,11,12,13]):
        highest=13, low[3]=12
        WVF = (13 - 12) / 13 * 100 = 100/13 ≈ 7.69230769
    i=4 (window [11,12,13,14]):
        highest=14, low[4]=13
        WVF = (14 - 13) / 14 * 100 = 100/14 ≈ 7.14285714
    i=5 (window [12,13,14,15]):
        highest=15, low[5]=11  ← capitulation example
        WVF = (15 - 11) / 15 * 100 = 400/15 ≈ 26.6666667
    """
    highs = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    lows = [9.0, 10.0, 11.0, 12.0, 13.0, 11.0]
    out = williams_vix_fix(highs, lows, period=4)

    assert out[3] == pytest.approx(100.0 / 13.0, abs=1e-12)
    assert out[4] == pytest.approx(100.0 / 14.0, abs=1e-12)
    assert out[5] == pytest.approx(400.0 / 15.0, abs=1e-12)


def test_wvf_capitulation_spike_is_visible() -> None:
    """When low drops sharply vs rolling-high, WVF spikes."""
    highs = [100.0] * 22
    lows = [99.0] * 21 + [50.0]  # crash on bar 21
    out = williams_vix_fix(highs, lows, period=22)
    # All bars 0..20 ⇒ WVF = (100 - 99) / 100 * 100 = 1.0
    for i in range(21, 21):
        assert out[i] == pytest.approx(1.0, abs=1e-12)
    # Bar 21: rolling-high still 100, low = 50 → WVF = 50.0
    assert out[21] == pytest.approx(50.0, abs=1e-12)


# ── Reference test ─────────────────────────────────────────────────────


def test_wvf_matches_manual_recomputation() -> None:
    """Recompute WVF using a naive O(n*period) Python loop and compare."""
    import random

    rng = random.Random(77)
    n = 50
    period = 14
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(max(1.0, closes[-1] + rng.uniform(-3, 3)))
    highs = [c + abs(rng.uniform(0, 2)) for c in closes]
    lows = [c - abs(rng.uniform(0, 2)) for c in closes]

    out = williams_vix_fix(highs, lows, period=period)

    for i in range(period - 1, n):
        win_high = max(highs[i - period + 1 : i + 1])
        if win_high == 0:
            assert out[i] is None
            continue
        expected = (win_high - lows[i]) / win_high * 100.0
        assert out[i] == pytest.approx(expected, abs=1e-12)


# ── Edge case tests ────────────────────────────────────────────────────


def test_wvf_empty_input() -> None:
    assert williams_vix_fix([], [], period=22) == []


def test_wvf_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        williams_vix_fix([1.0, 2.0, 3.0], [1.0, 2.0], period=2)


def test_wvf_period_greater_than_length() -> None:
    assert williams_vix_fix([1.0, 2.0], [0.5, 1.5], period=10) == []


def test_wvf_period_one_is_bar_range_over_high() -> None:
    """Period=1: window is just today, so WVF = (high - low) / high * 100."""
    highs = [10.0, 20.0, 5.0, 8.0]
    lows = [9.0, 18.0, 4.0, 6.0]
    out = williams_vix_fix(highs, lows, period=1)
    assert out[0] == pytest.approx(10.0, abs=1e-12)  # (10-9)/10 * 100
    assert out[1] == pytest.approx(10.0, abs=1e-12)  # (20-18)/20 * 100
    assert out[2] == pytest.approx(20.0, abs=1e-12)  # (5-4)/5 * 100
    assert out[3] == pytest.approx(25.0, abs=1e-12)  # (8-6)/8 * 100


def test_wvf_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="period"):
        williams_vix_fix([1.0, 2.0], [0.5, 1.5], period=0)


def test_wvf_zero_high_returns_none() -> None:
    """Division guard: rolling_high == 0 ⇒ None for that bar."""
    highs = [0.0, 0.0, 0.0, 0.0]
    lows = [-1.0, -2.0, -3.0, -4.0]
    out = williams_vix_fix(highs, lows, period=2)
    # Position 0 is None (warm-up); positions 1-3 all have window_high=0 ⇒ None
    assert out == [None, None, None, None]


def test_wvf_zero_low_gives_100_percent() -> None:
    """Edge: if low[i] == 0 and rolling-high > 0, WVF = 100%."""
    highs = [10.0, 10.0, 10.0]
    lows = [5.0, 5.0, 0.0]
    out = williams_vix_fix(highs, lows, period=2)
    assert out[1] == pytest.approx(50.0, abs=1e-12)  # (10-5)/10*100
    assert out[2] == pytest.approx(100.0, abs=1e-12)  # (10-0)/10*100
