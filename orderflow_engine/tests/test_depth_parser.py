"""Tests for the 20-level depth binary parser (Module R1)."""

from __future__ import annotations

from recorder import depth_parser as DP
from recorder.depth_schema import SIDE_ASK, SIDE_BID
from tests.fixtures import synthetic as S


def test_packet_geometry():
    assert DP.HEADER_LEN == 12
    assert DP.LEVEL_LEN == 16
    assert DP.PACKET_LEN == 332


def test_parse_bid_packet_roundtrip():
    levels = [(24500.0 - i, 100 + i, 3 + i) for i in range(20)]
    pkt = S.make_depth(1333, side="bid", segment=1, msg_seq=42, levels=levels)
    assert len(pkt) == DP.PACKET_LEN
    row = DP.parse_depth_packet(pkt)
    assert row["is_depth"] is True
    assert row["security_id"] == 1333
    assert row["exchange_segment"] == 1
    assert row["side"] == SIDE_BID
    assert row["msg_seq"] == 42
    # every level round-trips exactly
    for i, (px, qty, orders) in enumerate(levels, start=1):
        assert row[f"price_{i}"] == px
        assert row[f"qty_{i}"] == qty
        assert row[f"orders_{i}"] == orders


def test_ask_side_mapping():
    row = DP.parse_depth_packet(S.make_depth(99, side="ask"))
    assert row["side"] == SIDE_ASK


def test_split_frame_bid_then_ask_stacked():
    frame = S.make_depth(10, side="bid") + S.make_depth(10, side="ask")
    packets = list(DP.split_depth_frame(frame))
    assert len(packets) == 2
    rows = list(DP.parse_depth_frame(frame))
    assert [r["side"] for r in rows] == [SIDE_BID, SIDE_ASK]
    assert all(r["security_id"] == 10 for r in rows)


def test_truncated_trailing_packet_is_ignored():
    frame = S.make_depth(5, side="bid") + S.make_depth(5, side="ask")[:100]
    rows = list(DP.parse_depth_frame(frame))
    # only the first complete packet survives; the truncated tail is dropped
    assert len(rows) == 1
    assert rows[0]["side"] == SIDE_BID


def test_too_short_packet_returns_none():
    assert DP.parse_depth_packet(b"\x00\x01\x02") is None


def test_multiple_instruments_in_one_frame():
    frame = (S.make_depth(1, side="bid") + S.make_depth(1, side="ask")
             + S.make_depth(2, side="bid") + S.make_depth(2, side="ask"))
    rows = list(DP.parse_depth_frame(frame))
    assert [(r["security_id"], r["side"]) for r in rows] == [
        (1, SIDE_BID), (1, SIDE_ASK), (2, SIDE_BID), (2, SIDE_ASK)]
