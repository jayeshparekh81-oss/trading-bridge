"""Accumulative Swing Index — tests.

ASI = cumulative sum of SI. Built on the locked swing_index() calc.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.accumulative_swing_index import (
    accumulative_swing_index,
)
from app.strategy_engine.indicators.calculations.swing_index import swing_index


# ── Property tests ─────────────────────────────────────────────────────


def test_asi_output_length_matches_input() -> None:
    n = 20
    O = [10.0] * n
    H = [11.0] * n
    L = [9.0] * n
    C = [10.5] * n
    out = accumulative_swing_index(O, H, L, C)
    assert len(out) == n


def test_asi_flat_market_all_zeros() -> None:
    """Flat market → SI all 0 → ASI all 0."""
    n = 20
    O = H = L = C = [10.0] * n
    out = accumulative_swing_index(O, H, L, C)
    assert out == [0.0] * n


def test_asi_is_cumulative_sum_of_si() -> None:
    """For any input, ASI[t] should equal sum(SI[0..t])."""
    import random

    rng = random.Random(17)
    n = 30
    O = [100.0]
    for _ in range(n - 1):
        O.append(O[-1] + rng.uniform(-1, 1))
    H = [o + abs(rng.uniform(0.1, 1.0)) for o in O]
    L = [o - abs(rng.uniform(0.1, 1.0)) for o in O]
    C = [rng.uniform(lo, hi) for hi, lo in zip(H, L)]

    si = swing_index(O, H, L, C, limit_move=1.0)
    asi = accumulative_swing_index(O, H, L, C, limit_move=1.0)

    running = 0.0
    for i in range(n):
        running += si[i]
        assert asi[i] == pytest.approx(running, abs=1e-9), f"i={i}"


# ── Hand-computed test ────────────────────────────────────────────────


def test_asi_hand_computed_three_bars() -> None:
    """Reuse the hand-computed SI example from test_swing_index.py.

    O = [10, 10.5, 11]
    H = [11, 12, 10.5]
    L = [9, 10, 9.5]
    C = [10.5, 11, 10]

    From hand-computed SI verification:
        SI[0] = 0
        SI[1] = 525/17  (≈ 30.882352)
        SI[2] = 275/3   (≈ 91.666666)

    ASI:
        ASI[0] = 0
        ASI[1] = 0 + 525/17 = 525/17
        ASI[2] = 525/17 + 275/3 = (525*3 + 275*17) / (17*3) = (1575 + 4675) / 51 = 6250/51
    """
    O = [10.0, 10.5, 11.0]
    H = [11.0, 12.0, 10.5]
    L = [9.0, 10.0, 9.5]
    C = [10.5, 11.0, 10.0]
    out = accumulative_swing_index(O, H, L, C, limit_move=1.0)

    assert out[0] == 0.0
    assert out[1] == pytest.approx(525.0 / 17.0, abs=1e-9)
    assert out[2] == pytest.approx(6250.0 / 51.0, abs=1e-9)


# ── Reference test ─────────────────────────────────────────────────────


def test_asi_matches_running_sum_of_swing_index() -> None:
    """Independent recomputation: build SI manually then sum."""
    import random

    rng = random.Random(91)
    n = 50
    O = [100.0]
    for _ in range(n - 1):
        O.append(O[-1] + rng.uniform(-2, 2))
    H = [o + abs(rng.uniform(0.1, 2.0)) for o in O]
    L = [o - abs(rng.uniform(0.1, 2.0)) for o in O]
    C = [rng.uniform(lo, hi) for hi, lo in zip(H, L)]

    si_ref = swing_index(O, H, L, C, limit_move=1.0)
    asi = accumulative_swing_index(O, H, L, C, limit_move=1.0)

    cumsum = 0.0
    for i in range(n):
        cumsum += si_ref[i]
        assert asi[i] == pytest.approx(cumsum, abs=1e-9)


# ── Edge case tests ────────────────────────────────────────────────────


def test_asi_empty_input() -> None:
    assert accumulative_swing_index([], [], [], []) == []


def test_asi_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        accumulative_swing_index([1.0, 2.0], [1.0], [1.0], [1.0])


def test_asi_single_bar_is_zero() -> None:
    """Single bar → SI[0] = 0 → ASI[0] = 0."""
    out = accumulative_swing_index([10.0], [11.0], [9.0], [10.5])
    assert out == [0.0]


def test_asi_invalid_limit_move_raises() -> None:
    with pytest.raises(ValueError, match="limit_move"):
        accumulative_swing_index([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0], limit_move=0)
