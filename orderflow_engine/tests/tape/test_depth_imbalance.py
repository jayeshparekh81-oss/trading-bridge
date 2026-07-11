"""Tests for depth imbalance + book OFI pure functions (Module R3)."""

from __future__ import annotations

from recorder.depth_schema import SIDE_ASK, SIDE_BID

from tape.depth_imbalance import book_ofi, queue_imbalance, queue_imbalance_rows
from tests.tape import fixtures as F


def test_queue_imbalance_ratio():
    assert queue_imbalance([30, 20], [10, 10], levels=2) == (50 - 20) / 70


def test_queue_imbalance_balanced_is_zero():
    assert queue_imbalance([10, 10], [10, 10], levels=2) == 0.0


def test_queue_imbalance_empty_book_is_none():
    assert queue_imbalance([0, 0], [0, 0], levels=2) is None


def test_queue_imbalance_respects_levels():
    # only top 1 level counts -> (30-10)/40
    assert queue_imbalance([30, 999], [10, 999], levels=1) == (30 - 10) / 40


def test_queue_imbalance_from_rows():
    bid = F.depth_row(1, SIDE_BID, [30, 20])
    ask = F.depth_row(1, SIDE_ASK, [10, 10])
    assert queue_imbalance_rows(bid, ask, levels=2) == (50 - 20) / 70


def test_book_ofi_price_up_adds_full_bid():
    prev_b = {"price_1": 100.0, "qty_1": 50}
    prev_a = {"price_1": 101.0, "qty_1": 40}
    curr_b = {"price_1": 100.5, "qty_1": 30}   # bid px up -> +curr bid qty
    curr_a = {"price_1": 101.0, "qty_1": 40}   # ask unchanged -> Δ = 0
    assert book_ofi(prev_b, prev_a, curr_b, curr_a) == 30.0


def test_book_ofi_same_price_uses_delta():
    prev_b = {"price_1": 100.0, "qty_1": 50}
    prev_a = {"price_1": 101.0, "qty_1": 40}
    curr_b = {"price_1": 100.0, "qty_1": 60}   # +10 bid
    curr_a = {"price_1": 101.0, "qty_1": 55}   # +15 ask
    assert book_ofi(prev_b, prev_a, curr_b, curr_a) == (10 - 15)


def test_book_ofi_missing_snapshot_is_none():
    assert book_ofi(None, {}, {}, {}) is None
