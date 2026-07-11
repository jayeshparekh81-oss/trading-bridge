"""Tests for event-time bars (Module R3) — exact hand-computed math."""

from __future__ import annotations

from tape.bars import TICK, VOLUME, Bar, BarBuilder
from tape.classify import BUY, SELL
from tape.trades import Trade


def _t(ts, price, size, side):
    return Trade(ts_ns=ts, price=price, size=size, side=side, notional=price * size)


def test_n_tick_bar_closes_at_n_with_exact_ohlc_delta():
    b = BarBuilder(TICK, tick_size=3)
    assert b.on_trade(_t(10, 100.0, 5, BUY)) is None
    assert b.on_trade(_t(20, 102.0, 3, SELL)) is None
    bar = b.on_trade(_t(30, 101.0, 2, BUY))     # 3rd trade closes the bar
    assert isinstance(bar, Bar)
    assert (bar.open, bar.high, bar.low, bar.close) == (100.0, 102.0, 100.0, 101.0)
    assert bar.volume == 10
    assert bar.buy_vol == 7 and bar.sell_vol == 3      # 5+2 buy, 3 sell
    assert bar.delta == 4                              # 7 - 3
    assert bar.trade_count == 3
    assert bar.start_ts_ns == 10 and bar.end_ts_ns == 30
    assert bar.duration_s == 20 / 1e9


def test_tick_bars_reset_between_bars():
    b = BarBuilder(TICK, tick_size=2)
    b.on_trade(_t(1, 100.0, 1, BUY))
    bar1 = b.on_trade(_t(2, 100.0, 1, BUY))
    b.on_trade(_t(3, 200.0, 1, SELL))
    bar2 = b.on_trade(_t(4, 200.0, 1, SELL))
    assert bar1.bar_index == 0 and bar2.bar_index == 1
    assert bar2.open == 200.0 and bar2.buy_vol == 0 and bar2.sell_vol == 2


def test_volume_bar_closes_at_threshold():
    b = BarBuilder(VOLUME, volume_threshold=100)
    assert b.on_trade(_t(1, 50.0, 40, BUY)) is None
    assert b.on_trade(_t(2, 50.0, 40, BUY)) is None
    bar = b.on_trade(_t(3, 50.0, 30, SELL))     # cumulative 110 >= 100 -> close
    assert bar.volume == 110 and bar.trade_count == 3


def test_volume_bar_threshold_zero_never_closes():
    b = BarBuilder(VOLUME, volume_threshold=0)
    for i in range(50):
        assert b.on_trade(_t(i, 50.0, 1000, BUY)) is None


def test_flush_emits_trailing_partial_bar():
    b = BarBuilder(TICK, tick_size=10)
    b.on_trade(_t(1, 100.0, 5, BUY))
    b.on_trade(_t(2, 101.0, 5, SELL))
    bar = b.flush()
    assert bar.trade_count == 2 and bar.close == 101.0
    assert b.flush() is None      # nothing left
