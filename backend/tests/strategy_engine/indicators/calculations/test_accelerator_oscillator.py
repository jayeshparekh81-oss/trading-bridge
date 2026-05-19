"""Accelerator Oscillator (AC) calculation tests.

Test convention: Bill Williams' AC = AO - SMA(AO, ac_smoothing).
AO itself is the existing awesome_oscillator calc. First defined
position is at index (ao_slow - 1) + (ac_smoothing - 1).
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.accelerator_oscillator import (
    accelerator_oscillator,
)
from app.strategy_engine.indicators.calculations.awesome_oscillator import (
    awesome_oscillator,
)


# ── Property tests ─────────────────────────────────────────────────────


def test_ac_output_length_matches_input() -> None:
    """Output length = input length; warm-up is None-filled."""
    n = 50
    highs = [100.0 + i for i in range(n)]
    lows = [99.0 + i for i in range(n)]
    out = accelerator_oscillator(highs, lows)  # defaults
    assert len(out) == n
    # First defined index: ao_slow-1 + ac_smoothing-1 = 33 + 4 = 37
    for i in range(37):
        assert out[i] is None, f"Expected None at i={i}, got {out[i]}"
    for v in out[37:]:
        assert isinstance(v, float)


def test_ac_constant_series_is_zero() -> None:
    """Constant H+L series ⇒ AO=0 ⇒ AC=0 once warmed up."""
    n = 60
    highs = [10.0] * n
    lows = [9.0] * n  # constant median = 9.5
    out = accelerator_oscillator(highs, lows)
    first_defined = 34 - 1 + 5 - 1  # = 37
    for v in out[first_defined:]:
        assert v == pytest.approx(0.0, abs=1e-12)


# ── Hand-computed test (small custom params for tractable math) ───────


def test_ac_hand_computed_with_small_params() -> None:
    """Hand-computed with ao_fast=2, ao_slow=3, ac_smoothing=2.

    median[i] = (high[i] + low[i]) / 2 — use highs=[10,11,12,13,14],
    lows=[10,11,12,13,14] so median = [10,11,12,13,14] (clean integers).

    AO with fast=2, slow=3:
        i=0: None (slow warm-up)
        i=1: None (slow needs 3 bars)
        i=2: SMA(2, [11,12]) - SMA(3, [10,11,12])
           = 11.5 - 11.0 = 0.5
        i=3: SMA(2, [12,13]) - SMA(3, [11,12,13])
           = 12.5 - 12.0 = 0.5
        i=4: SMA(2, [13,14]) - SMA(3, [12,13,14])
           = 13.5 - 13.0 = 0.5

    AC = AO - SMA(2, AO):
        i=0,1: None (AO warm-up)
        i=2: None (SMA(AO,2) needs 2 non-None AO values; only 1 yet)
        i=3: AO[3] - SMA(2, [AO[2], AO[3]]) = 0.5 - (0.5+0.5)/2 = 0.0
        i=4: AO[4] - SMA(2, [AO[3], AO[4]]) = 0.5 - 0.5 = 0.0

    All AO values equal ⇒ all AC values are 0 once warmed up.
    """
    highs = [10.0, 11.0, 12.0, 13.0, 14.0]
    lows = [10.0, 11.0, 12.0, 13.0, 14.0]
    out = accelerator_oscillator(highs, lows, ao_fast=2, ao_slow=3, ac_smoothing=2)
    assert out[0] is None
    assert out[1] is None
    assert out[2] is None  # first SMA(AO,2) window has only 1 non-None AO
    assert out[3] == pytest.approx(0.0, abs=1e-12)
    assert out[4] == pytest.approx(0.0, abs=1e-12)


def test_ac_hand_computed_with_curvature() -> None:
    """A case where AO is NOT constant — so AC is non-zero.

    Use ao_fast=2, ao_slow=3, ac_smoothing=2.
    highs = [10, 11, 13, 16, 20]  (median accelerating)
    lows  = [10, 11, 13, 16, 20]

    median = [10,11,13,16,20]

    AO[2] = SMA(2,[11,13]) - SMA(3,[10,11,13]) = 12 - 11.333... = 0.6666...
    AO[3] = SMA(2,[13,16]) - SMA(3,[11,13,16]) = 14.5 - 13.333... = 1.1666...
    AO[4] = SMA(2,[16,20]) - SMA(3,[13,16,20]) = 18 - 16.333... = 1.6666...

    AC[3] = AO[3] - SMA(2,[AO[2],AO[3]]) = 1.1666... - (0.6666+1.1666)/2
          = 1.1666... - 0.9166... = 0.25
    AC[4] = AO[4] - SMA(2,[AO[3],AO[4]]) = 1.6666... - (1.1666+1.6666)/2
          = 1.6666... - 1.4166... = 0.25
    """
    highs = [10.0, 11.0, 13.0, 16.0, 20.0]
    lows = [10.0, 11.0, 13.0, 16.0, 20.0]
    out = accelerator_oscillator(highs, lows, ao_fast=2, ao_slow=3, ac_smoothing=2)
    assert out[3] == pytest.approx(0.25, abs=1e-9)
    assert out[4] == pytest.approx(0.25, abs=1e-9)


# ── Reference test (compose against awesome_oscillator manually) ───────


def test_ac_matches_explicit_ao_minus_sma_composition() -> None:
    """Recompute AC by hand from AO + manual SMA and compare."""
    import random

    rng = random.Random(99)
    n = 80
    highs = [100.0 + rng.uniform(-5, 5) for _ in range(n)]
    lows = [h - abs(rng.uniform(0.5, 2.0)) for h in highs]

    out = accelerator_oscillator(highs, lows)  # defaults

    ao = awesome_oscillator(highs, lows, fast=5, slow=34)
    expected: list[float | None] = [None] * n
    first_defined = 34 - 1 + 5 - 1  # = 37
    for i in range(first_defined, n):
        window = ao[i - 4 : i + 1]  # 5-bar AO window
        sma = sum(window) / 5  # type: ignore[arg-type]
        expected[i] = ao[i] - sma  # type: ignore[operator]

    for i in range(first_defined, n):
        assert out[i] == pytest.approx(expected[i], abs=1e-12), f"i={i}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_ac_empty_input() -> None:
    assert accelerator_oscillator([], []) == []


def test_ac_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        accelerator_oscillator([1.0, 2.0], [1.0])


def test_ac_too_short_returns_empty() -> None:
    """Series shorter than AO's warm-up ⇒ AO returns [] ⇒ AC returns []
    (matches Phase 1 ``period > len`` contract — short of warm-up = []).
    """
    out = accelerator_oscillator([1.0, 2.0, 3.0], [0.5, 1.5, 2.5])
    assert out == []


def test_ac_fast_ge_slow_raises() -> None:
    with pytest.raises(ValueError, match="ao_fast must be strictly less than ao_slow"):
        accelerator_oscillator([1.0] * 50, [0.5] * 50, ao_fast=10, ao_slow=10)


def test_ac_invalid_period_raises() -> None:
    with pytest.raises(ValueError):
        accelerator_oscillator([1.0] * 50, [0.5] * 50, ac_smoothing=0)
    with pytest.raises(ValueError):
        accelerator_oscillator([1.0] * 50, [0.5] * 50, ao_fast=-1)
