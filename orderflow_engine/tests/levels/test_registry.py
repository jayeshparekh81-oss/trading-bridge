"""LevelRegistry: nearest-level query + serialization (Module R4)."""

from __future__ import annotations

import json

from levels.registry import LevelRegistry


def _reg():
    r = LevelRegistry(61093, "NIFTY_FUT", "2026-07-13")
    r.add("VWAP", 105.0, {"std": 5.0})
    r.add("POC", 100.0)
    r.add("PIVOT_R1", 110.0)
    r.add("PDL", 92.0)
    return r


def test_distance_to_nearest_overall():
    n = _reg().distance_to_nearest(103.0)
    assert n["level_type"] == "VWAP"          # 105 is closest to 103
    assert n["signed_distance"] == 2.0        # level above price
    assert n["abs_distance"] == 2.0


def test_distance_below_price_is_negative():
    n = _reg().distance_to_nearest(101.0)
    assert n["level_type"] == "POC"           # 100 closest to 101
    assert n["signed_distance"] == -1.0       # level below price


def test_types_filter():
    n = _reg().distance_to_nearest(103.0, types=["POC", "PDL"])
    assert n["level_type"] == "POC"           # VWAP excluded by filter


def test_empty_registry_returns_none():
    assert LevelRegistry(1, "X", "d").distance_to_nearest(100.0) is None


def test_none_price_is_ignored():
    r = LevelRegistry(1, "X", "d")
    r.add("VAH", None)                         # e.g. empty profile
    assert r.levels() == []


def test_to_rows_sorted_with_metadata_json():
    rows = _reg().to_rows()
    assert [r["price"] for r in rows] == [92.0, 100.0, 105.0, 110.0]   # sorted
    vwap_row = next(r for r in rows if r["level_type"] == "VWAP")
    assert json.loads(vwap_row["metadata"]) == {"std": 5.0}
    assert all(r["security_id"] == 61093 for r in rows)
