"""Hand-computed VWAP + volume-weighted SD bands (Module R4)."""

from __future__ import annotations

import pytest

from levels.vwap import SessionVWAP
from tests.levels import fixtures as F


def test_vwap_and_bands_exact():
    v = SessionVWAP([1.0, 2.0])
    v.on_trade(F.trade(100.0, 10))
    v.on_trade(F.trade(110.0, 10))
    # Σpv=2100 Σv=20 -> vwap 105; Σpv2=221000 -> var=11050-11025=25 -> std 5
    assert v.vwap == 105.0
    assert v.std == 5.0
    snap = v.snapshot()
    assert snap.bands["upper_1"] == 110.0 and snap.bands["lower_1"] == 100.0
    assert snap.bands["upper_2"] == 115.0 and snap.bands["lower_2"] == 95.0
    assert snap.cum_volume == 20


def test_vwap_weights_by_size():
    v = SessionVWAP()
    v.on_trade(F.trade(100.0, 1))
    v.on_trade(F.trade(200.0, 3))    # heavier -> vwap pulled toward 200
    assert v.vwap == pytest.approx((100 + 600) / 4)   # 175


def test_empty_snapshot_is_none():
    assert SessionVWAP().snapshot() is None


def test_zero_variance_gives_zero_bands():
    v = SessionVWAP([1.0])
    v.on_trade(F.trade(100.0, 5))
    v.on_trade(F.trade(100.0, 5))
    assert v.std == 0.0
    snap = v.snapshot()
    assert snap.bands["upper_1"] == 100.0 == snap.bands["lower_1"]
