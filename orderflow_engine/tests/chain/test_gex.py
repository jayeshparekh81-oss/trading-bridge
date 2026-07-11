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
