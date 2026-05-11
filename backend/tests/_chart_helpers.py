"""Shared helpers for the chart-module test suite.

Pure factory functions — no ``@pytest.fixture`` decorators here. Each
per-subdir ``conftest.py`` can re-export these as fixtures with its own
scope; tests can also call them directly when they need multiple
instances of the same kind of payload.

The helpers fall into four buckets:

    * Pydantic model factories — ``make_tick``, ``make_candle``.
    * Dhan v2 binary frame builders — ``make_ticker_frame_bytes``,
      ``make_quote_frame_bytes``. These build byte strings whose layout
      exactly matches what :func:`app.brokers.dhan_websocket._decode_binary_frame`
      expects, so the decoder is tested against a known-good producer.
    * Dhan REST historical response builder — ``make_dhan_historical_response``.
    * Time helpers — ``IST_TZ``, ``utc_datetime``, ``ist_datetime``.
"""

from __future__ import annotations

import struct
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.schemas.candle import Candle, TickData, Timeframe


# ═══════════════════════════════════════════════════════════════════════
# Time helpers
# ═══════════════════════════════════════════════════════════════════════


#: IST (Indian Standard Time). Fixed UTC+5:30, no DST.
IST_TZ = timezone(timedelta(hours=5, minutes=30))


def utc_datetime(
    year: int = 2026,
    month: int = 5,
    day: int = 11,
    hour: int = 9,
    minute: int = 15,
    second: int = 0,
) -> datetime:
    """Aware UTC datetime — used as the canonical timestamp in test fixtures."""
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def ist_datetime(
    year: int = 2026,
    month: int = 5,
    day: int = 11,
    hour: int = 14,
    minute: int = 45,
    second: int = 0,
) -> datetime:
    """Aware IST datetime."""
    return datetime(year, month, day, hour, minute, second, tzinfo=IST_TZ)


# ═══════════════════════════════════════════════════════════════════════
# Pydantic model factories
# ═══════════════════════════════════════════════════════════════════════


def make_tick(
    *,
    symbol: str = "NIFTY",
    exchange_segment: str = "NSE_EQ",
    ltp: str = "22500.50",
    last_traded_quantity: int = 75,
    volume: int = 1_000_000,
    timestamp: datetime | None = None,
) -> TickData:
    """Construct a :class:`TickData` with sane defaults."""
    return TickData(
        symbol=symbol,
        exchange_segment=exchange_segment,
        ltp=Decimal(ltp),
        last_traded_quantity=last_traded_quantity,
        volume=volume,
        timestamp=timestamp if timestamp is not None else utc_datetime(),
    )


def make_candle(
    *,
    symbol: str = "NIFTY",
    timeframe: Timeframe = Timeframe.FIVE_MIN,
    timestamp: datetime | None = None,
    open: str = "22500.00",  # noqa: A002 — mirrors Pydantic field name
    high: str = "22510.50",
    low: str = "22498.25",
    close: str = "22505.75",
    volume: int = 250_000,
) -> Candle:
    """Construct a :class:`Candle` with sane defaults that satisfy the
    OHLC invariants (low ≤ open/close ≤ high)."""
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp if timestamp is not None else utc_datetime(),
        open=Decimal(open),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
    )


# ═══════════════════════════════════════════════════════════════════════
# Dhan v2 binary frame builders
# ═══════════════════════════════════════════════════════════════════════
#
# Layout matches the decoder in app.brokers.dhan_websocket — and the
# Dhan v2 published spec — exactly:
#
#   8-byte header: <BHBI
#       byte 0   : uint8  response_code (2=Ticker, 4=Quote, 5=OI,
#                                        6=PrevClose, 8=Full, 50=Disc)
#       bytes 1-2: uint16 message_length (LE)
#       byte 3   : uint8  exchange_segment
#       bytes 4-7: uint32 security_id (LE)
#
#   Ticker payload (8 bytes): <fI — LTP float32, LTT uint32 epoch
#   Quote payload (42 bytes): <fHIfIIIffff
#
# Note: earlier drafts of these helpers added 8 trailing reserved bytes
# between header and payload. That was wrong — Dhan's wire format has
# no such padding — and it masked a real ``_HEADER_LEN`` bug in source.
# Both sides corrected on 2026-05-11.


