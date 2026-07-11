"""Tests for the big-print detector + cluster (Module R3)."""

from __future__ import annotations

from tape.bigprint import BigPrintDetector
from tape.classify import BUY, SELL
from tape.trades import Trade


def _t(ts_ns, notional, side=BUY):
    return Trade(ts_ns=ts_ns, price=100.0, size=int(notional / 100),
                 side=side, notional=notional)


def test_inert_when_threshold_zero():
    d = BigPrintDetector(notional_threshold=0, cluster_k=3, cluster_window_s=10)
    assert d.on_trade(_t(1, 10_000_000)) == []


def test_emits_big_print_above_threshold():
    d = BigPrintDetector(notional_threshold=1_000_000, cluster_k=99, cluster_window_s=10)
    assert d.on_trade(_t(1, 999_999)) == []            # below
    evs = d.on_trade(_t(2, 1_000_000))                 # at threshold
    assert len(evs) == 1 and not evs[0].is_cluster
    assert evs[0].notional == 1_000_000


def test_cluster_k_in_window():
    ns = 1_000_000_000
    d = BigPrintDetector(notional_threshold=1_000_000, cluster_k=3, cluster_window_s=10)
    assert len(d.on_trade(_t(0 * ns, 2_000_000))) == 1        # print 1
    assert len(d.on_trade(_t(2 * ns, 2_000_000))) == 1        # print 2
    evs = d.on_trade(_t(4 * ns, 2_000_000))                   # print 3 within 10s -> cluster
    assert len(evs) == 2
    assert evs[1].is_cluster and evs[1].cluster_count == 3


def test_prints_outside_window_do_not_cluster():
    ns = 1_000_000_000
    d = BigPrintDetector(notional_threshold=1_000_000, cluster_k=3, cluster_window_s=10)
    d.on_trade(_t(0 * ns, 2_000_000))
    d.on_trade(_t(2 * ns, 2_000_000))
    evs = d.on_trade(_t(20 * ns, 2_000_000))     # 20s later -> first two aged out
    assert len(evs) == 1 and not evs[0].is_cluster
