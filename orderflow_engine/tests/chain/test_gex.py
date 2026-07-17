"""GEX proxy: signed per-strike, net, gamma-flip (Module R5)."""

from __future__ import annotations

import pytest

from chain import gex


def test_strike_gex_sign():
    assert gex.strike_gex(0.04, 100, 1, "CE") == pytest.approx(4.0)     # call positive
    assert gex.strike_gex(0.04, 100, 1, "PE") == pytest.approx(-4.0)    # put negative


def test_net_gex():
    strikes = [
        {"right": "PE", "strike": 100, "oi": 100, "gamma": 0.04},   # -4
        {"right": "CE", "strike": 110, "oi": 100, "gamma": 0.10},   # +10
    ]
    assert gex.net_gex(strikes, 1) == pytest.approx(6.0)


def test_gamma_flip_interpolates_zero_crossing():
    strikes = [
        {"right": "PE", "strike": 100, "oi": 100, "gamma": 0.04},   # cum -4 at 100
        {"right": "CE", "strike": 110, "oi": 100, "gamma": 0.10},   # cum +6 at 110
    ]
    # flip = 100 + (0-(-4))/(6-(-4)) * (110-100) = 104
    assert gex.gamma_flip(strikes, 1) == pytest.approx(104.0)


def test_no_flip_when_never_crosses():
    strikes = [
        {"right": "CE", "strike": 100, "oi": 100, "gamma": 0.04},
        {"right": "CE", "strike": 110, "oi": 100, "gamma": 0.10},
    ]
    assert gex.gamma_flip(strikes, 1) is None      # cumulative stays positive


def test_regime_flag_inert_at_zero_threshold():
    assert gex.regime_flag(1e9, 0) is None         # INERT until calibrated
    assert gex.regime_flag(1e9, 1e6) == "positive_gamma"
    assert gex.regime_flag(-1e9, 1e6) == "negative_gamma"


# --- LOT-SIZE INVARIANTS (2026-07-17) ---------------------------------------------
# The lot-size bug proved these hold: contract_size is a POSITIVE CONSTANT SCALE on every
# strike's GEX, so net_gex SIGN and gamma_flip LEVEL are invariant to it (only the
# net_gex MAGNITUDE moves). Pin them so nobody "optimises" a lot multiplier into a place
# that would silently break sign or flip.
_MIXED = [
    {"right": "PE", "strike": 100, "oi": 120, "gamma": 0.04},
    {"right": "CE", "strike": 110, "oi": 90, "gamma": 0.10},
    {"right": "PE", "strike": 120, "oi": 200, "gamma": 0.03},
    {"right": "CE", "strike": 130, "oi": 150, "gamma": 0.06},
]


@pytest.mark.parametrize("k", [2, 3, 30, 65, 75, 1000])
def test_net_gex_sign_invariant_to_positive_scale(k):
    base = gex.net_gex(_MIXED, 1)
    scaled = gex.net_gex(_MIXED, k)
    assert (scaled > 0) == (base > 0) and (scaled < 0) == (base < 0)   # SIGN preserved
    assert scaled == pytest.approx(base * k)                          # magnitude scales by k


@pytest.mark.parametrize("k", [2, 3, 30, 65, 75, 1000])
def test_gamma_flip_level_invariant_to_positive_scale(k):
    base = gex.gamma_flip(_MIXED, 1)
    assert base is not None
    assert gex.gamma_flip(_MIXED, k) == pytest.approx(base)           # LEVEL exactly unchanged


def test_the_bug_would_have_moved_only_magnitude():
    """A NIFTY 75-vs-65 error: magnitude off by 75/65, sign + flip identical."""
    wrong = gex.net_gex(_MIXED, 75)
    right = gex.net_gex(_MIXED, 65)
    assert (wrong > 0) == (right > 0)                                 # same sign
    assert wrong == pytest.approx(right * 75 / 65)                    # ~15.4% inflated
    assert gex.gamma_flip(_MIXED, 75) == pytest.approx(gex.gamma_flip(_MIXED, 65))
