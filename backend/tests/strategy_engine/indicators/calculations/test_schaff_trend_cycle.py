"""Schaff Trend Cycle — tests.

Locked variant: Pine ta.stc(close, cycle, fast, slow) parity.
fast_length=23, slow_length=50, cycle_length=10, factor=0.5.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.schaff_trend_cycle import (
    schaff_trend_cycle,
)


# ── Property tests ─────────────────────────────────────────────────────


def test_stc_output_length_matches_input() -> None:
    closes = [100.0 + i * 0.1 for i in range(100)]
    out = schaff_trend_cycle(closes)
    assert len(out) == 100


def test_stc_warmup_is_none() -> None:
    """First (slow_length - 1) bars cannot have STC defined (MACD warm-up)."""
    closes = [100.0 + i for i in range(60)]
    out = schaff_trend_cycle(closes)
    # slow=50 → MACD first defined at i=49. STC needs additional cycle bars
    # AND the two smoothing passes. So values appear later than 49.
    for i in range(49):
        assert out[i] is None


def test_stc_output_roughly_bounded_zero_to_hundred() -> None:
    """STC output bounded roughly [0, 100] — small overshoots OK."""
    import random

    rng = random.Random(31)
    closes = [100.0 + rng.uniform(-5, 5) for _ in range(120)]
    out = schaff_trend_cycle(closes)
    for v in out:
        if v is not None:
            # smoothing can never push outside the stoch's [0, 100] range
            # because state = state + factor*(stoch - state), bounded
            # between the two values both in [0, 100]
            assert -0.001 <= v <= 100.001, f"value out of range: {v}"


# ── Hand-computed test ────────────────────────────────────────────────


def test_stc_hand_computed_small_periods() -> None:
    """Hand-derive STC for closes=[10,12,11,14,13,16,15,18],
    fast_length=2, slow_length=3, cycle_length=2, factor=0.5.

    EMA(close, 2): alpha=2/3, SMA-seeded
      [None, 11, 11, 13, 13, 15, 15, 17]
      seed at i=1: (10+12)/2 = 11
      [2]: (2/3)*11 + (1/3)*11 = 11
      [3]: (2/3)*14 + (1/3)*11 = 13
      [4]: (2/3)*13 + (1/3)*13 = 13
      [5]: (2/3)*16 + (1/3)*13 = 15
      [6]: (2/3)*15 + (1/3)*15 = 15
      [7]: (2/3)*18 + (1/3)*15 = 17

    EMA(close, 3): alpha=0.5, SMA-seeded
      seed at i=2: (10+12+11)/3 = 11
      [3]: 0.5*14 + 0.5*11 = 12.5
      [4]: 0.5*13 + 0.5*12.5 = 12.75
      [5]: 0.5*16 + 0.5*12.75 = 14.375
      [6]: 0.5*15 + 0.5*14.375 = 14.6875
      [7]: 0.5*18 + 0.5*14.6875 = 16.34375

    MACD = EMA(2) - EMA(3):
      [None, None, 0, 0.5, 0.25, 0.625, 0.3125, 0.65625]

    stoch1 (cycle=2 windows on MACD):
      i=3: window [0, 0.5] → low=0, high=0.5 → stoch1[3] = 100
      i=4: window [0.5, 0.25] → low=0.25, high=0.5 → stoch1[4] = 0
      i=5: window [0.25, 0.625] → stoch1[5] = 100
      i=6: window [0.625, 0.3125] → stoch1[6] = 0
      i=7: window [0.3125, 0.65625] → stoch1[7] = 100

    smooth1 (factor=0.5, init to first non-None):
      i=3: smooth1[3] = 100 (init)
      i=4: smooth1[4] = 100 + 0.5*(0 - 100) = 50
      i=5: smooth1[5] = 50 + 0.5*(100 - 50) = 75
      i=6: smooth1[6] = 75 + 0.5*(0 - 75) = 37.5
      i=7: smooth1[7] = 37.5 + 0.5*(100 - 37.5) = 68.75

    stoch2 (cycle=2 windows on smooth1):
      i=4: window [100, 50] → stoch2[4] = (50-50)/(100-50)*100 = 0
      i=5: window [50, 75] → stoch2[5] = (75-50)/(75-50)*100 = 100
      i=6: window [75, 37.5] → stoch2[6] = (37.5-37.5)/(75-37.5)*100 = 0
      i=7: window [37.5, 68.75] → stoch2[7] = (68.75-37.5)/(68.75-37.5)*100 = 100

    stc (factor=0.5, init to first non-None stoch2):
      i=4: stc[4] = 0 (init)
      i=5: stc[5] = 0 + 0.5*(100 - 0) = 50
      i=6: stc[6] = 50 + 0.5*(0 - 50) = 25
      i=7: stc[7] = 25 + 0.5*(100 - 25) = 62.5

    Expected STC = [None, None, None, None, 0, 50, 25, 62.5]
    """
    closes = [10.0, 12.0, 11.0, 14.0, 13.0, 16.0, 15.0, 18.0]
    out = schaff_trend_cycle(
        closes,
        fast_length=2,
        slow_length=3,
        cycle_length=2,
        factor=0.5,
    )
    for i in range(4):
        assert out[i] is None, f"STC[{i}] should be None"
    assert out[4] == pytest.approx(0.0, abs=1e-9)
    assert out[5] == pytest.approx(50.0, abs=1e-9)
    assert out[6] == pytest.approx(25.0, abs=1e-9)
    assert out[7] == pytest.approx(62.5, abs=1e-9)


# ── Reference test ─────────────────────────────────────────────────────


def test_stc_matches_explicit_recomputation() -> None:
    """Explicit re-implementation of the algorithm matches our output."""
    import random

    rng = random.Random(101)
    n = 80
    closes = [100.0 + rng.uniform(-5, 5) for _ in range(n)]

    fast = 3
    slow = 5
    cycle = 3
    factor = 0.5
    out = schaff_trend_cycle(closes, fast, slow, cycle, factor)

    # Recompute reference using the same algorithm
    from app.strategy_engine.indicators.calculations.ema import ema as _ema

    e_fast = _ema(closes, fast)
    e_slow = _ema(closes, slow)
    macd: list[float | None] = [None] * n
    for i in range(n):
        if e_fast[i] is not None and e_slow[i] is not None:
            macd[i] = e_fast[i] - e_slow[i]  # type: ignore[operator]

    def _stoch(series, cy):
        m = len(series)
        result: list[float | None] = [None] * m
        prev = None
        for t in range(m):
            if series[t] is None:
                continue
            start = t - cy + 1
            if start < 0:
                continue
            w = series[start : t + 1]
            if any(v is None for v in w):
                continue
            ll = min(w)
            hh = max(w)
            if hh == ll:
                result[t] = prev
            else:
                result[t] = 100 * (series[t] - ll) / (hh - ll)
                prev = result[t]
        return result

    def _smooth(series, fac):
        m = len(series)
        result: list[float | None] = [None] * m
        state = None
        for t in range(m):
            if series[t] is None:
                continue
            if state is None:
                state = series[t]
            else:
                state = state + fac * (series[t] - state)
            result[t] = state
        return result

    expected = _smooth(_stoch(_smooth(_stoch(macd, cycle), factor), cycle), factor)

    for i in range(n):
        if expected[i] is None:
            assert out[i] is None
        else:
            assert out[i] == pytest.approx(expected[i], abs=1e-9), f"i={i}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_stc_empty_input() -> None:
    assert schaff_trend_cycle([]) == []


def test_stc_too_short_returns_all_none() -> None:
    """Series shorter than slow_length ⇒ MACD never defined ⇒ all None."""
    out = schaff_trend_cycle([1.0, 2.0, 3.0])  # defaults need 50+
    assert all(v is None for v in out)


def test_stc_fast_ge_slow_raises() -> None:
    with pytest.raises(ValueError, match="fast_length"):
        schaff_trend_cycle([1.0] * 100, fast_length=50, slow_length=50)


def test_stc_invalid_factor_raises() -> None:
    with pytest.raises(ValueError, match="factor"):
        schaff_trend_cycle([1.0] * 100, factor=0)
    with pytest.raises(ValueError, match="factor"):
        schaff_trend_cycle([1.0] * 100, factor=1.5)


def test_stc_constant_series_handles_zero_denom() -> None:
    """Constant series ⇒ MACD = 0 ⇒ stoch denominator 0 ⇒ carry-forward
    (initially None, stays None until the algorithm seeds)."""
    closes = [10.0] * 80
    out = schaff_trend_cycle(closes)
    # All flat ⇒ first stoch is None throughout ⇒ STC is all None.
    assert all(v is None for v in out)
