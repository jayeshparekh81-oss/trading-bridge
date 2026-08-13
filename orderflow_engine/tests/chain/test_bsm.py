"""Hand-computed Black-Scholes price / IV / Greeks + edge cases (Module R5)."""

from __future__ import annotations

import pytest

from chain.bsm import bs_price, greeks, implied_vol


# Reference point: S=K=100, T=1, r=0, sigma=0.2 (all hand-computable)
def test_atm_call_price():
    assert bs_price(100, 100, 1, 0, 0.2, "CE") == pytest.approx(7.9656, abs=1e-3)


def test_put_call_parity():
    c = bs_price(100, 100, 1, 0, 0.2, "CE")
    p = bs_price(100, 100, 1, 0, 0.2, "PE")
    assert c - p == pytest.approx(100 - 100 * 1.0, abs=1e-6)   # S - K e^{-rT}, r=0


def test_iv_inverts_price():
    price = bs_price(100, 100, 1, 0, 0.2, "CE")
    assert implied_vol(price, 100, 100, 1, 0, "CE") == pytest.approx(0.2, abs=1e-4)


def test_greeks_reference_values():
    g = greeks(100, 100, 1, 0, 0.2, "CE")
    assert g["delta"] == pytest.approx(0.539828, abs=1e-4)
    assert g["gamma"] == pytest.approx(0.0198476, abs=1e-5)
    assert g["vega"] == pytest.approx(39.6953, abs=1e-2)
    assert g["theta"] == pytest.approx(-3.9695, abs=1e-2)


def test_put_delta_is_negative():
    g = greeks(100, 100, 1, 0, 0.2, "PE")
    assert -1.0 < g["delta"] < 0.0


def test_expired_option_iv_none():
    assert implied_vol(5.0, 100, 100, 0.0, 0, "CE") is None
    assert greeks(100, 100, 0.0, 0, 0.2, "CE") is None


def test_price_below_intrinsic_iv_none():
    # deep ITM call with price below intrinsic (stale/arb) -> no IV
    assert implied_vol(1.0, 150, 100, 1, 0, "CE") is None


def test_price_above_underlying_iv_none():
    assert implied_vol(101.0, 100, 100, 1, 0, "CE") is None


def test_deep_otm_still_solvable_when_priced():
    price = bs_price(100, 130, 0.1, 0, 0.3, "CE")
    if price > 0:
        iv = implied_vol(price, 100, 130, 0.1, 0, "CE")
        assert iv == pytest.approx(0.3, abs=1e-3)
