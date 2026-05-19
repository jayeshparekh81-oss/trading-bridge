"""Volume Profile — tests.

Locked variant: bins=24, lookback=100, value_area_pct=0.7,
typical_price single-bin distribution, POC = single max bin.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.volume_profile import (
    volume_profile,
)


# ── Property tests ─────────────────────────────────────────────────────


def test_vp_returns_dict_with_required_keys() -> None:
    n = 20
    highs = [10.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    closes = [9.5 + i * 0.1 for i in range(n)]
    vols = [100.0] * n
    out = volume_profile(highs, lows, closes, vols, bins=5, lookback=20)
    assert "bins" in out and "poc" in out and "vah" in out and "val" in out
    assert "total_volume" in out
    assert len(out["bins"]) == 5
    for b in out["bins"]:
        assert {"price_lo", "price_hi", "volume"} <= b.keys()


def test_vp_total_volume_equals_sum() -> None:
    highs = [10.0, 12.0, 14.0]
    lows = [5.0, 7.0, 9.0]
    closes = [8.0, 10.0, 12.0]
    vols = [100.0, 200.0, 300.0]
    out = volume_profile(highs, lows, closes, vols, bins=2, lookback=3)
    assert out["total_volume"] == pytest.approx(600.0)
    assert sum(b["volume"] for b in out["bins"]) == pytest.approx(600.0)


def test_vp_poc_within_value_area() -> None:
    """POC price must be between VAL and VAH (VA contains POC by construction)."""
    import random

    rng = random.Random(13)
    n = 50
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(closes[-1] + rng.uniform(-2, 2))
    highs = [c + abs(rng.uniform(0.1, 1.0)) for c in closes]
    lows = [c - abs(rng.uniform(0.1, 1.0)) for c in closes]
    vols = [rng.uniform(100, 5000) for _ in range(n)]
    out = volume_profile(highs, lows, closes, vols, bins=10, lookback=50)
    assert out["val"] <= out["poc"] <= out["vah"]


# ── Hand-computed test ────────────────────────────────────────────────


def test_vp_hand_computed_three_bars() -> None:
    """3 bars, bins=2, lookback=3, value_area_pct=0.7.

    highs   = [10, 12, 14]
    lows    = [ 5,  7,  9]
    closes  = [ 8, 10, 12]
    volumes = [100, 200, 300]

    price_min = 5, price_max = 14, range = 9, bin_width = 4.5
    Bin 0: [5, 9.5)
    Bin 1: [9.5, 14]

    Typical prices:
      bar 0: (10+5+8)/3 = 23/3 ≈ 7.667 → idx = (7.667-5)/4.5 = 0.593 → bin 0
      bar 1: (12+7+10)/3 = 29/3 ≈ 9.667 → idx = (9.667-5)/4.5 = 1.037 → bin 1
      bar 2: (14+9+12)/3 = 35/3 ≈ 11.667 → idx = (11.667-5)/4.5 = 1.482 → bin 1

    Bin volumes:
      Bin 0: 100
      Bin 1: 200 + 300 = 500

    POC = Bin 1 (highest volume); poc_price = (9.5 + 14)/2 = 11.75
    Total = 600, target = 420.
    Expansion from bin 1: acc=500 already >= 420. Done.
    VA = {bin 1}. VAH = 14.0, VAL = 9.5.
    """
    highs = [10.0, 12.0, 14.0]
    lows = [5.0, 7.0, 9.0]
    closes = [8.0, 10.0, 12.0]
    vols = [100.0, 200.0, 300.0]
    out = volume_profile(highs, lows, closes, vols, bins=2, lookback=3, value_area_pct=0.7)

    assert out["bins"][0]["volume"] == pytest.approx(100.0)
    assert out["bins"][0]["price_lo"] == pytest.approx(5.0)
    assert out["bins"][0]["price_hi"] == pytest.approx(9.5)
    assert out["bins"][1]["volume"] == pytest.approx(500.0)
    assert out["bins"][1]["price_lo"] == pytest.approx(9.5)
    assert out["bins"][1]["price_hi"] == pytest.approx(14.0)
    assert out["poc"] == pytest.approx(11.75)
    assert out["vah"] == pytest.approx(14.0)
    assert out["val"] == pytest.approx(9.5)


def test_vp_value_area_expansion() -> None:
    """4 bars with 3 bins; expand from POC outward to reach 70% target.

    typicals fall in bins such that POC's own volume is < 70%, forcing
    expansion to include neighbours.

    bins=3 over price range [0, 30]: bin_width=10
    Bin 0: [0, 10), Bin 1: [10, 20), Bin 2: [20, 30]

    Place typicals:
      bar 0: tp = 5 → bin 0, vol 100
      bar 1: tp = 15 → bin 1, vol 500  (POC)
      bar 2: tp = 25 → bin 2, vol 200
      bar 3: tp = 26 → bin 2, vol 50

    Total = 850. Target = 0.7 * 850 = 595.
    Start at bin 1 (500). Need to add more.
    Look below (bin 0=100) vs above (bin 2=250). Pick above → acc=750. >= 595. Stop.
    VA = bins {1, 2}. VAH = 30, VAL = 10.

    To construct: need highs/lows so each bar's typical lands in target bin.
    For tp = (h+l+c)/3 = target, easiest: h=l=c=target. But also need
    overall price_min = 0, price_max = 30. Use bar 0 with low=0, bar 3 with high=30.

    Let me just set:
      bar 0: H=5, L=0, C=10  → tp = 15/3 = 5  (in bin 0 if 5 < 10... idx = (5-0)/10 = 0 ✓)
      Wait, but then bar 0's low (0) sets price_min, but H=5 doesn't push price_max.
      bar 1: H=15, L=15, C=15 → tp = 15 → idx = 1.5 → bin 1
      bar 2: H=25, L=25, C=25 → tp = 25 → idx = 2.5 → clamp to bin 2 (since 2 is max)
      bar 3: H=30, L=26, C=22 → tp = 78/3 = 26 → idx = 2.6 → clamp to bin 2

      price_min = min(0,15,25,26) = 0 ✓
      price_max = max(5,15,25,30) = 30 ✓
      range = 30, bin_width = 10. Bins as expected.
    """
    highs = [5.0, 15.0, 25.0, 30.0]
    lows = [0.0, 15.0, 25.0, 26.0]
    closes = [10.0, 15.0, 25.0, 22.0]
    vols = [100.0, 500.0, 200.0, 50.0]
    out = volume_profile(highs, lows, closes, vols, bins=3, lookback=4, value_area_pct=0.7)

    assert out["bins"][0]["volume"] == pytest.approx(100.0)
    assert out["bins"][1]["volume"] == pytest.approx(500.0)
    assert out["bins"][2]["volume"] == pytest.approx(250.0)
    assert out["total_volume"] == pytest.approx(850.0)
    # POC = bin 1; poc_price = midpoint = 15.0
    assert out["poc"] == pytest.approx(15.0)
    # VA expansion picks bin 2 (vol 250) over bin 0 (vol 100).
    # acc after expansion = 500 + 250 = 750 >= 595. VA = {1, 2}.
    assert out["vah"] == pytest.approx(30.0)
    assert out["val"] == pytest.approx(10.0)


# ── Reference test ─────────────────────────────────────────────────────


def test_vp_bin_volumes_sum_to_total_for_random_walk() -> None:
    import random

    rng = random.Random(77)
    n = 80
    highs = [50.0 + rng.uniform(0, 3) for _ in range(n)]
    lows = [h - abs(rng.uniform(0.1, 1.0)) for h in highs]
    closes = [rng.uniform(lo, hi) for hi, lo in zip(highs, lows)]
    vols = [rng.uniform(50, 5000) for _ in range(n)]

    out = volume_profile(highs, lows, closes, vols, bins=20, lookback=80)
    sum_bin_vol = sum(b["volume"] for b in out["bins"])
    expected_total = sum(vols)
    assert out["total_volume"] == pytest.approx(expected_total, abs=1e-9)
    assert sum_bin_vol == pytest.approx(expected_total, abs=1e-9)


# ── Edge case tests ────────────────────────────────────────────────────


def test_vp_empty_input() -> None:
    assert volume_profile([], [], [], []) == {}


def test_vp_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        volume_profile([1.0, 2.0], [0.5], [1.0, 2.0], [100.0, 200.0])


def test_vp_flat_market_degenerate_bin() -> None:
    """All same prices ⇒ single degenerate bin holding all volume."""
    n = 10
    out = volume_profile([5.0] * n, [5.0] * n, [5.0] * n, [100.0] * n, bins=10, lookback=10)
    assert len(out["bins"]) == 1
    assert out["bins"][0]["volume"] == pytest.approx(1000.0)
    assert out["poc"] == pytest.approx(5.0)


def test_vp_lookback_exceeds_length_uses_what_is_available() -> None:
    """If lookback > n, use all available bars."""
    highs = [10.0, 12.0, 14.0]
    lows = [5.0, 7.0, 9.0]
    closes = [8.0, 10.0, 12.0]
    vols = [100.0, 200.0, 300.0]
    out = volume_profile(highs, lows, closes, vols, bins=2, lookback=100)
    assert out["total_volume"] == pytest.approx(600.0)


def test_vp_invalid_bins_raises() -> None:
    with pytest.raises(ValueError, match="bins"):
        volume_profile([1.0], [0.5], [0.7], [100.0], bins=0)


def test_vp_invalid_value_area_raises() -> None:
    with pytest.raises(ValueError, match="value_area"):
        volume_profile([1.0], [0.5], [0.7], [100.0], value_area_pct=0)
    with pytest.raises(ValueError, match="value_area"):
        volume_profile([1.0], [0.5], [0.7], [100.0], value_area_pct=1.5)


def test_vp_zero_total_volume_handled() -> None:
    """All zero volumes ⇒ degenerate VA at POC bin."""
    highs = [10.0, 11.0, 12.0]
    lows = [9.0, 10.0, 11.0]
    closes = [9.5, 10.5, 11.5]
    vols = [0.0, 0.0, 0.0]
    out = volume_profile(highs, lows, closes, vols, bins=3, lookback=3)
    assert out["total_volume"] == 0.0
