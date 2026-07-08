"""Binary packet parser for the Dhan v2 Live Market Feed (Option B — own parser).

Layouts verified against:
  - https://dhanhq.co/docs/v2/live-market-feed/
  - dhanhq-py marketfeed struct formats (used as a cross-check reference)

All packets are little-endian. A single WebSocket binary frame may contain
several concatenated packets; use ``split_frame`` to break a frame into
individual packets before parsing.

Response header (8 bytes): <BHBI
    packet_type      uint8   (feed response code)
    message_length   uint16  (total packet length incl. this 8-byte header)
    exchange_segment uint8
    security_id      uint32

The parser is intentionally lossless: raw epoch ints and raw floats are kept
(no string formatting), so recorded ticks can be replayed for backtesting.
"""

from __future__ import annotations

import struct
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Packet type codes (first byte of every packet)
# ---------------------------------------------------------------------------
PKT_TICKER = 2
PKT_DEPTH = 3
PKT_QUOTE = 4
PKT_OI = 5
PKT_PREV_CLOSE = 6
PKT_STATUS = 7
PKT_FULL = 8
PKT_DISCONNECT = 50

# Human-readable labels for events/logging
PACKET_TYPE_NAMES = {
    PKT_TICKER: "ticker",
    PKT_DEPTH: "depth",
    PKT_QUOTE: "quote",
    PKT_OI: "oi",
    PKT_PREV_CLOSE: "prev_close",
    PKT_STATUS: "status",
    PKT_FULL: "full",
    PKT_DISCONNECT: "disconnect",
}

# Packet types we persist to the tick parquet (carry price/qty/oi data)
TICK_PACKET_TYPES = frozenset({PKT_FULL, PKT_QUOTE, PKT_OI, PKT_TICKER})

# Subscription request codes (JSON "RequestCode")
REQ_TICKER = 15
REQ_QUOTE = 17
REQ_DEPTH = 19
REQ_FULL = 21
REQ_DISCONNECT = 12

# Exchange segment string <-> numeric code
EXCHANGE_SEGMENTS = {
    "IDX_I": 0,
    "NSE_EQ": 1,
    "NSE_FNO": 2,
    "NSE_CURR": 3,
    "BSE_EQ": 4,
    "MCX_COMM": 5,
    "BSE_CURR": 7,
    "BSE_FNO": 8,
}
SEGMENT_CODE_TO_NAME = {v: k for k, v in EXCHANGE_SEGMENTS.items()}

# Disconnect reason codes (from feed docs)
DISCONNECT_CODES = {
    805: "exceeded max connections",
    806: "data-api not subscribed",
    807: "access token expired",
    808: "invalid client id",
    809: "auth failed",
}

_HEADER = struct.Struct("<BHBI")          # type, msg_len, segment, security_id
HEADER_LEN = _HEADER.size                 # 8

# Body structs (do NOT include the 8-byte header; slice past it first)
_FULL_BODY = struct.Struct("<fHIfIIIIIIffff")   # 54 bytes, then 100 bytes depth
_QUOTE_BODY = struct.Struct("<fHIfIIIffff")      # 42 bytes
_TICKER_BODY = struct.Struct("<fI")              # LTP, LTT
_OI_BODY = struct.Struct("<I")                   # OI
_PREV_CLOSE_BODY = struct.Struct("<fI")          # prev_close, prev_oi
_DISCONNECT_BODY = struct.Struct("<H")           # reason code
_DEPTH_LEVEL = struct.Struct("<IIHHff")          # bid_qty, ask_qty, bid_ord, ask_ord, bid_px, ask_px
DEPTH_LEVELS = 5
DEPTH_BYTES = _DEPTH_LEVEL.size * DEPTH_LEVELS    # 100

FULL_PACKET_LEN = HEADER_LEN + _FULL_BODY.size + DEPTH_BYTES  # 162

