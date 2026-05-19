"""Random Walk Index (RWI) — tests.

Locked variant: Poulos formulation, max_length=10, atr_period=10,
sqrt divisor uses n (not n-1). Returns (rwi_high, rwi_low).
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.random_walk_index import (
    random_walk_index,
)
from app.strategy_engine.indicators.calculations.atr import atr


# ── Property tests ─────────────────────────────────────────────────────


def test_rwi_returns_tuple_of_two_lists() -> None:
    n = 30
    highs = [10.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    closes = [9.5 + i * 0.1 for i in range(n)]
    h_out, l_out = random_walk_index(highs, lows, closes)
    assert len(h_out) == n
    assert len(l_out) == n


def test_rwi_uptrend_high_dominates() -> None:
    """In a pure uptrend, RWI_high should exceed RWI_low at every defined bar."""
    n = 30
    highs = [10.0 + i for i in range(n)]
    lows = [9.0 + i for i in range(n)]
    closes = [9.5 + i for i in range(n)]
    h_out, l_out = random_walk_index(highs, lows, closes)
    for i in range(10, n):
        assert h_out[i] is not None
        assert l_out[i] is not None
        assert h_out[i] > l_out[i]


def test_rwi_warmup_is_none() -> None:
    """First max(max_length, atr_period-1) bars are None."""
    n = 20
    highs = [10.0 + i for i in range(n)]
    lows = [9.0 + i for i in range(n)]
    closes = [9.5 + i for i in range(n)]
    h_out, l_out = random_walk_index(highs, lows, closes)
    # Defaults: max_length=10, atr_period=10. First defined = max(10, 9) = 10.
    for i in range(10):
        assert h_out[i] is None, f"h_out[{i}] should be None"
        assert l_out[i] is None, f"l_out[{i}] should be None"


# ── Hand-computed test ────────────────────────────────────────────────


def test_rwi_hand_computed_constant_range() -> None:
    """Hand-computed for an 11-bar pure uptrend with constant bar range = 1.0.

    highs[i] = 10 + 0.5*i, lows[i] = 9 + 0.5*i, closes[i] = 9.5 + 0.5*i.

    True range at every bar = 1.0 (range = 1.0, gap = 0.5 from prev close
    which is smaller). ATR(10) = 1.0 at every defined position.

    At bar t=10 with ATR=1.0:
      For RWI_high, n=k: (high[10] - low[10-k]) / sqrt(k)
        n=2: (15 - 13)   / sqrt(2)  = 2 / 1.41421... ≈ 1.4142
        n=3: (15 - 12.5) / sqrt(3)  = 2.5 / 1.73205 ≈ 1.4434
        n=4: (15 - 12)   / sqrt(4)  = 3 / 2.0 = 1.5
        n=5: (15 - 11.5) / sqrt(5)  = 3.5 / 2.2360 ≈ 1.5652
        n=6: (15 - 11)   / sqrt(6)  = 4 / 2.4494 ≈ 1.6330
        n=7: (15 - 10.5) / sqrt(7)  = 4.5 / 2.6457 ≈ 1.7008
        n=8: (15 - 10)   / sqrt(8)  = 5 / 2.8284 ≈ 1.7677
        n=9: (15 - 9.5)  / sqrt(9)  = 5.5 / 3.0 = 1.8333
        n=10: (15 - 9)   / sqrt(10) = 6 / 3.16227 ≈ 1.8973
      Max = 1.89736... at n=10.

      For RWI_low, n=k: (high[10-k] - low[10]) / sqrt(k); note low[10]=14
        n=2: (high[8] - 14) / sqrt(2) = (14 - 14) / sqrt(2) = 0
        n=3: (high[7] - 14) / sqrt(3) = (13.5 - 14) / sqrt(3) = -0.288...
        ... all negative or zero.
      Max = 0.0 at n=2.
    """
    highs = [10.0 + 0.5 * i for i in range(11)]
    lows = [9.0 + 0.5 * i for i in range(11)]
    closes = [9.5 + 0.5 * i for i in range(11)]
    h_out, l_out = random_walk_index(highs, lows, closes)

    # First 10 bars: None
    for i in range(10):
        assert h_out[i] is None
        assert l_out[i] is None

    # ATR should be 1.0 at bar 10
    atr_vals = atr(highs, lows, closes, period=10)
    assert atr_vals[10] == pytest.approx(1.0, abs=1e-12)

    expected_high = 6.0 / math.sqrt(10.0)
    assert h_out[10] == pytest.approx(expected_high, abs=1e-9)

    # RWI_low at bar 10: best (most positive) over n in 2..10.
    # All windows give (high[10-n] - low[10]) which is <= 0.
    # n=2: (high[8] - 14) / sqrt(2) = (14 - 14) / sqrt(2) = 0.0  ← max
    assert l_out[10] == pytest.approx(0.0, abs=1e-12)


# ── Reference test ─────────────────────────────────────────────────────


def test_rwi_matches_explicit_recomputation() -> None:
    """Compare against explicit n-sweep recomputation."""
    import random

    rng = random.Random(13)
    n = 50
    highs = [50.0 + rng.uniform(-3, 3) for _ in range(n)]
    lows = [h - abs(rng.uniform(0.5, 2.0)) for h in highs]
    closes = [
        max(lo, min(hi, 50.0 + rng.uniform(-2, 2)))
        for hi, lo in zip(highs, lows)
    ]

    max_length = 10
    atr_period = 10
    h_out, l_out = random_walk_index(
        highs, lows, closes, max_length=max_length, atr_period=atr_period
    )

    atr_vals = atr(highs, lows, closes, period=atr_period)
    first_defined = max(max_length, atr_period - 1)
    for t in range(first_defined, n):
        a = atr_vals[t]
        if a is None or a == 0.0:
            assert h_out[t] is None
            assert l_out[t] is None
            continue
        best_h = -float("inf")
        best_l = -float("inf")
        for k in range(2, max_length + 1):
            denom = a * math.sqrt(k)
            best_h = max(best_h, (highs[t] - lows[t - k]) / denom)
            best_l = max(best_l, (highs[t - k] - lows[t]) / denom)
        assert h_out[t] == pytest.approx(best_h, abs=1e-9), f"high@{t}"
        assert l_out[t] == pytest.approx(best_l, abs=1e-9), f"low@{t}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_rwi_empty_input() -> None:
    out = random_walk_index([], [], [])
    assert out == ([], [])


def test_rwi_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        random_walk_index([1.0, 2.0], [0.5], [1.0])


def test_rwi_too_short_returns_none_pair() -> None:
    """If shorter than ATR seed, ATR returns []; RWI returns all-None pair."""
    # 5 bars but max_length=10 means we can't even sweep n
    highs = [10.0, 11.0, 12.0, 13.0, 14.0]
    lows = [9.0, 10.0, 11.0, 12.0, 13.0]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5]
    h_out, l_out = random_walk_index(highs, lows, closes)
    assert h_out == [None] * 5
    assert l_out == [None] * 5


def test_rwi_invalid_max_length_raises() -> None:
    with pytest.raises(ValueError, match="max_length"):
        random_walk_index([1.0] * 20, [0.5] * 20, [0.7] * 20, max_length=1)
    with pytest.raises(ValueError, match="max_length"):
        random_walk_index([1.0] * 20, [0.5] * 20, [0.7] * 20, max_length=0)


def test_rwi_invalid_atr_period_raises() -> None:
    with pytest.raises(ValueError, match="atr_period"):
        random_walk_index([1.0] * 20, [0.5] * 20, [0.7] * 20, atr_period=0)
