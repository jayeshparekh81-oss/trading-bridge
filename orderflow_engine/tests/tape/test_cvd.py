"""Tests for CVD + slope (Module R3) — hand-computed."""

from __future__ import annotations

from tape.classify import BUY, SELL
from tape.cvd import CVD, SlopeSeries
from tape.trades import Trade


def _t(size, side):
    return Trade(ts_ns=0, price=100.0, size=size, side=side, notional=0.0)


def test_cvd_accumulates_signed_size():
    cvd = CVD()
    assert cvd.on_trade(_t(10, BUY)) == 10
    assert cvd.on_trade(_t(4, SELL)) == 6
    assert cvd.on_trade(_t(6, SELL)) == 0
    assert cvd.on_trade(_t(15, BUY)) == 15
    assert cvd.running == 15


def test_slope_is_change_per_bar_over_window():
    s = SlopeSeries(window_bars=3)
    assert s.sample(0) == 0.0            # first sample, no slope yet
    assert s.sample(10) == 10.0         # (10-0)/1
    assert s.sample(30) == 15.0         # (30-0)/2
    assert s.sample(60) == 20.0         # (60-0)/3
    # window is 3 -> deque holds last 4 samples; oldest (0) now drops
    assert s.sample(100) == round((100 - 10) / 3, 6)   # (100-10)/3 = 30.0


def test_slope_window_one():
    s = SlopeSeries(window_bars=1)
    s.sample(5)
    assert s.sample(9) == 4.0           # (9-5)/1