# Canonical null-filled tick schema keys (feed adds ts_recv_ns / seq_local)
_DEPTH_KEYS = []
for _i in range(1, DEPTH_LEVELS + 1):
    _DEPTH_KEYS += [
        f"bid_price_{_i}", f"bid_qty_{_i}", f"bid_orders_{_i}",
        f"ask_price_{_i}", f"ask_qty_{_i}", f"ask_orders_{_i}",
    ]

TICK_FIELDS = [
    "packet_type", "security_id", "ltt", "ltp", "ltq", "atp",
    "volume", "total_buy_qty", "total_sell_qty", "oi",
] + _DEPTH_KEYS


def _empty_tick() -> dict:
    """A tick dict with every schema field present and None where unset."""
    return {k: None for k in TICK_FIELDS}


def split_frame(data: bytes) -> Iterator[bytes]:
    """Yield individual packets from a (possibly multi-packet) WebSocket frame.

    Uses the header's message_length to walk the buffer. Stops cleanly on a
    truncated trailing fragment (yields nothing further) rather than raising,
    so a malformed tail can't crash the recorder.
    """
    n = len(data)
    off = 0
    while off + HEADER_LEN <= n:
        _pt, msg_len, _seg, _sid = _HEADER.unpack_from(data, off)
        # msg_len is the full packet length including the header. Some feeds
        # have historically reported 0 for fixed-size packets; fall back to a
        # known length by packet type when msg_len looks invalid.
        if msg_len < HEADER_LEN:
            msg_len = _fallback_len(_pt)
            if msg_len is None:
                break
        if off + msg_len > n:
            break  # truncated trailing packet; wait for more data
        yield data[off:off + msg_len]
        off += msg_len


def _fallback_len(packet_type: int) -> Optional[int]:
    if packet_type == PKT_FULL:
        return FULL_PACKET_LEN
    if packet_type == PKT_QUOTE:
        return HEADER_LEN + _QUOTE_BODY.size
    if packet_type == PKT_TICKER:
        return HEADER_LEN + _TICKER_BODY.size
    if packet_type == PKT_OI:
        return HEADER_LEN + _OI_BODY.size
    if packet_type == PKT_PREV_CLOSE:
        return HEADER_LEN + _PREV_CLOSE_BODY.size
    if packet_type == PKT_DISCONNECT:
        return HEADER_LEN + _DISCONNECT_BODY.size
    return None


def peek_header(packet: bytes) -> tuple[int, int, int, int]:
    """Return (packet_type, message_length, exchange_segment, security_id)."""
    return _HEADER.unpack_from(packet, 0)


def _parse_depth(body: bytes, start: int, tick: dict) -> None:
    for lvl in range(DEPTH_LEVELS):
        off = start + lvl * _DEPTH_LEVEL.size
        bid_qty, ask_qty, bid_ord, ask_ord, bid_px, ask_px = _DEPTH_LEVEL.unpack_from(body, off)
        i = lvl + 1
        tick[f"bid_qty_{i}"] = bid_qty
        tick[f"ask_qty_{i}"] = ask_qty
        tick[f"bid_orders_{i}"] = bid_ord
        tick[f"ask_orders_{i}"] = ask_ord
        tick[f"bid_price_{i}"] = bid_px
        tick[f"ask_price_{i}"] = ask_px


