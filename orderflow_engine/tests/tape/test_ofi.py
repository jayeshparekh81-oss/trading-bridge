"""Book-OFI end-to-end in the tape engine (2026-07-15 R1 depth wiring).

Covers the accumulator, each guard (zero-qty, crossed, dt-gap), inert-when-off,
and the per-bar `ofi` emission. Signal-side plumbing is in tests/signals.
"""

from __future__ import annotations

from tape.config import TapeConfig
from tape.depth_imbalance import book_ofi, book_ok
from tape.engine import TapeEngine

SID = 61093
NS = 1_000_000_000


def _cfg(enabled=True, guard_s=5.0, tick_bar=2):
    return TapeConfig({"depth": {"ofi_enabled": enabled, "ofi_gap_guard_s": guard_s},
                       "bars": {"tick_bar_size": tick_bar}})


def _bid(p, q):
    return {"security_id": SID, "side": 0, "price_1": p, "qty_1": q}


def _ask(p, q):
    return {"security_id": SID, "side": 1, "price_1": p, "qty_1": q}


def _snap(eng, ts, bp, bq, ap, aq):
    """Feed one paired book snapshot (bid then ask at the same ts)."""
    eng.on_depth(_bid(bp, bq), ts)
    eng.on_depth(_ask(ap, aq), ts)


def _ofi(eng):
    return eng.state[SID].ofi_running


# -- accumulator ------------------------------------------------------------
def test_ofi_accumulates_across_snapshots():
    eng = TapeEngine(_cfg(), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)   # seed, no prev -> 0
    assert _ofi(eng) == 0.0
    _snap(eng, 2 * NS, 100.0, 15, 101.0, 10)   # bid qty +5, ask flat -> +5
    assert _ofi(eng) == 5.0
    _snap(eng, 3 * NS, 100.0, 15, 101.0, 8)    # ask qty -2 (d_ask=-2) -> -(-2)=+2
    assert _ofi(eng) == 7.0
    _snap(eng, 4 * NS, 100.5, 20, 101.0, 8)    # bid px up -> +cbq=+20
    assert _ofi(eng) == 27.0


def test_matches_book_ofi_primitive():
    """Accumulated increment == the pure book_ofi() between the two books."""
    eng = TapeEngine(_cfg(), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)
    _snap(eng, 2 * NS, 99.5, 12, 101.5, 7)
    expect = book_ofi(_bid(100.0, 10), _ask(101.0, 10), _bid(99.5, 12), _ask(101.5, 7))
    assert _ofi(eng) == expect


# -- inert when disabled ----------------------------------------------------
def test_inert_when_ofi_disabled():
    eng = TapeEngine(_cfg(enabled=False), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)
    _snap(eng, 2 * NS, 100.0, 99, 101.0, 10)
    assert eng.state[SID].ofi_running == 0.0
    assert eng.state[SID].ofi_prev_bid is None       # accumulator never armed


# -- guards -----------------------------------------------------------------
def test_guard_zero_qty_skipped():
    eng = TapeEngine(_cfg(), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)   # valid prev
    _snap(eng, 2 * NS, 100.0, 0, 101.0, 10)    # best bid qty 0 -> skipped
    assert _ofi(eng) == 0.0
    _snap(eng, 3 * NS, 100.0, 14, 101.0, 10)   # vs the LAST VALID book (qty 10->14) -> +4
    assert _ofi(eng) == 4.0                     # zero-qty book did not poison prev


def test_guard_crossed_book_skipped():
    eng = TapeEngine(_cfg(), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)
    _snap(eng, 2 * NS, 102.0, 10, 101.0, 10)   # bid(102) > ask(101) crossed -> skipped
    assert _ofi(eng) == 0.0
    assert book_ok(_bid(102.0, 10), _ask(101.0, 10)) is False


def test_guard_dt_gap_skipped():
    eng = TapeEngine(_cfg(guard_s=5.0), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)
    _snap(eng, 7 * NS, 100.0, 50, 101.0, 10)   # 6s > 5s guard -> increment skipped
    assert _ofi(eng) == 0.0
    _snap(eng, 8 * NS, 100.0, 60, 101.0, 10)   # 1s later, vs the 7s book (50->60) -> +10
    assert _ofi(eng) == 10.0                    # gap didn't emit a spike; prev did advance


# -- per-bar emission -------------------------------------------------------
def _tick(eng, ts, vol, ltp, bid, ask):
    eng.on_packet({"is_tick": True, "security_id": SID, "ts_recv_ns": ts, "volume": vol,
                   "ltp": ltp, "ltq": 0, "bid_price_1": bid, "ask_price_1": ask,
                   "ltt": ts // NS}, ts)


def test_per_bar_ofi_column_emitted():
    eng = TapeEngine(_cfg(tick_bar=2), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)
    _snap(eng, 2 * NS, 100.0, 18, 101.0, 10)          # +8 OFI before the bar closes
    b = 2 * NS
    _tick(eng, b + 1, 1000, 100.0, 99.5, 100.5)       # seed (no trade)
    _tick(eng, b + 2, 1010, 100.5, 100.0, 100.5)      # trade 1
    _tick(eng, b + 3, 1020, 101.0, 100.5, 101.0)      # trade 2 -> closes tick bar
    bars = eng.bar_rows
    assert bars, "expected at least one closed bar"
    assert "ofi" in bars[0]
    assert bars[0]["ofi"] == 8.0                       # net OFI captured in the first bar
    # a later bar with no new depth movement has ofi 0 (per-bar delta, not cumulative)
    _snap(eng, 3 * NS, 100.0, 18, 101.0, 10)          # no change -> +0
    _tick(eng, b + 4, 1030, 100.5, 100.0, 100.5)
    _tick(eng, b + 5, 1040, 100.0, 99.5, 100.5)       # closes 2nd bar
    assert eng.bar_rows[-1]["ofi"] == 0.0


def test_per_bar_queue_imbalance_emitted():
    """Bar carries the latest-book queue imbalance (bid-heavy > 0). INERT downstream
    (signal weight 0); this only plumbs the value for calibration."""
    eng = TapeEngine(_cfg(tick_bar=2), {SID: "NIFTY_FUT"})
    _snap(eng, 1 * NS, 100.0, 10, 101.0, 10)
    _snap(eng, 2 * NS, 100.0, 18, 101.0, 10)          # bid 18 vs ask 10 at bar close
    b = 2 * NS
    _tick(eng, b + 1, 1000, 100.0, 99.5, 100.5)       # seed (no trade)
    _tick(eng, b + 2, 1010, 100.5, 100.0, 100.5)      # trade 1
    _tick(eng, b + 3, 1020, 101.0, 100.5, 101.0)      # trade 2 -> closes tick bar
    assert eng.bar_rows[0]["queue_imbalance"] == (18 - 10) / (18 + 10)


def test_per_bar_queue_imbalance_none_without_book():
    """No depth seen -> queue_imbalance is None (not a spurious 0)."""
    eng = TapeEngine(_cfg(tick_bar=2), {SID: "NIFTY_FUT"})
    _tick(eng, 1, 1000, 100.0, 99.5, 100.5)           # seed
    _tick(eng, 2, 1010, 100.5, 100.0, 100.5)
    _tick(eng, 3, 1020, 101.0, 100.5, 101.0)          # closes bar, no on_depth ever
    assert eng.bar_rows[0]["queue_imbalance"] is None
