"""Binary parser for the Dhan v2 20-level Market Depth feed (Module R1).

Layout verified against https://dhanhq.co/docs/v2/full-market-depth/ (2026-07-11).

This is a SEPARATE feed from the R0 Live Market Feed and has a DIFFERENT header,
so it gets its own parser (``recorder.parser`` stays untouched):

  Response header (12 bytes, little-endian):
    message_length   uint16   entire payload length
    feed_code        uint8    41 = bid (buy), 51 = ask (sell)
    exchange_segment uint8
    security_id      uint32
    message_sequence uint32   exchange sequence (captured as msg_seq)

  Then 20 depth levels, 16 bytes each (little-endian):
    price   float64
    qty     uint32
    orders  uint32

Bid and ask arrive as separate packets; a single WebSocket binary frame may
stack several packets one after another. ``split_depth_frame`` walks the frame;
``parse_depth_packet`` turns one packet into a side-tagged depth row.

All values are kept raw (no string formatting) so recorded depth replays exactly.
"""

from __future__ import annotations

import struct
from typing import Iterator, Optional

from recorder.depth_schema import DEPTH_LEVELS, SIDE_ASK, SIDE_BID

# Feed response codes (byte 3 of every packet)
FEED_BID = 41
FEED_ASK = 51
FEED_DISCONNECT = 50

_FEED_TO_SIDE = {FEED_BID: SIDE_BID, FEED_ASK: SIDE_ASK}

_HEADER = struct.Struct("<HBBII")   # msg_len, feed_code, segment, security_id, msg_seq
HEADER_LEN = _HEADER.size           # 12
_LEVEL = struct.Struct("<dII")      # price, qty, orders
LEVEL_LEN = _LEVEL.size             # 16
PACKET_LEN = HEADER_LEN + DEPTH_LEVELS * LEVEL_LEN   # 332

# Disconnect control packet (see docs): 8-byte header + int16 reason.
_DISCONNECT_REASON = struct.Struct("<H")

DISCONNECT_CODES = {
    805: "exceeded max connections",
    806: "data-api not subscribed",
    807: "access token expired",
    808: "invalid client id",
    809: "auth failed",
}


def split_depth_frame(data: bytes) -> Iterator[bytes]:
    """Yield individual packets from a (possibly multi-packet) frame.

    Depth packets are a fixed 332 bytes, so for a bid/ask feed code we advance by
    that fixed length (robust to any msg_len quirk). For a non-depth control
    packet we fall back to the header's message_length. A truncated trailing
    fragment stops the walk cleanly rather than raising.
    """
    n = len(data)
    off = 0
    while off + HEADER_LEN <= n:
        msg_len, feed_code, _seg, _sid, _seq = _HEADER.unpack_from(data, off)
        if feed_code in _FEED_TO_SIDE:
            plen = PACKET_LEN
        elif msg_len >= HEADER_LEN:
            plen = msg_len
        else:
            break  # unknown packet with no usable length; stop rather than guess
        if off + plen > n:
            break  # truncated trailing packet; wait for more data
        yield data[off:off + plen]
        off += plen


def parse_depth_packet(packet: bytes) -> Optional[dict]:
    """Parse one depth (or control) packet.

    Returns a side-tagged depth row (``is_depth=True``) for a bid/ask packet with
    every level filled; an event dict (``is_depth=False``) for a disconnect; or
    None for an unrecognized/too-short packet. ``ts_recv_ns`` and ``seq_local``
    are stamped by the caller (as in R0), never here.
    """
    if len(packet) < HEADER_LEN:
        return None
    msg_len, feed_code, segment, security_id, msg_seq = _HEADER.unpack_from(packet, 0)

    if feed_code in _FEED_TO_SIDE:
        if len(packet) < PACKET_LEN:
            return None
        row: dict = {
            "is_depth": True,
            "security_id": security_id,
            "exchange_segment": segment,
            "side": _FEED_TO_SIDE[feed_code],
            "msg_seq": msg_seq,
        }
        off = HEADER_LEN
        for lvl in range(1, DEPTH_LEVELS + 1):
            price, qty, orders = _LEVEL.unpack_from(packet, off)
            row[f"price_{lvl}"] = price
            row[f"qty_{lvl}"] = qty
            row[f"orders_{lvl}"] = orders
            off += LEVEL_LEN
        return row

    if feed_code == FEED_DISCONNECT:
        code = None
        # reason int16 sits right after the (variable) header; be tolerant.
        if len(packet) >= HEADER_LEN + _DISCONNECT_REASON.size:
            (code,) = _DISCONNECT_REASON.unpack_from(packet, HEADER_LEN)
        return {
            "is_depth": False, "event": "disconnect", "feed_code": feed_code,
            "security_id": security_id, "exchange_segment": segment,
            "reason_code": code, "reason": DISCONNECT_CODES.get(code, "unknown"),
        }

    return {
        "is_depth": False, "event": "unknown", "feed_code": feed_code,
        "security_id": security_id, "exchange_segment": segment,
    }


def parse_depth_frame(data: bytes) -> Iterator[dict]:
    """Split a frame and yield parsed dicts (skipping None)."""
    for packet in split_depth_frame(data):
        parsed = parse_depth_packet(packet)
        if parsed is not None:
            yield parsed
