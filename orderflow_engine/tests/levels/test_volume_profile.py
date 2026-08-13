"""Hand-computed volume profile: bins, POC, VAH/VAL, HVN/LVN (Module R4)."""

from __future__ import annotations

from levels.volume_profile import VolumeProfile
from tests.levels import fixtures as F


def _profile():
    p = VolumeProfile(bin_size=5.0)
    p.on_trade(F.trade(100.0, 10))   # bin 100
    p.on_trade(F.trade(106.0, 6))    # bin 105
    p.on_trade(F.trade(111.0, 4))    # bin 110
    return p


def test_binning_and_poc():
    p = _profile()
    r = p.result()
    assert r.bins == {100.0: 10, 105.0: 6, 110.0: 4}
    assert r.total_volume == 20
    assert r.poc == 100.0            # heaviest bin


def test_value_area_expands_to_70pct():
    r = _profile().result(value_area_pct=0.70)   # target 14: POC 10 + up 6 = 16
    assert r.val == 100.0 and r.vah == 105.0     # bin 110 excluded


def test_hvn_lvn_inert_by_default():
    r = _profile().result()          # thresholds 0 -> inert
    assert r.hvn == [] and r.lvn == []


def test_hvn_lvn_when_calibrated():
    r = _profile().result(hvn_threshold=8, lvn_threshold=5)
    assert r.hvn == [100.0]          # only bin 100 (vol 10) >= 8
    assert r.lvn == [110.0]          # only bin 110 (vol 4) <= 5


def test_empty_profile_is_safe():
    r = VolumeProfile(5.0).result()
    assert r.poc is None and r.total_volume == 0


def test_bin_edges_floor_to_lower_edge():
    p = VolumeProfile(5.0)
    p.on_trade(F.trade(104.99, 1))   # -> bin 100
    p.on_trade(F.trade(105.0, 1))    # -> bin 105
    assert set(p.result().bins) == {100.0, 105.0}