def make_ticker_frame_bytes(
    *,
    response_code: int = 2,  # Dhan v2 Ticker code
    exchange_segment_byte: int = 1,  # NSE_EQ
    security_id: int = 11536,
    ltp: float = 22500.50,
    ltt_epoch: int | None = None,
) -> bytes:
    """Build a valid Dhan v2 Ticker frame (default RC=2, 16 bytes total).

    Override fields to inject corrupt / edge-case shapes:

    >>> truncated = make_ticker_frame_bytes()[:10]   # missing 6 bytes
    >>> unknown_segment = make_ticker_frame_bytes(exchange_segment_byte=99)
    >>> oi_packet = make_ticker_frame_bytes(response_code=5)
    """
    if ltt_epoch is None:
        ltt_epoch = int(utc_datetime().timestamp())
    payload = struct.pack("<fI", float(ltp), int(ltt_epoch))
    message_length = 8 + len(payload)
    header = struct.pack(
        "<BHBI",
        response_code,
        message_length,
        exchange_segment_byte,
        security_id,
    )
    return header + payload


def make_quote_frame_bytes(
    *,
    response_code: int = 4,  # Dhan v2 Quote code
    exchange_segment_byte: int = 1,
    security_id: int = 11536,
    ltp: float = 22500.50,
    ltq: int = 75,
    ltt_epoch: int | None = None,
    atp: float = 22500.0,
    volume: int = 1_000_000,
    total_sell_qty: int = 50_000,
    total_buy_qty: int = 60_000,
    open_: float = 22500.00,
    close: float = 22480.00,
    high: float = 22510.50,
    low: float = 22498.25,
) -> bytes:
    """Build a valid Dhan v2 Quote frame (default RC=4, 50 bytes total)."""
    if ltt_epoch is None:
        ltt_epoch = int(utc_datetime().timestamp())
    payload = struct.pack(
        "<fHIfIIIffff",
        float(ltp),
        int(ltq),
        int(ltt_epoch),
        float(atp),
        int(volume),
        int(total_sell_qty),
        int(total_buy_qty),
        float(open_),
        float(close),
        float(high),
        float(low),
    )
    message_length = 8 + len(payload)
    header = struct.pack(
        "<BHBI",
        response_code,
        message_length,
        exchange_segment_byte,
        security_id,
    )
    return header + payload


def make_disconnect_frame_bytes(
    *,
    exchange_segment_byte: int = 1,
    security_id: int = 0,
) -> bytes:
    """Build a Dhan v2 Disconnect (RC=50) signal frame. Header-only, 8 bytes."""
    header = struct.pack(
        "<BHBI",
        50,
        8,
        exchange_segment_byte,
        security_id,
    )
    return header


# ═══════════════════════════════════════════════════════════════════════
# Dhan v2 REST /charts/historical response builder
# ═══════════════════════════════════════════════════════════════════════


def make_dhan_historical_response(
    *,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    closes: list[float] | None = None,
    volumes: list[int] | None = None,
    timestamps: list[int] | None = None,
    wrap_in_data: bool = False,
) -> dict[str, Any]:
    """Build a Dhan v2 ``/charts/historical`` response body.

    Defaults to a valid 3-bar response with monotonic OHLC. Pass any
    array explicitly to test edge cases (length mismatch, empty,
    malformed value).

    Args:
        wrap_in_data: When ``True``, wraps the body under a top-level
            ``{"data": {...}}`` — Dhan tenants vary on this; both
            shapes are supported by the parser.
    """
    base_ts = int(utc_datetime(hour=9, minute=15).timestamp())
    timestamps = (
        timestamps
        if timestamps is not None
        else [base_ts, base_ts + 300, base_ts + 600]
    )
    n = len(timestamps)
    opens = opens if opens is not None else [22500.0 + i for i in range(n)]
    highs = highs if highs is not None else [22510.0 + i for i in range(n)]
    lows = lows if lows is not None else [22495.0 + i for i in range(n)]
    closes = closes if closes is not None else [22505.0 + i for i in range(n)]
    volumes = (
        volumes
        if volumes is not None
        else [100_000 * (i + 1) for i in range(n)]
    )

    body: dict[str, Any] = {
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "timestamp": timestamps,
    }
    return {"data": body} if wrap_in_data else body


__all__ = [
    "IST_TZ",
    "ist_datetime",
    "make_candle",
    "make_dhan_historical_response",
    "make_disconnect_frame_bytes",
    "make_quote_frame_bytes",
    "make_ticker_frame_bytes",
    "make_tick",
    "utc_datetime",
]
