"""Swing Index — tests.

Locked variant: Wilder 1978, 3-branch R selection, limit_move T=1.0,
SI[0]=0 by convention, R==0 → SI=0.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.swing_index import swing_index


# ── Property tests ─────────────────────────────────────────────────────


def test_si_output_length_matches_input() -> None:
    n = 30
    O = H = L = C = [10.0] * n
    out = swing_index(O, H, L, C)
    assert len(out) == n


def test_si_first_bar_is_zero() -> None:
    O = [10.0, 11.0, 12.0]
    H = [10.5, 11.5, 12.5]
    L = [9.5, 10.5, 11.5]
    C = [10.2, 11.2, 12.2]
    out = swing_index(O, H, L, C)
    assert out[0] == 0.0


def test_si_flat_market_all_zeros() -> None:
    """All-equal OHLC ⇒ TR1=TR2=TR3=0 ⇒ R=0 ⇒ SI=0 throughout."""
    O = H = L = C = [10.0] * 20
    out = swing_index(O, H, L, C)
    assert out == [0.0] * 20


# ── Hand-computed test (3-branch coverage) ─────────────────────────────


def test_si_hand_computed_three_branches() -> None:
    """Hand-computed 3-bar example covering ELSE and ELIF branches.

    Bar 0: O=10, H=11, L=9, C=10.5
        SI[0] = 0 (convention; no prior bar)

    Bar 1: O=10.5, H=12, L=10, C=11. Prev: O=10, C=10.5.
        TR1 = |12-10.5| = 1.5
        TR2 = |10-10.5| = 0.5
        TR3 = |12-10|   = 2.0   ← largest
        ELSE branch:
            R = (12-10) + 0.25*(10.5-10) = 2 + 0.125 = 2.125
        N = (11-10.5) + 0.5*(11-10.5) + 0.25*(10.5-10)
          = 0.5 + 0.25 + 0.125 = 0.875
        K = max(1.5, 0.5) = 1.5
        SI[1] = 50 * (0.875/2.125) * (1.5/1.0)
              = 50 * (7/17) * (3/2)
              = 525/17  ≈ 30.882352...

    Bar 2: O=11, H=10.5, L=9.5, C=10. Prev: O=10.5, C=11.
        TR1 = |10.5-11| = 0.5
        TR2 = |9.5-11|  = 1.5    ← largest
        TR3 = |10.5-9.5| = 1.0
        ELIF branch (TR2 largest):
            R = (9.5-11) - 0.5*(10.5-11) + 0.25*(11-10.5)
              = -1.5 - (-0.25) + 0.125 = -1.5 + 0.25 + 0.125 = -1.125
        N = (10-11) + 0.5*(10-11) + 0.25*(11-10.5)
          = -1.0 + -0.5 + 0.125 = -1.375
        K = max(0.5, 1.5) = 1.5
        SI[2] = 50 * (-1.375 / -1.125) * (1.5/1.0)
              = 50 * (11/9) * (3/2)
              = 1650/18 = 275/3 ≈ 91.6666...
    """
    O = [10.0, 10.5, 11.0]
    H = [11.0, 12.0, 10.5]
    L = [9.0, 10.0, 9.5]
    C = [10.5, 11.0, 10.0]
    out = swing_index(O, H, L, C, limit_move=1.0)

    assert out[0] == 0.0
    assert out[1] == pytest.approx(525.0 / 17.0, abs=1e-9)
    assert out[2] == pytest.approx(275.0 / 3.0, abs=1e-9)


def test_si_first_branch_when_tr1_largest() -> None:
    """Force TR1 (|H - C_prev|) to be the strictly largest.

    Bar 1: O=10, H=20, L=9.9, C=15. Prev: O=10, C=10.
        TR1 = |20-10|  = 10.0  ← largest
        TR2 = |9.9-10| = 0.1
        TR3 = |20-9.9| = 10.1   ← actually larger!

    Hmm — need a case where TR1 > TR3.  Let's use:
    Bar 1: O=10, H=15, L=9.5, C=12. Prev: O=10, C=10.
        TR1 = |15-10|  = 5.0   ← largest
        TR2 = |9.5-10| = 0.5
        TR3 = |15-9.5| = 5.5   ← still larger.

    The only way TR1 > TR3 is if |H - C_prev| > |H - L|.
    That's only possible when C_prev < L (high gap up where prev close
    was below today's low). Use:
    Bar 1: O=15, H=15.5, L=14.5, C=15.2. Prev: O=10, C=10.
        TR1 = |15.5-10| = 5.5  ← largest
        TR2 = |14.5-10| = 4.5
        TR3 = |15.5-14.5| = 1.0
        IF branch:
            R = (15.5-10) - 0.5*(14.5-10) + 0.25*(10-10)
              = 5.5 - 2.25 + 0 = 3.25
        N = (15.2-10) + 0.5*(15.2-15) + 0.25*(10-10)
          = 5.2 + 0.1 + 0 = 5.3
        K = max(5.5, 4.5) = 5.5
        SI[1] = 50 * (5.3/3.25) * (5.5/1.0)
              = 50 * 1.6307... * 5.5
              ≈ 448.46...
    """
    O = [10.0, 15.0]
    H = [10.0, 15.5]
    L = [10.0, 14.5]
    C = [10.0, 15.2]
    out = swing_index(O, H, L, C, limit_move=1.0)
    expected = 50.0 * (5.3 / 3.25) * (5.5 / 1.0)
    assert out[1] == pytest.approx(expected, abs=1e-9)


# ── Reference test ─────────────────────────────────────────────────────


def test_si_matches_explicit_recomputation() -> None:
    """Recompute via explicit branch logic and compare."""
    import random

    rng = random.Random(33)
    n = 50
    O = [100.0]
    for _ in range(n - 1):
        O.append(O[-1] + rng.uniform(-2, 2))
    H = [o + abs(rng.uniform(0.1, 2.0)) for o in O]
    L = [o - abs(rng.uniform(0.1, 2.0)) for o in O]
    C = [rng.uniform(lo, hi) for hi, lo in zip(H, L)]

    out = swing_index(O, H, L, C, limit_move=1.0)

    for i in range(1, n):
        h, l, c, o = H[i], L[i], C[i], O[i]
        c_prev, o_prev = C[i - 1], O[i - 1]
        tr1 = abs(h - c_prev)
        tr2 = abs(l - c_prev)
        tr3 = abs(h - l)
        if tr1 >= tr2 and tr1 >= tr3:
            R = (h - c_prev) - 0.5 * (l - c_prev) + 0.25 * (c_prev - o_prev)
        elif tr2 >= tr1 and tr2 >= tr3:
            R = (l - c_prev) - 0.5 * (h - c_prev) + 0.25 * (c_prev - o_prev)
        else:
            R = (h - l) + 0.25 * (c_prev - o_prev)
        if R == 0.0:
            expected = 0.0
        else:
            N = (c - c_prev) + 0.5 * (c - o) + 0.25 * (c_prev - o_prev)
            K = max(tr1, tr2)
            expected = 50.0 * (N / R) * (K / 1.0)
        assert out[i] == pytest.approx(expected, abs=1e-9), f"i={i}"


# ── Edge case tests ────────────────────────────────────────────────────


def test_si_empty_input() -> None:
    assert swing_index([], [], [], []) == []


def test_si_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        swing_index([1.0, 2.0], [1.0], [1.0], [1.0])


def test_si_single_bar_returns_zero() -> None:
    out = swing_index([10.0], [11.0], [9.0], [10.5])
    assert out == [0.0]


def test_si_invalid_limit_move_raises() -> None:
    with pytest.raises(ValueError, match="limit_move"):
        swing_index([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0], limit_move=0)
    with pytest.raises(ValueError, match="limit_move"):
        swing_index([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0], limit_move=-1.0)


def test_si_zero_R_returns_zero() -> None:
    """If by some construction R = 0, SI should be 0 (not crash)."""
    # An all-zero series triggers R=0 from the start.
    O = H = L = C = [0.0, 0.0, 0.0]
    out = swing_index(O, H, L, C)
    assert out == [0.0, 0.0, 0.0]
