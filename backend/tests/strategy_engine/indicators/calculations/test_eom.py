"""Ease of Movement (EOM) — tests.

Test convention: Pine ``ta.eom(length=14, divisor=10000)`` parity.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.eom import eom


# ── Property tests ─────────────────────────────────────────────────────


def test_eom_output_length_matches_input() -> None:
    n = 30
    highs = [10.0 + i * 0.5 for i in range(n)]
    lows = [9.0 + i * 0.5 for i in range(n)]
    vols = [1000.0] * n
    out = eom(highs, lows, vols, length=14)
    assert len(out) == n
    for i in range(14):
        assert out[i] is None


def test_eom_uptrend_positive_downtrend_negative() -> None:
    """Pure uptrend with low volume ⇒ EOM positive; downtrend ⇒ negative."""
    n = 30
    up_h = [10.0 + i for i in range(n)]
    up_l = [9.0 + i for i in range(n)]
    vols = [1000.0] * n  # constant low volume
    out_up = eom(up_h, up_l, vols, length=5)
    for v in out_up[5:]:
        assert v is not None and v > 0

    dn_h = [40.0 - i for i in range(n)]
    dn_l = [39.0 - i for i in range(n)]
    out_dn = eom(dn_h, dn_l, vols, length=5)
    for v in out_dn[5:]:
        assert v is not None and v < 0


# ── Hand-computed test ────────────────────────────────────────────────


def test_eom_hand_computed() -> None:
    """Hand-computed for 5 bars with length=2, divisor=10000:

    highs   = [10, 11, 13, 12, 14]
    lows    = [ 9, 10, 12, 11, 13]
    volumes = [1000, 1100, 1200, 1050, 1150]

    eom_raw computation:
      i=1: midpoint_move = (11+10)/2 - (10+9)/2 = 10.5 - 9.5 = 1.0
           box_ratio     = (1100/10000) / (11-10) = 0.11
           eom_raw[1]    = 1.0 / 0.11 = 100/11
      i=2: midpoint_move = (13+12)/2 - (11+10)/2 = 12.5 - 10.5 = 2.0
           box_ratio     = (1200/10000) / 1 = 0.12
           eom_raw[2]    = 2.0 / 0.12 = 200/12 = 50/3
      i=3: midpoint_move = (12+11)/2 - (13+12)/2 = 11.5 - 12.5 = -1.0
           box_ratio     = (1050/10000) / 1 = 0.105
           eom_raw[3]    = -1.0 / 0.105 = -1000/105 = -200/21
      i=4: midpoint_move = (14+13)/2 - (12+11)/2 = 13.5 - 11.5 = 2.0
           box_ratio     = (1150/10000) / 1 = 0.115
           eom_raw[4]    = 2.0 / 0.115 = 2000/115 = 400/23

    SMA over length=2:
      EOM[2] = (eom_raw[1] + eom_raw[2]) / 2 = (100/11 + 50/3) / 2
      EOM[3] = (eom_raw[2] + eom_raw[3]) / 2 = (50/3 + -200/21) / 2
      EOM[4] = (eom_raw[3] + eom_raw[4]) / 2 = (-200/21 + 400/23) / 2
    """
    highs = [10.0, 11.0, 13.0, 12.0, 14.0]
    lows = [9.0, 10.0, 12.0, 11.0, 13.0]
    vols = [1000.0, 1100.0, 1200.0, 1050.0, 1150.0]
    out = eom(highs, lows, vols, length=2, divisor=10000)

    # Warm-up positions (need length+1 = 3 bars before SMA starts):
    # index 0: None (no prev for diff)
    # index 1: only 1 raw value in window
    # First valid EOM at index 2 (window covers raw[1], raw[2])
    assert out[0] is None
    assert out[1] is None

    expected_2 = (100.0 / 11.0 + 50.0 / 3.0) / 2.0
    expected_3 = (50.0 / 3.0 + -200.0 / 21.0) / 2.0
    expected_4 = (-200.0 / 21.0 + 400.0 / 23.0) / 2.0

    assert out[2] == pytest.approx(expected_2, abs=1e-12)
    assert out[3] == pytest.approx(expected_3, abs=1e-12)
    assert out[4] == pytest.approx(expected_4, abs=1e-12)


# ── Reference test ─────────────────────────────────────────────────────


def test_eom_matches_explicit_recomputation() -> None:
    """Explicit recomputation of midpoint/box_ratio/SMA, comparing."""
    import random

    rng = random.Random(42)
    n = 60
    length = 14
    divisor = 10000
    highs = [50.0 + rng.uniform(0, 3) for _ in range(n)]
    lows = [h - abs(rng.uniform(0.5, 2.0)) for h in highs]
    vols = [rng.uniform(500, 5000) for _ in range(n)]

    out = eom(highs, lows, vols, length=length, divisor=divisor)

    raw = [None]
    for i in range(1, n):
        mid_move = (highs[i] + lows[i]) / 2 - (highs[i - 1] + lows[i - 1]) / 2
        rng_bar = highs[i] - lows[i]
        if rng_bar == 0:
            raw.append(None)
            continue
        box = (vols[i] / divisor) / rng_bar
        if box == 0:
            raw.append(None)
            continue
        raw.append(mid_move / box)

    for i in range(length, n):
        window = raw[i - length + 1 : i + 1]
        if any(v is None for v in window):
            assert out[i] is None
        else:
            expected = sum(window) / length  # type: ignore[arg-type]
            assert out[i] == pytest.approx(expected, abs=1e-12), f"i={i}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_eom_empty_input() -> None:
    assert eom([], [], [], length=14) == []


def test_eom_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        eom([1.0, 2.0], [0.5, 1.5], [100.0], length=2)


def test_eom_too_short_returns_empty() -> None:
    """Need at least length+1 bars (one for diff seed)."""
    out = eom([1.0, 2.0], [0.5, 1.5], [100.0, 200.0], length=10)
    assert out == []


def test_eom_zero_range_bar_returns_none() -> None:
    """A bar with high == low has eom_raw = None ⇒ pollutes that window."""
    highs = [10.0, 11.0, 12.0, 12.0, 13.0]
    lows = [9.0, 10.0, 12.0, 12.0, 12.0]  # i=2 and i=3 have h == l
    vols = [1000.0] * 5
    out = eom(highs, lows, vols, length=2, divisor=10000)
    # raw[2] and raw[3] are None ⇒ SMA at any window touching them is None
    assert out[2] is None
    assert out[3] is None
    assert out[4] is None  # window covers raw[3], raw[4] but raw[3] is None


def test_eom_invalid_length_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        eom([1.0, 2.0], [0.5, 1.5], [100.0, 200.0], length=0)


def test_eom_invalid_divisor_raises() -> None:
    with pytest.raises(ValueError, match="divisor"):
        eom([1.0, 2.0], [0.5, 1.5], [100.0, 200.0], length=2, divisor=0)
    with pytest.raises(ValueError, match="divisor"):
        eom([1.0, 2.0], [0.5, 1.5], [100.0, 200.0], length=2, divisor=-1)
