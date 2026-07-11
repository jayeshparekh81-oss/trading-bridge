"""Price x OI buildup classification + inert significance gate (Module R5)."""

from __future__ import annotations

from chain.buildup import classify_buildup


def test_four_way_labels():
    assert classify_buildup(100, 105, 1000, 1100).label == "long_buildup"
    assert classify_buildup(105, 100, 1000, 1100).label == "short_buildup"
    assert classify_buildup(100, 105, 1100, 1000).label == "short_covering"
    assert classify_buildup(105, 100, 1100, 1000).label == "long_unwinding"


def test_flat_is_neutral():
    assert classify_buildup(100, 100, 1000, 1100).label == "neutral"
    assert classify_buildup(100, 105, 1000, 1000).label == "neutral"


def test_significance_inert_at_zero():
    b = classify_buildup(100, 105, 1000, 1100)     # thresholds default 0
    assert b.significant is False                   # inert until calibrated


def test_significance_fires_when_calibrated():
    b = classify_buildup(100, 105, 1000, 1100,
                         price_threshold_pct=1.0, oi_threshold_pct=5.0)
    assert b.price_change_pct == 5.0 and b.oi_change_pct == 10.0
    assert b.significant is True                     # both exceed thresholds


def test_significance_needs_both():
    # oi move (10%) big but price move (0.5%) below its threshold -> not significant
    b = classify_buildup(100, 100.5, 1000, 1100,
                         price_threshold_pct=1.0, oi_threshold_pct=5.0)
    assert b.significant is False
