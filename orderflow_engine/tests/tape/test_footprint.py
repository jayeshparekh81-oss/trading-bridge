"""Footprint per-level splits + stacked-imbalance detector (Module R3 addendum)."""

from __future__ import annotations

import json

from tape.bars import TICK, BarBuilder
from tape.classify import BUY, SELL
from tape.config import TapeConfig
from tape.engine import TapeEngine
from tape.footprint import detect_stacked_imbalance
from tape.trades import Trade


def _t(ts, price, size, side):
    return Trade(ts_ns=ts, price=price, size=size, side=side, notional=price * size)


def test_footprint_per_level_splits_exact():
    b = BarBuilder(TICK, tick_size=3, footprint_bin_size=1.0)
    b.on_trade(_t(1, 100.0, 10, BUY))    # bin 100 buy
    b.on_trade(_t(2, 100.5, 5, SELL))    # bin 100 sell
    bar = b.on_trade(_t(3, 101.5, 8, BUY))   # bin 101 buy -> closes (3 trades)
    assert bar.footprint == {100.0: [10, 5], 101.0: [8, 0]}


def test_no_footprint_when_bin_size_zero():
    b = BarBuilder(TICK, tick_size=1, footprint_bin_size=0.0)
    bar = b.on_trade(_t(1, 100.0, 10, BUY))
    assert bar.footprint == {}


# --- stacked imbalance ---------------------------------------------------
_FP = {100.0: [30, 2], 101.0: [40, 3], 102.0: [50, 4]}   # each bin buy >> sell-below


def test_inert_at_zero_ratio():
    assert detect_stacked_imbalance(_FP, 1.0, 0, 3) == []


def test_stacked_buy_across_consecutive_levels():
    out = detect_stacked_imbalance(_FP, 1.0, 3.0, 3)
    assert len(out) == 1
    assert out[0].side == "buy" and out[0].levels == 3
    assert (out[0].price_low, out[0].price_high) == (100.0, 102.0)


def test_needs_min_levels():
    # only 2 consecutive imbalanced bins, min_levels=3 -> no event
    fp = {100.0: [30, 2], 101.0: [40, 3]}
    assert detect_stacked_imbalance(fp, 1.0, 3.0, 3) == []
    assert detect_stacked_imbalance(fp, 1.0, 3.0, 2)[0].levels == 2


def test_ratio_boundary_is_inclusive():
    # buy[P] == 3 * sell[P-1] exactly at each of 100/101/102 (>= is inclusive)
    fp = {99.0: [0, 1], 100.0: [3, 2], 101.0: [6, 3], 102.0: [9, 0]}
    out = detect_stacked_imbalance(fp, 1.0, 3.0, 3)
    assert out and out[0].side == "buy"
    assert (out[0].price_low, out[0].price_high) == (100.0, 102.0)


def test_below_ratio_breaks_the_run():
    fp = {100.0: [30, 2], 101.0: [5, 3], 102.0: [50, 4]}   # 101: 5 >= 3*2=6? no -> breaks
    assert detect_stacked_imbalance(fp, 1.0, 3.0, 3) == []


def test_sell_side_diagonal():
    # sell_vol[P] >= ratio * buy_vol[P+bin]
    fp = {100.0: [1, 40], 101.0: [2, 50], 102.0: [3, 60]}
    out = detect_stacked_imbalance(fp, 1.0, 3.0, 3)
    assert out and out[0].side == "sell"


def test_engine_emits_stacked_imbalance_event_when_calibrated():
    cfg = TapeConfig({"bars": {"tick_bar_size": 3},
                      "footprint": {"bin_size": {"index_fut": 1.0}, "imbalance_ratio": 3.0,
                                    "stacked_min_levels": 3}})
    eng = TapeEngine(cfg, {1: "NIFTY_FUT"})

    def tick(ts, vol, ltp):
        return {"is_tick": True, "security_id": 1, "ts_recv_ns": ts, "volume": vol,
                "ltp": ltp, "bid_price_1": ltp - 0.5, "ask_price_1": ltp + 0.5}

    # seed then 3 aggressive buys climbing one bin each -> stacked buy imbalance
    eng.on_packet(tick(0, 1000, 100.0), 0)
    eng.on_packet(tick(1, 1030, 100.9), 1)     # +30 buy @ bin 100
    eng.on_packet(tick(2, 1070, 101.9), 2)     # +40 buy @ bin 101
    eng.on_packet(tick(3, 1120, 102.9), 3)     # +50 buy @ bin 102 -> bar closes
    eng.finalize()
    kinds = [e["kind"] for e in eng.event_rows]
    assert "STACKED_IMBALANCE" in kinds
    row = next(r for r in eng.bar_rows if r["footprint"])
    assert json.loads(row["footprint"])          # footprint persisted as JSON
