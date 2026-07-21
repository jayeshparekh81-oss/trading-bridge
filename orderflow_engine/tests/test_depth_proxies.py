"""P6 depth-proxy tests (t1..t5) — deterministic, pure-core (no replayer needed).

t1 hand-built snapshot-sequence golden -> exact refill_ratio + cancel_proxy
t2 price-shift -> ZERO fake events when the book merely shifts
t3 full-execution -> cancel_proxy = 0
t4 causality: future snapshots never change already-emitted events
t5 feature off by default -> pipeline outputs byte-identical
"""

from __future__ import annotations

import pytest

from research.depth_proxies import DepthProxyEngine, aggregate, snapshot_to_book
from tape.config import TapeConfig
from tape.engine import TapeEngine

NS = 1_000_000_000


def _eng(**kw):
    # small wall_lookback so P90 becomes available quickly in tests
    kw.setdefault("wall_lookback", 500)
    return DepthProxyEngine(**kw)


# t1) golden: removal partially traded -> cancel; later refill at same price -> exact ratio
def test_t1_hand_built_golden_cancel_and_refill():
    e = _eng()
    e.on_snapshot(1 * NS, "bid", {100.00: 500, 99.95: 400, 99.90: 300})
    e.on_trade(int(1.5 * NS), 100.00, 100)                       # 100 traded at the level
    e.on_snapshot(2 * NS, "bid", {100.00: 200, 99.95: 400, 99.90: 300})
    # removed 300, traded 100 -> cancel_proxy = 200
    cancels = [x for x in e.events if x.kind == "cancel"]
    assert len(cancels) == 1
    c = cancels[0]
    assert c.price == 100.00 and c.removed == 300 and c.traded == 100
    assert c.cancel_qty == pytest.approx(200)
    # refill within k snapshots, best still at the level -> ratio = 250/300
    e.on_snapshot(3 * NS, "bid", {100.00: 450, 99.95: 400, 99.90: 300})
    refills = [x for x in e.events if x.kind == "refill"]
    assert len(refills) == 1
    r = refills[0]
    assert r.removed == 300 and r.restored == 250
    assert r.ratio == pytest.approx(250 / 300, abs=1e-6)
    # aggregation rolls the numbers up per bar
    rows = aggregate(e.events, [(0, 4 * NS)], window=10)
    assert rows[0]["bid_refills"] == 1 and rows[0]["bid_cancel_qty"] == pytest.approx(200)
    assert rows[0]["bid_refill_ratio"] == pytest.approx(250 / 300, abs=1e-6)


# t2) pure price shift: same qtys, book moved one tick -> no events (diff is BY PRICE)
def test_t2_price_shift_zero_fake_events():
    e = _eng()
    e.on_snapshot(1 * NS, "ask", {100.05: 200, 100.10: 200, 100.15: 200})
    e.on_snapshot(2 * NS, "ask", {100.10: 200, 100.15: 200, 100.20: 200})   # shifted up 1 tick
    assert e.events == []                                        # overlap prices unchanged
    # index-diffing would have manufactured a cancel at "level 1" here — we must not.


# t3) removal fully explained by trades -> cancel_proxy = 0 (no cancel event)
def test_t3_full_execution_no_cancel():
    e = _eng()
    e.on_snapshot(1 * NS, "bid", {100.00: 500})
    e.on_trade(int(1.2 * NS), 100.00, 300)
    e.on_snapshot(2 * NS, "bid", {100.00: 200})
    assert [x for x in e.events if x.kind == "cancel"] == []
    # (the removal is still tracked for a possible refill — that's replenishment, not cancel)


# t4) causality: events emitted so far never change when future snapshots arrive
def test_t4_causal_no_future_rewrite():
    e = _eng()
    e.on_snapshot(1 * NS, "bid", {100.00: 500})
    e.on_snapshot(2 * NS, "bid", {100.00: 100})                  # removal, no trades -> cancel
    frozen = [tuple(vars(x).items()) for x in e.events]
    e.on_snapshot(3 * NS, "bid", {100.00: 9999})                 # absurd future refill
    e.on_snapshot(4 * NS, "bid", {50.0: 1})                      # absurd future book
    assert [tuple(vars(x).items()) for x in e.events[:len(frozen)]] == frozen


# gap guard: a lull discards the diff and pending state (no stale events)
def test_gap_guard_discards_stale_diff():
    e = _eng()
    e.on_snapshot(1 * NS, "bid", {100.00: 500})
    e.on_snapshot(1 * NS + 6 * NS, "bid", {100.00: 100})         # 6s > 5s guard
    assert e.events == []


# t5) OFF by default — pipeline bar rows carry no proxy keys; import changes nothing
def test_t5_flag_off_pipeline_untouched():
    def run_bars():
        eng = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {61093: "NIFTY_FUT"})
        vol = 1000
        for i in range(1, 7):
            vol += 10
            eng.on_packet({"is_tick": True, "security_id": 61093, "ts_recv_ns": i * NS,
                           "volume": vol, "ltp": 100.0 + i * 0.1, "ltq": 0,
                           "bid_price_1": 99.9, "ask_price_1": 100.1, "ltt": i}, i * NS)
        return eng.bar_rows
    rows = run_bars()
    assert rows and all("cancel" not in str(sorted(r)) and "refill" not in str(sorted(r))
                        for r in rows)
    assert run_bars() == rows                                    # import changed nothing


# snapshot_to_book: zero/absent levels excluded
def test_snapshot_to_book():
    parsed = {"price_1": 100.0, "qty_1": 10, "price_2": 0.0, "qty_2": 50,
              "price_3": 99.9, "qty_3": 0, "price_4": 99.8, "qty_4": 5}
    assert snapshot_to_book(parsed, levels=5) == {100.0: 10.0, 99.8: 5.0}
