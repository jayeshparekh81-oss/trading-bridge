"""DeMarker (DeM) calculation tests.

Test convention: Tom DeMark's DeM formula —
SmoothedDeMax / (SmoothedDeMax + SmoothedDeMin), bounded [0, 1].
DeMax/DeMin require i >= 1 (need a previous bar); first defined
position is ``period`` (one extra warm-up).
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.demarker import demarker


# ── Property tests ─────────────────────────────────────────────────────


def test_demarker_output_length_matches_input() -> None:
    """Output length = input length."""
    n = 30
    highs = [10.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    out = demarker(highs, lows, period=14)
    assert len(out) == n


def test_demarker_warm_up_is_none() -> None:
    """First ``period`` positions are None."""
    highs = [10.0, 11.0, 13.0, 12.0, 14.0, 15.0]
    lows = [9.0, 10.0, 12.0, 11.0, 13.0, 14.0]
    out = demarker(highs, lows, period=3)
    for i in range(3):
        assert out[i] is None, f"Expected None at i={i}, got {out[i]}"


def test_demarker_output_bounded_zero_to_one() -> None:
    """Output is bounded in [0, 1] when defined."""
    import random

    rng = random.Random(11)
    n = 100
    highs = [50.0 + rng.uniform(0, 5) for _ in range(n)]
    lows = [h - abs(rng.uniform(0.5, 3.0)) for h in highs]
    out = demarker(highs, lows, period=14)
    for v in out:
        if v is not None:
            assert 0.0 <= v <= 1.0, f"out of range: {v}"


# ── Hand-computed test ────────────────────────────────────────────────


def test_demarker_hand_computed() -> None:
    """Hand-computed for period=3.

    highs = [10, 11, 13, 12, 14, 15]
    lows  = [9,  10, 12, 11, 13, 14]

    DeMax (max(0, high[i] - high[i-1])):
        i=0: 0   (by convention; no prior bar)
        i=1: max(0, 11-10) = 1
        i=2: max(0, 13-11) = 2
        i=3: max(0, 12-13) = 0
        i=4: max(0, 14-12) = 2
        i=5: max(0, 15-14) = 1

    DeMin (max(0, low[i-1] - low[i])):
        i=0: 0
        i=1: max(0, 9-10) = 0
        i=2: max(0, 10-12) = 0
        i=3: max(0, 12-11) = 1
        i=4: max(0, 11-13) = 0
        i=5: max(0, 13-14) = 0

    SMA(DeMax, 3):
        i=3: (DeMax[1] + DeMax[2] + DeMax[3]) / 3 = (1+2+0)/3 = 1.0
        i=4: (2+0+2)/3 = 4/3
        i=5: (0+2+1)/3 = 1.0

    SMA(DeMin, 3):
        i=3: (0+0+1)/3 = 1/3
        i=4: (0+1+0)/3 = 1/3
        i=5: (1+0+0)/3 = 1/3

    DeMarker:
        i=3: 1.0 / (1.0 + 1/3) = 1.0 / (4/3) = 3/4 = 0.75
        i=4: (4/3) / (4/3 + 1/3) = (4/3) / (5/3) = 4/5 = 0.80
        i=5: 1.0 / (1.0 + 1/3) = 0.75
    """
    highs = [10.0, 11.0, 13.0, 12.0, 14.0, 15.0]
    lows = [9.0, 10.0, 12.0, 11.0, 13.0, 14.0]
    out = demarker(highs, lows, period=3)

    assert out[0] is None
    assert out[1] is None
    assert out[2] is None
    assert out[3] == pytest.approx(0.75, abs=1e-12)
    assert out[4] == pytest.approx(0.8, abs=1e-12)
    assert out[5] == pytest.approx(0.75, abs=1e-12)


def test_demarker_strong_uptrend_gives_high_reading() -> None:
    """Pure uptrend (every bar's high > prior high, lows ascending) ⇒
    DeMax always positive, DeMin always 0 ⇒ DeMarker = 1.0.
    """
    highs = [float(i) for i in range(10, 30)]
    lows = [float(i) for i in range(9, 29)]  # also ascending
    out = demarker(highs, lows, period=5)
    for v in out[5:]:
        assert v == pytest.approx(1.0, abs=1e-12)


def test_demarker_strong_downtrend_gives_zero_reading() -> None:
    """Pure downtrend ⇒ DeMax always 0, DeMin always positive ⇒ DeMarker = 0."""
    highs = [float(i) for i in range(30, 10, -1)]
    lows = [float(i) for i in range(29, 9, -1)]
    out = demarker(highs, lows, period=5)
    for v in out[5:]:
        assert v == pytest.approx(0.0, abs=1e-12)


# ── Reference test (recompute from formula) ────────────────────────────


def test_demarker_matches_explicit_recomputation() -> None:
    """Reference: explicit DeMax/DeMin/SMA recomputation matches our output."""
    import random

    rng = random.Random(123)
    n = 50
    period = 14
    highs = [100.0 + rng.uniform(-2, 2) for _ in range(n)]
    lows = [h - abs(rng.uniform(0.1, 1.5)) for h in highs]

    out = demarker(highs, lows, period=period)

    demax = [0.0] + [max(0.0, highs[i] - highs[i - 1]) for i in range(1, n)]
    demin = [0.0] + [max(0.0, lows[i - 1] - lows[i]) for i in range(1, n)]
    for i in range(period, n):
        s_max = sum(demax[i - period + 1 : i + 1]) / period
        s_min = sum(demin[i - period + 1 : i + 1]) / period
        denom = s_max + s_min
        expected = s_max / denom if denom != 0.0 else None
        if expected is None:
            assert out[i] is None
        else:
            assert out[i] == pytest.approx(expected, abs=1e-12), f"i={i}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_demarker_empty_input() -> None:
    assert demarker([], [], period=14) == []


def test_demarker_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        demarker([1.0, 2.0, 3.0], [0.5, 1.5], period=2)


def test_demarker_period_too_large_for_data() -> None:
    """Need at least period+1 bars (one extra for diff seed)."""
    assert demarker([1.0, 2.0, 3.0], [0.5, 1.5, 2.5], period=10) == []


def test_demarker_flat_series_returns_none() -> None:
    """Flat series ⇒ DeMax = DeMin = 0 ⇒ denom = 0 ⇒ None."""
    highs = [10.0] * 20
    lows = [9.0] * 20
    out = demarker(highs, lows, period=5)
    for v in out[5:]:
        assert v is None


def test_demarker_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="period"):
        demarker([1.0, 2.0], [0.5, 1.5], period=0)
