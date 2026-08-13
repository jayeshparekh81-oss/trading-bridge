"""Tests for trade extraction incl. the volume_delta vs ltq reconciliation."""

from __future__ import annotations

from tape.classify import BUY, SELL
from tape.trades import TradeExtractor
from tests.tape import fixtures as F


def test_first_snapshot_seeds_no_trade():
    ex = TradeExtractor()
    assert ex.on_tick(F.tick(1, volume=1000, ltp=100.0, bid=99.5, ask=100.5)) is None


def test_volume_delta_is_trade_size():
    ex = TradeExtractor(size_mode="volume_delta")
    ex.on_tick(F.tick(1, volume=1000, ltp=100.0, bid=99.5, ask=100.5))       # seed
    t = ex.on_tick(F.tick(2, volume=1030, ltp=100.5, bid=100.0, ask=100.5))  # +30, lifts ask
    assert t is not None
    assert t.size == 30 and t.side == BUY
    assert t.notional == 100.5 * 30


def test_no_trade_when_volume_flat():
    ex = TradeExtractor()
    ex.on_tick(F.tick(1, volume=1000, ltp=100.0, bid=99.5, ask=100.5))
    assert ex.on_tick(F.tick(2, volume=1000, ltp=100.0, bid=99.5, ask=100.5)) is None


def test_reconciliation_volume_delta_equals_ltq_when_derivable():
    """Founder requirement: on data where each snapshot is exactly one trade and
    volume advances by exactly ltq, volume_delta and ltq modes must AGREE."""
    seq = [
        F.tick(1, volume=1000, ltp=100.0, ltq=0, bid=99.5, ask=100.5),   # seed
        F.tick(2, volume=1010, ltp=100.5, ltq=10, bid=100.0, ask=100.5),
        F.tick(3, volume=1035, ltp=100.0, ltq=25, bid=100.0, ask=100.5),
        F.tick(4, volume=1040, ltp=100.5, ltq=5, bid=100.0, ask=100.5),
    ]
    vd = TradeExtractor(size_mode="volume_delta")
    lq = TradeExtractor(size_mode="ltq")
    out_vd = [vd.on_tick(r) for r in seq]
    out_lq = [lq.on_tick(r) for r in seq]
    got_vd = [(t.size, t.side, t.price) for t in out_vd if t]
    got_lq = [(t.size, t.side, t.price) for t in out_lq if t]
    assert got_vd == got_lq == [(10, BUY, 100.5), (25, SELL, 100.0), (5, BUY, 100.5)]


def test_divergence_when_multiple_trades_between_snapshots():
    """When volume jumps more than ltq (multiple trades between snapshots),
    volume_delta captures the total while ltq only sees the last print."""
    seq = [
        F.tick(1, volume=1000, ltp=100.0, ltq=0, bid=99.5, ask=100.5),   # seed
        F.tick(2, volume=1090, ltp=100.5, ltq=10, bid=100.0, ask=100.5),  # +90 but ltq=10
    ]
    vd = TradeExtractor(size_mode="volume_delta")
    lq = TradeExtractor(size_mode="ltq")
    vd.on_tick(seq[0]); lq.on_tick(seq[0])
    tv = vd.on_tick(seq[1])
    tl = lq.on_tick(seq[1])
    assert tv.size == 90        # volume_delta = total traded
    assert tl.size == 10        # ltq = last print only
    assert tv.size != tl.size   # documented divergence
