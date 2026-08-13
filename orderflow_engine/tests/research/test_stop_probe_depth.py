"""Sanity tests for the stop-probe-depth classifier (research, 2026-07-16)."""

from __future__ import annotations

from research.stop_probe_depth import day_atr, probes_for_level


def _b(h, l, c):
    return (h, l, c)


def test_single_bar_rejection_is_a_probe():
    # prev bar under 100; touch bar wicks to 100.5 but closes back below -> probe depth 0.5
    bars = [_b(99.0, 98.0, 98.5), _b(100.5, 99.0, 99.2), _b(99.5, 98.0, 98.5)]
    ev = probes_for_level(bars, 100.0, k=5)
    assert ev == [(0.5, "probe")]


def test_break_when_price_continues_past():
    # touch 100 from below and keep closing above for the whole window -> break
    bars = [_b(99.0, 98.0, 98.5), _b(100.5, 99.0, 100.4), _b(102.0, 100.5, 101.8),
            _b(103.0, 101.5, 102.9)]
    ev = probes_for_level(bars, 100.0, k=5)
    assert ev == [(3.0, "break")]      # depth = peak excursion 103-100 within window


def test_probe_after_a_few_bars_uses_deepest_excursion():
    # touches, wicks deeper over 2 bars (peak 101.2), then closes back below -> probe 1.2
    bars = [_b(99.0, 98.0, 98.5), _b(100.4, 99.5, 100.1), _b(101.2, 100.0, 100.3),
            _b(100.5, 98.5, 99.0)]
    ev = probes_for_level(bars, 100.0, k=5)
    assert ev == [(1.2, "probe")]


def test_support_side_mirrors():
    # prev bar above 100; touch wicks DOWN to 99.3, closes back above -> probe depth 0.7
    bars = [_b(102.0, 101.0, 101.5), _b(101.0, 99.3, 100.6), _b(101.5, 100.2, 101.0)]
    ev = probes_for_level(bars, 100.0, k=5)
    assert ev == [(0.7, "probe")]


def test_no_touch_no_event():
    bars = [_b(99.0, 98.0, 98.5), _b(99.5, 98.5, 99.0)]      # never reaches 100
    assert probes_for_level(bars, 100.0, k=5) == []


def test_day_atr_positive():
    bars = [_b(101, 99, 100), _b(102, 100, 101), _b(101, 99, 100)]
    assert day_atr(bars) > 0
