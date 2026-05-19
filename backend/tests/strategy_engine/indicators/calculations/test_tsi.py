"""True Strength Index (TSI) — tests.

Test convention: Pine ``ta.tsi(close, 25, 13)`` parity. SMA-seeded
nested EMAs over the price-change series.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.tsi import tsi


# ── Property tests ─────────────────────────────────────────────────────


def test_tsi_output_length_matches_input() -> None:
    n = 60
    values = [100.0 + i * 0.1 for i in range(n)]
    out = tsi(values)  # defaults long=25, short=13
    assert len(out) == n


def test_tsi_monotonic_uptrend_approaches_100() -> None:
    """Pure uptrend ⇒ PC = |PC| ⇒ TSI = 100 once fully warmed up."""
    n = 80
    values = [100.0 + i for i in range(n)]  # strictly ascending
    out = tsi(values, long_period=5, short_period=3)
    # After warm-up (1 + 4 + 2 = 7 → defined from index 7), all values 100.
    for v in out[7:]:
        assert v == pytest.approx(100.0, abs=1e-9)


def test_tsi_monotonic_downtrend_approaches_minus_100() -> None:
    """Pure downtrend ⇒ PC = -|PC| ⇒ TSI = -100."""
    n = 80
    values = [200.0 - i for i in range(n)]
    out = tsi(values, long_period=5, short_period=3)
    for v in out[7:]:
        assert v == pytest.approx(-100.0, abs=1e-9)


# ── Hand-computed tests ────────────────────────────────────────────────


def test_tsi_hand_computed_mixed_series_short_periods() -> None:
    """Hand-computed for closes=[10, 12, 8, 14, 9], long=2, short=2.

    PC = [_, 2, -4, 6, -5]  (orig indices 1..4)
    |PC| = [_, 2, 4, 6, 5]

    EMA1(PC, 2):       SMA-seeded at first 2 PC values
        seed @ PC-index 1 (orig idx 2): (2 + -4)/2 = -1.0
        step @ idx 3: alpha=2/3 → (2/3)*6 + (1/3)*-1.0 = 4.0 - 0.333... = 3.6666...
        step @ idx 4: (2/3)*-5 + (1/3)*3.6666... = -3.333... + 1.2222... = -2.1111...

    EMA1(|PC|, 2):
        seed: (2 + 4)/2 = 3.0
        step @ idx 3: (2/3)*6 + (1/3)*3.0 = 4 + 1 = 5.0
        step @ idx 4: (2/3)*5 + (1/3)*5.0 = 3.333 + 1.667 = 5.0

    EMA2(EMA1_pc, 2):
        seed (first 2 EMA1 values, orig idx 2 and 3): (-1.0 + 3.6666...) / 2 = 1.3333...
            → assigned at orig idx 3
        step @ idx 4: (2/3)*-2.1111... + (1/3)*1.3333...
                    = -1.4074... + 0.4444... = -0.9629...

    EMA2(EMA1_abspc, 2):
        seed: (3.0 + 5.0)/2 = 4.0 @ orig idx 3
        step @ idx 4: (2/3)*5.0 + (1/3)*4.0 = 3.333... + 1.333... = 4.6666...

    TSI[3] = 100 * 1.3333... / 4.0 = 33.3333...
    TSI[4] = 100 * -0.9629... / 4.6666... = -20.6349...
    """
    out = tsi([10.0, 12.0, 8.0, 14.0, 9.0], long_period=2, short_period=2)

    assert out[0] is None
    assert out[1] is None
    assert out[2] is None
    # TSI[3] = 100 * (4/3) / 4 = 33.333...
    assert out[3] == pytest.approx(100.0 / 3.0, abs=1e-9)
    # TSI[4] = 100 * -0.9629... / 4.6666...
    # = 100 * (-2.1111... * 2/3 + 1.3333... * 1/3) / ((5.0 * 2/3) + (4.0 * 1/3))
    # Compute analytically using exact fractions:
    # EMA2_pc[4]    = (2/3)*(-19/9) + (1/3)*(4/3) = -38/27 + 4/9 = -38/27 + 12/27 = -26/27
    # EMA2_abspc[4] = (2/3)*5 + (1/3)*4 = 10/3 + 4/3 = 14/3
    # TSI[4] = 100 * (-26/27) / (14/3) = 100 * -26/27 * 3/14 = -7800/378 = -20.6349...
    assert out[4] == pytest.approx(-7800.0 / 378.0, abs=1e-9)


def test_tsi_zero_momentum_returns_none() -> None:
    """Constant series ⇒ PC = 0 throughout ⇒ EMA2_abspc = 0 ⇒ None."""
    out = tsi([5.0] * 30, long_period=3, short_period=2)
    # All defined positions should be None (divisor zero)
    for v in out:
        assert v is None


# ── Reference test ─────────────────────────────────────────────────────


def test_tsi_matches_explicit_recomputation() -> None:
    """Reference: explicit nested-EMA recomputation on random walk."""
    import random
    import math

    rng = random.Random(7)
    n = 100
    long_p = 25
    short_p = 13
    values = [100.0]
    for _ in range(n - 1):
        values.append(values[-1] + rng.uniform(-2, 2))

    out = tsi(values, long_period=long_p, short_period=short_p)

    # Recompute reference values using same nested EMA logic.
    pc = [values[i] - values[i - 1] for i in range(1, n)]
    apc = [abs(x) for x in pc]

    def _ema(series, p):
        m = len(series)
        if p > m:
            return []
        res = [None] * (p - 1)
        seed = sum(series[:p]) / p
        res.append(seed)
        a = 2.0 / (p + 1)
        prev = seed
        for k in range(p, m):
            cur = a * series[k] + (1 - a) * prev
            res.append(cur)
            prev = cur
        return res

    ema1_pc = _ema(pc, long_p)
    ema1_apc = _ema(apc, long_p)

    # EMA2 over the defined contiguous tail of EMA1
    first_def = long_p - 1  # first non-None index in ema1
    ema1_pc_tail = ema1_pc[first_def:]
    ema1_apc_tail = ema1_apc[first_def:]
    ema2_pc_tail = _ema(ema1_pc_tail, short_p)
    ema2_apc_tail = _ema(ema1_apc_tail, short_p)

    # Re-align: ema2 tail at sub-index k → ema1 index first_def+k → pc index = same → original index pc_index+1
    for k, (n_val, d_val) in enumerate(zip(ema2_pc_tail, ema2_apc_tail)):
        if n_val is None or d_val is None:
            continue
        if d_val == 0.0:
            continue
        expected = 100.0 * n_val / d_val
        orig_idx = (first_def + k) + 1
        if not math.isnan(out[orig_idx]):  # type: ignore[arg-type]
            assert out[orig_idx] == pytest.approx(expected, abs=1e-9), f"i={orig_idx}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_tsi_empty_input() -> None:
    assert tsi([]) == []


def test_tsi_series_shorter_than_warmup() -> None:
    """Total warm-up = 1 + (long-1) + (short-1) = 37 with defaults."""
    out = tsi([10.0, 11.0, 12.0])  # only 3 bars
    assert all(v is None for v in out)


def test_tsi_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="long_period"):
        tsi([1.0, 2.0, 3.0], long_period=0)
    with pytest.raises(ValueError, match="short_period"):
        tsi([1.0, 2.0, 3.0], short_period=-1)


def test_tsi_single_bar_returns_all_none() -> None:
    out = tsi([10.0])
    assert out == [None]


def test_tsi_two_bars_all_none() -> None:
    """Two bars produces 1 PC value; can't even seed long EMA with default 25."""
    out = tsi([10.0, 11.0])
    assert out == [None, None]
