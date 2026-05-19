"""DMI +DI / -DI wrappers — tests.

dmi_plus and dmi_minus are thin wrappers around the existing adx()
calc, returning just the +DI or -DI series respectively.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.dmi_plus import dmi_plus
from app.strategy_engine.indicators.calculations.dmi_minus import dmi_minus
from app.strategy_engine.indicators.calculations.adx import adx


def test_dmi_plus_matches_adx_plus_di() -> None:
    """dmi_plus(...) byte-equals adx(...)[1]."""
    import random

    rng = random.Random(42)
    n = 40
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(closes[-1] + rng.uniform(-1, 1))
    highs = [c + abs(rng.uniform(0.1, 1.0)) for c in closes]
    lows = [c - abs(rng.uniform(0.1, 1.0)) for c in closes]

    _, expected_plus, _ = adx(highs, lows, closes, period=14)
    out = dmi_plus(highs, lows, closes, period=14)
    assert out == expected_plus


def test_dmi_minus_matches_adx_minus_di() -> None:
    """dmi_minus(...) byte-equals adx(...)[2]."""
    import random

    rng = random.Random(99)
    n = 40
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(closes[-1] + rng.uniform(-1, 1))
    highs = [c + abs(rng.uniform(0.1, 1.0)) for c in closes]
    lows = [c - abs(rng.uniform(0.1, 1.0)) for c in closes]

    _, _, expected_minus = adx(highs, lows, closes, period=14)
    out = dmi_minus(highs, lows, closes, period=14)
    assert out == expected_minus


def test_dmi_plus_strong_uptrend_dominates() -> None:
    """In a sustained uptrend, +DI > -DI for most defined bars."""
    n = 40
    closes = [100.0 + i for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    plus = dmi_plus(highs, lows, closes, period=14)
    minus = dmi_minus(highs, lows, closes, period=14)
    # Past warm-up, +DI should be strictly > -DI on a clean uptrend
    for i in range(20, n):
        if plus[i] is not None and minus[i] is not None:
            assert plus[i] > minus[i], f"i={i}: +DI={plus[i]} -DI={minus[i]}"


def test_dmi_plus_empty_input() -> None:
    assert dmi_plus([], [], []) == []
    assert dmi_minus([], [], []) == []


def test_dmi_plus_invalid_period_raises() -> None:
    with pytest.raises(ValueError):
        dmi_plus([1.0] * 20, [0.5] * 20, [0.7] * 20, period=0)
    with pytest.raises(ValueError):
        dmi_minus([1.0] * 20, [0.5] * 20, [0.7] * 20, period=0)


def test_dmi_plus_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        dmi_plus([1.0, 2.0], [0.5], [0.7, 0.8])
    with pytest.raises(ValueError):
        dmi_minus([1.0, 2.0], [0.5], [0.7, 0.8])