def parse_packet(packet: bytes) -> Optional[dict]:
    """Parse one packet into a normalized dict.

    For tick-bearing packets (full/quote/oi/ticker) returns a dict with every
    ``TICK_FIELDS`` key present (None where the packet lacks that field) plus
    the raw header fields. For non-tick packets (status/prev_close/disconnect)
    returns an event dict with ``event`` set and ``is_tick=False``. Returns
    None for an unrecognized/too-short packet.
    """
    if len(packet) < HEADER_LEN:
        return None
    packet_type, msg_len, segment, security_id = _HEADER.unpack_from(packet, 0)

    if packet_type == PKT_FULL:
        need = HEADER_LEN + _FULL_BODY.size + DEPTH_BYTES
        if len(packet) < need:
            return None
        (ltp, ltq, ltt, atp, volume, total_sell, total_buy, oi,
         oi_high, oi_low, day_open, day_close, day_high, day_low) = \
            _FULL_BODY.unpack_from(packet, HEADER_LEN)
        tick = _empty_tick()
        tick.update(
            packet_type=packet_type, security_id=security_id, ltt=ltt, ltp=ltp,
            ltq=ltq, atp=atp, volume=volume, total_buy_qty=total_buy,
            total_sell_qty=total_sell, oi=oi,
        )
        _parse_depth(packet, HEADER_LEN + _FULL_BODY.size, tick)
        tick["is_tick"] = True
        tick["exchange_segment"] = segment
        return tick

    if packet_type == PKT_QUOTE:
        if len(packet) < HEADER_LEN + _QUOTE_BODY.size:
            return None
        (ltp, ltq, ltt, atp, volume, total_sell, total_buy,
         day_open, day_close, day_high, day_low) = \
            _QUOTE_BODY.unpack_from(packet, HEADER_LEN)
        tick = _empty_tick()
        tick.update(
            packet_type=packet_type, security_id=security_id, ltt=ltt, ltp=ltp,
            ltq=ltq, atp=atp, volume=volume, total_buy_qty=total_buy,
            total_sell_qty=total_sell,
        )
        tick["is_tick"] = True
        tick["exchange_segment"] = segment
        return tick

    if packet_type == PKT_TICKER:
        if len(packet) < HEADER_LEN + _TICKER_BODY.size:
            return None
        ltp, ltt = _TICKER_BODY.unpack_from(packet, HEADER_LEN)
        tick = _empty_tick()
        tick.update(packet_type=packet_type, security_id=security_id, ltp=ltp, ltt=ltt)
        tick["is_tick"] = True
        tick["exchange_segment"] = segment
        return tick

    if packet_type == PKT_OI:
        if len(packet) < HEADER_LEN + _OI_BODY.size:
            return None
        (oi,) = _OI_BODY.unpack_from(packet, HEADER_LEN)
        tick = _empty_tick()
        tick.update(packet_type=packet_type, security_id=security_id, oi=oi)
        tick["is_tick"] = True
        tick["exchange_segment"] = segment
        return tick

    if packet_type == PKT_PREV_CLOSE:
        prev_close = prev_oi = None
        if len(packet) >= HEADER_LEN + _PREV_CLOSE_BODY.size:
            prev_close, prev_oi = _PREV_CLOSE_BODY.unpack_from(packet, HEADER_LEN)
        return {
            "is_tick": False, "event": "prev_close", "packet_type": packet_type,
            "security_id": security_id, "exchange_segment": segment,
            "prev_close": prev_close, "prev_oi": prev_oi,
        }

    if packet_type == PKT_STATUS:
        return {
            "is_tick": False, "event": "market_status", "packet_type": packet_type,
            "security_id": security_id, "exchange_segment": segment,
        }

    if packet_type == PKT_DISCONNECT:
        code = None
        if len(packet) >= HEADER_LEN + _DISCONNECT_BODY.size:
            (code,) = _DISCONNECT_BODY.unpack_from(packet, HEADER_LEN)
        return {
            "is_tick": False, "event": "disconnect", "packet_type": packet_type,
            "security_id": security_id, "exchange_segment": segment,
            "reason_code": code, "reason": DISCONNECT_CODES.get(code, "unknown"),
        }

    # PKT_DEPTH (3) and anything else: acknowledge but don't persist as a tick.
    return {
        "is_tick": False, "event": PACKET_TYPE_NAMES.get(packet_type, "unknown"),
        "packet_type": packet_type, "security_id": security_id,
        "exchange_segment": segment,
    }


def parse_frame(data: bytes) -> Iterator[dict]:
    """Convenience: split a frame and yield parsed dicts (skipping None)."""
    for packet in split_frame(data):
        parsed = parse_packet(packet)
        if parsed is not None:
            yield parsed
