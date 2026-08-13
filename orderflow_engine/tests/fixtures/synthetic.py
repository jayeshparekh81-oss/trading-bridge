"""Synthesize Dhan feed binary packets from the documented layout.

These are used until real captured bytes are recorded on a live session.
The builders here MUST mirror the byte layout in ``recorder.parser`` exactly;
they are the inverse operation. On the first live session, capture real frames
and add them as byte fixtures to lock the layout against the exchange.
"""

from __future__ import annotations

import struct

from recorder import depth_parser as DP
from recorder import parser as P


def _header(packet_type: int, msg_len: int, segment: int, security_id: int) -> bytes:
    return P._HEADER.pack(packet_type, msg_len, segment, security_id)


def make_depth(
    security_id: int,
    *,
    side: str = "bid",
    segment: int = P.EXCHANGE_SEGMENTS["NSE_FNO"],
    msg_seq: int = 0,
    levels: list | None = None,
) -> bytes:
    """Build a 332-byte 20-level depth packet (bid feed code 41 / ask 51).

    ``levels`` is 20 tuples of (price, qty, orders); a default ladder is used
    when omitted. Mirrors ``recorder.depth_parser`` byte-for-byte (inverse op).
    """
    feed_code = DP.FEED_BID if side == "bid" else DP.FEED_ASK
    if levels is None:
        base = 24500.0 if side == "bid" else 24501.0
        step = -1.0 if side == "bid" else 1.0
        levels = [(base + step * i, 100 + i, 3 + i) for i in range(DP.DEPTH_LEVELS)]
    assert len(levels) == DP.DEPTH_LEVELS
    body = b"".join(DP._LEVEL.pack(px, qty, orders) for px, qty, orders in levels)
    msg_len = DP.HEADER_LEN + len(body)          # == 332
    return DP._HEADER.pack(msg_len, feed_code, segment, security_id, msg_seq) + body


def make_full(
    security_id: int,
    *,
    segment: int = P.EXCHANGE_SEGMENTS["NSE_FNO"],
    ltp: float = 24500.5,
    ltq: int = 75,
    ltt: int = 1_700_000_000,
    atp: float = 24499.0,
    volume: int = 1_234_567,
    total_sell: int = 5000,
    total_buy: int = 6000,
    oi: int = 987654,
    oi_high: int = 990000,
    oi_low: int = 980000,
    day_open: float = 24450.0,
    day_close: float = 24400.0,
    day_high: float = 24600.0,
    day_low: float = 24380.0,
    depth: list | None = None,
) -> bytes:
    """Build a 162-byte FULL packet. ``depth`` is 5 tuples of
    (bid_qty, ask_qty, bid_ord, ask_ord, bid_px, ask_px)."""
    body = P._FULL_BODY.pack(
        ltp, ltq, ltt, atp, volume, total_sell, total_buy, oi,
        oi_high, oi_low, day_open, day_close, day_high, day_low,
    )
    if depth is None:
        depth = [
            (100 + i, 200 + i, 3 + i, 4 + i, 24499.0 - i, 24501.0 + i)
            for i in range(P.DEPTH_LEVELS)
        ]
    depth_bytes = b"".join(P._DEPTH_LEVEL.pack(*lvl) for lvl in depth)
    msg_len = P.HEADER_LEN + len(body) + len(depth_bytes)
    return _header(P.PKT_FULL, msg_len, segment, security_id) + body + depth_bytes


def make_quote(
    security_id: int,
    *,
    segment: int = P.EXCHANGE_SEGMENTS["NSE_FNO"],
    ltp: float = 24500.5,
    ltq: int = 75,
    ltt: int = 1_700_000_000,
    atp: float = 24499.0,
    volume: int = 1_234_567,
    total_sell: int = 5000,
    total_buy: int = 6000,
    day_open: float = 24450.0,
    day_close: float = 24400.0,
    day_high: float = 24600.0,
    day_low: float = 24380.0,
) -> bytes:
    body = P._QUOTE_BODY.pack(
        ltp, ltq, ltt, atp, volume, total_sell, total_buy,
        day_open, day_close, day_high, day_low,
    )
    msg_len = P.HEADER_LEN + len(body)
    return _header(P.PKT_QUOTE, msg_len, segment, security_id) + body


def make_ticker(security_id: int, *, segment: int = 0, ltp: float = 24500.5,
                ltt: int = 1_700_000_000) -> bytes:
    body = P._TICKER_BODY.pack(ltp, ltt)
    return _header(P.PKT_TICKER, P.HEADER_LEN + len(body), segment, security_id) + body


def make_oi(security_id: int, *, segment: int = P.EXCHANGE_SEGMENTS["NSE_FNO"],
            oi: int = 987654) -> bytes:
    body = P._OI_BODY.pack(oi)
    return _header(P.PKT_OI, P.HEADER_LEN + len(body), segment, security_id) + body


def make_prev_close(security_id: int, *, segment: int = 0, prev_close: float = 24400.0,
                    prev_oi: int = 900000) -> bytes:
    body = P._PREV_CLOSE_BODY.pack(prev_close, prev_oi)
    return _header(P.PKT_PREV_CLOSE, P.HEADER_LEN + len(body), segment, security_id) + body


def make_disconnect(security_id: int = 0, *, segment: int = 0, code: int = 807) -> bytes:
    body = P._DISCONNECT_BODY.pack(code)
    return _header(P.PKT_DISCONNECT, P.HEADER_LEN + len(body), segment, security_id) + body


def make_status(security_id: int = 0, *, segment: int = 0) -> bytes:
    # Status packet: header only for our purposes (logged as an event).
    return _header(P.PKT_STATUS, P.HEADER_LEN, segment, security_id)
