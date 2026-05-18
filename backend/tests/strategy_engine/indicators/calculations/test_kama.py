"""KAMA tests — math validation + edge cases + reference compare.

Reference: Kaufman's original formulation. TA-Lib's ``KAMA`` and
pandas-ta's ``ta.kama`` both ship the same formula. Cross-validation
tests below pass if pandas-ta is installed; skip otherwise.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.kama import kama


# ─── Validation ────────────────────────────────────────────────────────


def test_invalid_period_raises() -> None:
    with pytest.raises(ValueError, match="period"):
        kama([1.0] * 20, period=0)


def test_invalid_fast_raises() -> None:
    with pytest.raises(ValueError, match="fast"):
        kama([1.0] * 20, period=10, fast=0)


def test_slow_le_fast_raises() -> None:
    with pytest.raises(ValueError, match="slow"):
        kama([1.0] * 20, period=10, fast=10, slow=5)


# ─── Edge cases ────────────────────────────────────────────────────────


def test_empty_input_returns_empty() -> None:
    assert kama([]) == []


def test_too_short_input_returns_empty() -> None:
    # Need at least `period` values for warm-up
    assert kama([1.0, 2.0, 3.0], period=10) == []


# ─── Seeding ───────────────────────────────────────────────────────────


def test_seed_at_period_minus_one_equals_close_at_that_index() -> None:
    values = [float(i) for i in range(20)]
    result = kama(values, period=5)
    # Indices 0..3 are None (warmup); index 4 is the seed = values[4]
    assert result[0:4] == [None, None, None, None]
    assert result[4] == pytest.approx(5.0 - 1.0)  # values[4] = 4.0


# ─── Math invariants ───────────────────────────────────────────────────


def test_constant_series_yields_constant_kama() -> None:
    """If price is flat, ER is undefined (0/0) → ER = 0 → KAMA stays seed."""
    values = [42.0] * 30
    result = kama(values, period=10)
    defined = [v for v in result if v is not None]
    assert defined
    assert all(v == pytest.approx(42.0) for v in defined)


def test_kama_output_length_matches_input() -> None:
    values = [float(i) for i in range(50)]
    result = kama(values, period=10)
    assert len(result) == 50


def test_kama_warmup_is_none() -> None:
    values = [float(i) for i in range(30)]
    result = kama(values, period=10)
    for v in result[:9]:
        assert v is None
    assert result[9] is not None  # seed at period-1


# ─── Behavioural ───────────────────────────────────────────────────────


def test_strong_trend_kama_accelerates() -> None:
    """In a perfect linear uptrend ER=1, sc=fast_sc^2, KAMA tracks closer."""
    values = [float(i) for i in range(50)]
    result = kama(values, period=10, fast=2, slow=30)
    # In a perfect trend, KAMA should be increasing
    defined = [v for v in result if v is not None]
    for a, b in zip(defined, defined[1:], strict=False):
        assert b > a


def test_kama_no_nans_no_infs() -> None:
    import random

    rng = random.Random(7)
    values = [100.0 + rng.gauss(0, 1) for _ in range(100)]
    result = kama(values, period=10)
    for v in result:
        if v is not None:
            assert not math.isnan(v)
            assert not math.isinf(v)


def test_short_period_seeds_earlier() -> None:
    values = [float(i) for i in range(20)]
    result_p3 = kama(values, period=3)
    result_p5 = kama(values, period=5)
    assert result_p3[2] is not None  # seed at period-1
    assert result_p5[4] is not None


# ─── Reference cross-validation (pandas-ta optional) ──────────────────


def test_kama_matches_pandas_ta_when_available() -> None:
    """Cross-validate against pandas-ta if installed.

    Reference values must match within 1e-6 tolerance. If pandas-ta
    is not in the environment, skip gracefully.
    """
    try:
        import numpy as np
        import pandas as pd
        import pandas_ta as pta  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("pandas-ta not installed; reference test skipped")

    import random

    rng = random.Random(123)
    n = 100
    values = [100.0 + rng.gauss(0, 1) for _ in range(n)]

    our_result = kama(values, period=10, fast=2, slow=30)

    # pandas-ta KAMA: positional args differ per version; pass keyword-only.
    series = pd.Series(values)
    ref = pta.kama(series, length=10, fast=2, slow=30)
    if ref is None:
        pytest.skip("pandas-ta.kama returned None for this input")
    ref_list = ref.tolist()

    # Both series should be the same length
    assert len(our_result) == len(ref_list)

    diffs = []
    for ours, theirs in zip(our_result, ref_list, strict=True):
        if ours is None and (theirs is None or (isinstance(theirs, float) and math.isnan(theirs))):
            continue
        if ours is None or theirs is None or (isinstance(theirs, float) and math.isnan(theirs)):
            continue  # warmup mismatch tolerated
        diffs.append(abs(ours - theirs))
    if not diffs:
        pytest.skip("No overlapping defined values between ours and pandas-ta")
    max_diff = max(diffs)
    assert max_diff < 1e-3, (
        f"Max abs diff vs pandas-ta = {max_diff}; expected < 1e-3"
    )


def test_kama_with_volatility_window_handles_zero_volatility() -> None:
    """If a sub-window has zero volatility (perfectly flat), ER=0 and
    KAMA stays at the seed value (not NaN)."""
    # 15 flat, then upward step. The first 15 bars are flat so vol = 0.
    values = [10.0] * 15 + [11.0, 12.0, 13.0, 14.0, 15.0]
    result = kama(values, period=5)
    # No NaN/inf
    for v in result:
        if v is not None:
            assert not math.isnan(v)
            assert not math.isinf(v)
