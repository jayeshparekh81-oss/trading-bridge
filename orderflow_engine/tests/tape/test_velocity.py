"""Tests for tape velocity (Module R3) — hand-computed median baseline."""

from __future__ import annotations

from tape.velocity import TapeVelocity


def test_no_baseline_until_m_bars():
    v = TapeVelocity(baseline_bars=3, spike_ratio=0.5)
    r1 = v.on_bar_duration(1.0)
    assert r1.baseline_s is None and r1.ratio is None and r1.spike is False
    v.on_bar_duration(1.0)
    r3 = v.on_bar_duration(1.0)                 # still only 2 priors when computing
    assert r3.baseline_s is None


def test_ratio_and_spike_after_baseline():
    v = TapeVelocity(baseline_bars=3, spike_ratio=0.5)
    for d in (2.0, 2.0, 2.0):                   # seed 3 priors, median = 2.0
        v.on_bar_duration(d)
    r = v.on_bar_duration(0.8)                  # baseline median(2,2,2)=2.0; ratio 0.4
    assert r.baseline_s == 2.0
    assert r.ratio == 0.4
    assert r.spike is True                      # 0.4 < 0.5


def test_no_spike_when_ratio_above_threshold():
    v = TapeVelocity(baseline_bars=3, spike_ratio=0.5)
    for d in (2.0, 2.0, 2.0):
        v.on_bar_duration(d)
    r = v.on_bar_duration(1.5)                  # ratio 0.75 > 0.5
    assert r.spike is False


def test_median_uses_last_m_only():
    v = TapeVelocity(baseline_bars=2, spike_ratio=0.5)
    v.on_bar_duration(10.0)
    v.on_bar_duration(4.0)                      # window now [10,4]
    r = v.on_bar_duration(1.0)                  # median(10,4)=7.0; ratio 1/7
    assert r.baseline_s == 7.0
