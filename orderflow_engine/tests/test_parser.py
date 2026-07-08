"""Parser unit tests — byte fixtures synthesized from the documented layout.

TODO(live): on the first live session, capture real frames and add them as
raw byte fixtures here to lock the layout against the exchange.
"""

from __future__ import annotations

import math

import pytest

from recorder import parser as P
from tests.fixtures import synthetic as S


def test_full_packet_length_is_162():
    pkt = S.make_full(53001)
    assert len(pkt) == 162 == P.FULL_PACKET_LEN


def test_parse_full_roundtrip():
    pkt = S.make_full(
        53001, ltp=24512.75, ltq=50, ltt=1_700_123_456, atp=24500.0,
        volume=9_876_543, total_sell=1111, total_buy=2222, oi=555000,
    )
    t = P.parse_packet(pkt)
    assert t["is_tick"] is True
    assert t["packet_type"] == P.PKT_FULL
    assert t["security_id"] == 53001
    assert math.isclose(t["ltp"], 24512.75, rel_tol=1e-6)
    assert t["ltq"] == 50
    assert t["ltt"] == 1_700_123_456
    assert math.isclose(t["atp"], 24500.0, rel_tol=1e-6)
    assert t["volume"] == 9_876_543
    assert t["total_sell_qty"] == 1111
    assert t["total_buy_qty"] == 2222
    assert t["oi"] == 555000


def test_parse_full_depth_flattened():
    depth = [(10 * i, 20 * i, i, i + 1, 100.0 + i, 200.0 + i) for i in range(1, 6)]
    pkt = S.make_full(53001, depth=depth)
    t = P.parse_packet(pkt)
    for i in range(1, 6):
        assert t[f"bid_qty_{i}"] == 10 * i
        assert t[f"ask_qty_{i}"] == 20 * i
        assert t[f"bid_orders_{i}"] == i
        assert t[f"ask_orders_{i}"] == i + 1
        assert math.isclose(t[f"bid_price_{i}"], 100.0 + i, rel_tol=1e-6)
        assert math.isclose(t[f"ask_price_{i}"], 200.0 + i, rel_tol=1e-6)


def test_parse_quote():
    pkt = S.make_quote(1333, volume=42, total_buy=7, total_sell=9)
    t = P.parse_packet(pkt)
    assert t["is_tick"] is True
    assert t["packet_type"] == P.PKT_QUOTE
    assert t["security_id"] == 1333
    assert t["volume"] == 42
    assert t["total_buy_qty"] == 7
    assert t["total_sell_qty"] == 9
    # Quote has no OI or depth -> None
    assert t["oi"] is None
    assert t["bid_price_1"] is None


def test_parse_ticker_and_oi():
    tick = P.parse_packet(S.make_ticker(13, ltp=24000.25, ltt=1_700_000_001))
    assert tick["packet_type"] == P.PKT_TICKER
    assert math.isclose(tick["ltp"], 24000.25, rel_tol=1e-6)
    assert tick["ltt"] == 1_700_000_001
    assert tick["volume"] is None

    oi = P.parse_packet(S.make_oi(53001, oi=123456))
    assert oi["packet_type"] == P.PKT_OI
    assert oi["oi"] == 123456
    assert oi["ltp"] is None


def test_every_tick_has_full_schema_keys():
    t = P.parse_packet(S.make_ticker(13))
    for key in P.TICK_FIELDS:
        assert key in t, f"missing schema key {key}"


def test_parse_disconnect_event():
    ev = P.parse_packet(S.make_disconnect(code=807))
    assert ev["is_tick"] is False
    assert ev["event"] == "disconnect"
    assert ev["reason_code"] == 807
    assert ev["reason"] == "access token expired"


def test_parse_prev_close_and_status():
    pc = P.parse_packet(S.make_prev_close(13, prev_close=23999.5, prev_oi=800000))
    assert pc["is_tick"] is False
    assert pc["event"] == "prev_close"
    assert math.isclose(pc["prev_close"], 23999.5, rel_tol=1e-6)
    assert pc["prev_oi"] == 800000

    st = P.parse_packet(S.make_status())
    assert st["is_tick"] is False
    assert st["event"] == "market_status"


def test_split_multi_packet_frame():
    frame = S.make_full(53001) + S.make_quote(1333) + S.make_oi(53001)
    packets = list(P.split_frame(frame))
    assert len(packets) == 3
    parsed = [P.parse_packet(p) for p in packets]
    assert [p["packet_type"] for p in parsed] == [P.PKT_FULL, P.PKT_QUOTE, P.PKT_OI]


def test_split_frame_ignores_truncated_tail():
    frame = S.make_full(53001) + S.make_quote(1333)[:10]  # chop the quote
    packets = list(P.split_frame(frame))
    assert len(packets) == 1  # only the complete full packet
    assert P.parse_packet(packets[0])["packet_type"] == P.PKT_FULL


def test_parse_frame_yields_all():
    frame = S.make_full(53001) + S.make_disconnect(code=805)
    out = list(P.parse_frame(frame))
    assert len(out) == 2
    assert out[0]["is_tick"] is True
    assert out[1]["event"] == "disconnect"


def test_short_packet_returns_none():
    assert P.parse_packet(b"\x08\x00\x00") is None


def test_peek_header():
    pkt = S.make_full(53001, segment=P.EXCHANGE_SEGMENTS["NSE_FNO"])
    ptype, mlen, seg, sid = P.peek_header(pkt)
    assert ptype == P.PKT_FULL
    assert mlen == 162
    assert seg == P.EXCHANGE_SEGMENTS["NSE_FNO"]
    assert sid == 53001


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
