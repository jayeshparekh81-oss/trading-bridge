"""PCR, max-pain, basis, ATM-IV (Module R5) — hand-verified."""

from __future__ import annotations

import pytest

from chain import analytics


def _strikes():
    return [
        {"right": "CE", "strike": 100, "oi": 10, "volume": 5, "ltp": 3.0, "iv": 0.20},
        {"right": "CE", "strike": 110, "oi": 5, "volume": 2, "ltp": 1.0, "iv": 0.22},
        {"right": "PE", "strike": 100, "oi": 10, "volume": 8, "ltp": 3.0, "iv": 0.24},
        {"right": "PE", "strike": 90, "oi": 5, "volume": 3, "ltp": 1.0, "iv": 0.26},
    ]


def test_pcr_oi_and_volume():
    s = _strikes()
    assert analytics.pcr_oi(s) == pytest.approx(15 / 15)      # PE 15 / CE 15 = 1.0
    assert analytics.pcr_volume(s) == pytest.approx(11 / 7)   # PE 11 / CE 7


def test_max_pain():
    # payout min at 100 (=0); at 90 and 110 it's 100 -> max pain = 100
    assert analytics.max_pain(_strikes()) == 100


def test_max_pain_shifts_with_oi():
    s = [
        {"right": "CE", "strike": 100, "oi": 1},
        {"right": "PE", "strike": 100, "oi": 1},
        {"right": "PE", "strike": 110, "oi": 100},   # huge put OI at 110
    ]
    # heavy put writers at 110 pull max pain up toward 110
    assert analytics.max_pain(s) == 110


def test_basis_and_annualized():
    assert analytics.basis(105.0, 100.0) == 5.0
    ann = analytics.annualized_basis(105.0, 100.0, days_to_expiry=30, day_count=365)
    assert ann == pytest.approx(0.05 * (365 / 30))


def test_atm_iv_picks_nearest_strike():
    s = _strikes()
    # spot 101 -> ATM strike 100 -> avg(CE 0.20, PE 0.24) = 0.22
    assert analytics.atm_strike(s, 101) == 100
    assert analytics.atm_iv(s, 101) == pytest.approx(0.22)


def test_pcr_none_when_no_ce():
    assert analytics.pcr_oi([{"right": "PE", "strike": 100, "oi": 5}]) is None


def test_atm_iv_none_without_spot():
    assert analytics.atm_iv(_strikes(), None) is None
