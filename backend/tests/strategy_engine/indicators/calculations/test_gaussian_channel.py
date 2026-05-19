"""Gaussian Channel — tests.

Locked variant: Ehlers 4-pole filter, period=144, multiplier=sqrt(2),
source=HLCC4, band basis = 4-pole-filtered TR.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.gaussian_channel import (
    gaussian_channel,
)


# ── Property tests ─────────────────────────────────────────────────────


def test_gc_returns_triple_of_three_lists() -> None:
    n = 20
    highs = [10.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    closes = [9.5 + i * 0.1 for i in range(n)]
    line, upper, lower = gaussian_channel(highs, lows, closes, period=10)
    assert len(line) == n
    assert len(upper) == n
    assert len(lower) == n


def test_gc_upper_ge_line_ge_lower_when_tr_nonneg() -> None:
    """TR is always >= 0; filt_tr is the 4-pole filter of a non-negative
    series. Constants preserved by the recursion, so when initial TR
    values are >= 0 and the recursion is started fresh, filtered TR
    tends to stay >= 0 for non-pathological inputs.
    """
    n = 60
    highs = [10.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    closes = [9.5 + i * 0.1 for i in range(n)]
    line, upper, lower = gaussian_channel(highs, lows, closes, period=20)
    for i in range(n):
        assert upper[i] >= line[i] - 1e-9, f"upper >= line failed at {i}"
        assert line[i] >= lower[i] - 1e-9, f"line >= lower failed at {i}"


def test_gc_constant_series_preserves_constant() -> None:
    """For src constant c, the filter coefficients sum to 1 ⇒ filt = c.

    Demonstrates the binomial identity:
      alpha^4 + 4(1-α) - 6(1-α)² + 4(1-α)³ - (1-α)^4 = 1
    (which is alpha^4 + (1 - (1-α)^4) - ... but works out to 1)
    """
    n = 30
    # Constant H, L, C ⇒ HLCC4 constant; TR = 0 throughout (h-l = 0).
    highs = [10.0] * n
    lows = [10.0] * n
    closes = [10.0] * n
    line, upper, lower = gaussian_channel(highs, lows, closes, period=10, multiplier=1.414)
    for i in range(n):
        assert line[i] == pytest.approx(10.0, abs=1e-9)
        # TR = 0 ⇒ bands = line
        assert upper[i] == pytest.approx(10.0, abs=1e-9)
        assert lower[i] == pytest.approx(10.0, abs=1e-9)


# ── Hand-computed test ────────────────────────────────────────────────


def test_gc_hand_computed_first_recursion_step() -> None:
    """Verify the filt[4] recursion against an inline computation.

    Use period=2, multiplier=1.0, and synthetic OHLC that's easy to
    track:
      highs   = [1, 2, 3, 4, 5]
      lows    = [1, 2, 3, 4, 5]   (range=0 ⇒ TR ≈ 0)
      closes  = [1, 2, 3, 4, 5]

    HLCC4 = (h + l + 2c)/4 = (1+1+2)/4 = 1, (2+2+4)/4 = 2, ... so
    src = [1, 2, 3, 4, 5].
    TR  = [0, 1, 1, 1, 1]   (i>=1: max(0, |h-c_prev|, |l-c_prev|) = 1)

    Init: filt_src[0..3] = [1, 2, 3, 4]; filt_tr[0..3] = [0, 1, 1, 1].

    Coefficients for period=2:
      beta  = (1 - cos(pi)) / (sqrt(2) - 1) = (1 - (-1)) / (sqrt(2)-1) = 2/(sqrt(2)-1)
      alpha = -beta + sqrt(beta^2 + 2*beta)

    Recursion at i=4 for src=[1,2,3,4,5]:
      filt_src[4] = alpha^4 * 5
                  + 4*(1-alpha) * filt_src[3]    # = 4*(1-α)*4
                  - 6*(1-alpha)^2 * filt_src[2]  # = -6*(1-α)^2 *3
                  + 4*(1-alpha)^3 * filt_src[1]  # = +4*(1-α)^3 *2
                  -    (1-alpha)^4 * filt_src[0] # = -(1-α)^4 *1

    Same recursion for TR series.

    We don't manually compute alpha to many digits; instead we
    reproduce the recursion explicitly using Python math and assert
    equality.
    """
    period = 2
    multiplier = 1.0
    highs = [1.0, 2.0, 3.0, 4.0, 5.0]
    lows = [1.0, 2.0, 3.0, 4.0, 5.0]
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]

    line, upper, lower = gaussian_channel(
        highs, lows, closes, period=period, multiplier=multiplier
    )

    # Independent reproduction.
    beta = (1.0 - math.cos(2.0 * math.pi / period)) / (math.sqrt(2.0) - 1.0)
    alpha = -beta + math.sqrt(beta * beta + 2.0 * beta)
    one_minus = 1.0 - alpha
    c0 = alpha ** 4
    c1 = 4.0 * one_minus
    c2 = 6.0 * one_minus ** 2
    c3 = 4.0 * one_minus ** 3
    c4 = one_minus ** 4

    src = [(h + l + 2 * c) / 4 for h, l, c in zip(highs, lows, closes)]
    tr = [highs[0] - lows[0]]
    for i in range(1, 5):
        tr.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    # Init filt[0..3] = series[0..3]; recursion i=4.
    fs = src[:4]
    expected_fs4 = (
        c0 * src[4]
        + c1 * fs[3]
        - c2 * fs[2]
        + c3 * fs[1]
        - c4 * fs[0]
    )
    ft = tr[:4]
    expected_ft4 = (
        c0 * tr[4]
        + c1 * ft[3]
        - c2 * ft[2]
        + c3 * ft[1]
        - c4 * ft[0]
    )
    expected_upper4 = expected_fs4 + multiplier * expected_ft4
    expected_lower4 = expected_fs4 - multiplier * expected_ft4

    assert line[4] == pytest.approx(expected_fs4, abs=1e-12)
    assert upper[4] == pytest.approx(expected_upper4, abs=1e-12)
    assert lower[4] == pytest.approx(expected_lower4, abs=1e-12)


# ── Reference test ─────────────────────────────────────────────────────


def test_gc_matches_full_recursion_recomputation() -> None:
    """Reproduce the full recursion and compare every defined position."""
    import random

    rng = random.Random(55)
    n = 60
    period = 20
    multiplier = 1.414

    closes = [100.0]
    for _ in range(n - 1):
        closes.append(closes[-1] + rng.uniform(-1, 1))
    highs = [c + abs(rng.uniform(0.1, 1.0)) for c in closes]
    lows = [c - abs(rng.uniform(0.1, 1.0)) for c in closes]

    line, upper, lower = gaussian_channel(highs, lows, closes, period, multiplier)

    # Reference recursion
    src = [(h + l + 2 * c) / 4 for h, l, c in zip(highs, lows, closes)]
    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        tr.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    beta = (1.0 - math.cos(2.0 * math.pi / period)) / (math.sqrt(2.0) - 1.0)
    alpha = -beta + math.sqrt(beta * beta + 2.0 * beta)
    one_minus = 1.0 - alpha
    c0 = alpha ** 4
    c1 = 4.0 * one_minus
    c2 = 6.0 * one_minus ** 2
    c3 = 4.0 * one_minus ** 3
    c4 = one_minus ** 4

    def _filt(series):
        out = list(series[:4])
        for i in range(4, len(series)):
            out.append(
                c0 * series[i]
                + c1 * out[i - 1]
                - c2 * out[i - 2]
                + c3 * out[i - 3]
                - c4 * out[i - 4]
            )
        return out

    expected_line = _filt(src)
    expected_tr = _filt(tr)

    for i in range(n):
        assert line[i] == pytest.approx(expected_line[i], abs=1e-9), f"line@{i}"
        assert upper[i] == pytest.approx(
            expected_line[i] + multiplier * expected_tr[i], abs=1e-9
        ), f"upper@{i}"
        assert lower[i] == pytest.approx(
            expected_line[i] - multiplier * expected_tr[i], abs=1e-9
        ), f"lower@{i}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_gc_empty_input() -> None:
    line, upper, lower = gaussian_channel([], [], [])
    assert (line, upper, lower) == ([], [], [])


def test_gc_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        gaussian_channel([1.0, 2.0], [0.5], [1.0])


def test_gc_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="period"):
        gaussian_channel([1.0] * 10, [0.5] * 10, [0.7] * 10, period=1)
    with pytest.raises(ValueError, match="period"):
        gaussian_channel([1.0] * 10, [0.5] * 10, [0.7] * 10, period=0)


def test_gc_negative_multiplier_raises() -> None:
    with pytest.raises(ValueError, match="multiplier"):
        gaussian_channel([1.0] * 10, [0.5] * 10, [0.7] * 10, multiplier=-1.0)


def test_gc_fewer_than_4_bars_works() -> None:
    """3 bars ⇒ filt[0..2] = src[0..2]; no recursion."""
    line, upper, lower = gaussian_channel(
        [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], period=5
    )
    assert len(line) == 3
    assert line[0] == pytest.approx(1.0)
    assert line[1] == pytest.approx(2.0)
    assert line[2] == pytest.approx(3.0)
