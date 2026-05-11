"""Self-contained Dhan v2 WebSocket adapter — live tick + candle stream.

Maintains a single async WebSocket connection to Dhan's market-data feed,
decodes the binary tick frames into :class:`~app.schemas.candle.TickData`,
folds them into rolling :class:`~app.schemas.candle.Candle` bars per
``(symbol, timeframe)``, and publishes both onto Redis pub/sub channels
defined in :mod:`app.services.chart_redis`.

This module is the producer side of the chart-module fanout. Consumers
(the live chart WebSocket endpoint, ops dashboards) subscribe to the
``chart:ticks:*`` / ``chart:candles:*`` channels — they do NOT see the
broker connection directly.

Coordination
------------
This file is part of the chart-module branch (``feat/charting-module``)
and follows the **new-files-only** coordination rule:

* Does NOT import from :mod:`app.brokers.dhan` (the existing REST
  adapter) — concurrent CC session may be editing it.
* Does NOT modify :mod:`app.core.config` — the WS URL is sourced from
  ``os.environ["DHAN_WS_URL"]`` with a documented default.
* Reuses :mod:`app.services.chart_redis` for channel naming / publish
  helpers (chart-namespaced helpers in a new file, import only).

Both of the above are flagged in ``backend/PATCH_INSTRUCTIONS.md`` as
future consolidations.

Architecture
------------
::

    Dhan WS (binary frames)
            │
            ▼
    _decode_binary_frame  ──►  TickData
            │
            ├──► publish_json(chart:ticks:{sym}, tick)
            │
            ▼
    _CandleAggregator      (one rolling bucket per (symbol, tf))
            │
            └──► publish_json(chart:candles:{sym}:{tf}, candle)
                 [on bucket roll = candle close]

Reconnect + disconnect signalling
---------------------------------
* Exponential backoff: 1 → 2 → 4 → 8 → 16 → 32s, capped at 60s, with
  ±25% full jitter. Implemented in :func:`_reconnect_delay`.
* **Log spam control:** INFO on attempt #1 of an outage, WARN on every
  10th attempt thereafter. No per-attempt INFO floods.
* **5-minute disconnect threshold:** if reconnect attempts continue
  failing for ≥5 minutes, emit a :class:`BrokerDisconnectedEvent` on
  ``chart:control:{symbol}`` for every subscribed symbol. The frontend
  catches this and renders a Hinglish banner — "Broker se connection
  toot gaya, retry kar rahe hain..."
* On recovery, emit exactly one :class:`BrokerReconnectedEvent` per
  subscribed symbol so the frontend can dismiss the banner.

Rate limiting
-------------
Dhan publishes 100 req/s as the binding subscribe/unsubscribe message
limit per connection. We throttle to **80 msg/s** at the producer side
(in :meth:`DhanWebSocketAdapter._send_subscription`) to keep 20%
headroom. Live ticks coming the other way are not rate-limited — we
just consume them as fast as Dhan sends them.

Binary protocol notes (Dhan v2 market-data feed)
------------------------------------------------
Every frame starts with a 16-byte header:

    +--------+--------+--------+--------+
    | RC (1) | Length (2 LE)   | EXS(1) |
    +--------+--------+--------+--------+
    |     SecurityId (4 LE)             |
    +--------+--------+--------+--------+
    |        reserved / msg-seq (8)     |
    +--------+--------+--------+--------+

Where:
    * RC  — response code: 4=Ticker, 7=Quote, 50=Disconnection signal.
    * EXS — exchange-segment code: see ``_EXS_BYTE_TO_SEGMENT``.

Payloads for the supported codes:
    * 4 (Ticker): 4B float32 LTP + 4B uint32 LTT (epoch seconds).
    * 7 (Quote) : 4B LTP + 2B LTQ + 4B LTT + 4B ATP + 4B vol +
                  4B sell_qty + 4B buy_qty + 4B open + 4B close +
                  4B high + 4B low (all float32 / uint LE).
    * 50 (Disc) : server-initiated disconnection; treat as upstream
                  drop and reconnect.

Layout verified against Dhan v2 public docs as of 2026-05-11. Operator
should re-verify against the current Dhan binary spec before deploy —
flagged in ``PATCH_INSTRUCTIONS.md``.

Subscribe message format (RequestCode = 15 for Quote, 21 for Ticker):
    ``{"RequestCode": 15, "InstrumentCount": N,``
    ``"InstrumentList": [{"ExchangeSegment": "NSE_EQ", "SecurityId": "11536"}, ...]}``

Per-user instantiation
----------------------
Each adapter instance is bound to one user's Dhan credentials. Caller
(typically the chart route's lifespan or a dedicated worker) constructs
``DhanWebSocketAdapter(client_id=..., access_token=..., user_id=...)``,
calls ``await adapter.start()`` once, then ``await adapter.subscribe(...)``
per symbol the user wants to chart. ``stop()`` on teardown.

Yeh adapter ek hi WebSocket connection pe multiple symbols subscribe
karta hai; aggregator candles bhi parallel mein build karta hai. Auto-
reconnect aur log-spam control built-in hain.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import struct
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.candle import (
    BrokerDisconnectedEvent,
    BrokerReconnectedEvent,
    Candle,
    TickData,
    Timeframe,
)
from app.services.chart_redis import (
    chart_candles_channel,
    chart_control_channel,
    chart_ticks_channel,
    publish_json,
)

if TYPE_CHECKING:
    # Avoid hard import at top-level so this module can be loaded for
    # static analysis / docs without the websockets library installed.
    # ``websockets>=13`` is a runtime dep — see PATCH_INSTRUCTIONS.md.
    from websockets.asyncio.client import ClientConnection


_logger = get_logger("brokers.dhan_websocket")


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════


#: Default Dhan v2 market-data WebSocket endpoint. Override via env var
#: ``DHAN_WS_URL`` (e.g. when targeting a sandbox). Inlined here per the
#: new-files-only rule — future move to :class:`Settings.dhan_ws_url`
#: flagged in ``PATCH_INSTRUCTIONS.md``.
DHAN_WS_URL: str = os.environ.get("DHAN_WS_URL", "wss://api-feed.dhan.co")

#: WebSocket library ping interval / timeout — survives idle periods on
#: slow links without aggressive resets.
_WS_PING_INTERVAL_S = 20.0
_WS_PING_TIMEOUT_S = 20.0

#: Reconnect backoff — exponential with jitter, capped.
_RECONNECT_BASE_DELAY_S = 1.0
_RECONNECT_MAX_DELAY_S = 60.0
_RECONNECT_JITTER_FACTOR = 0.25

#: Log-spam control: INFO on attempt 1, WARN on every Nth attempt after.
_RECONNECT_WARN_EVERY_N = 10

#: Disconnect threshold: emit BROKER_DISCONNECTED after this many
#: seconds of continuous reconnect failure.
_DISCONNECT_THRESHOLD_S = 5 * 60  # 5 minutes

#: Producer-side subscribe-message throttle. Dhan limit is 100 msg/s;
#: 80/s leaves headroom. Implemented as an asyncio.Semaphore-backed
#: token release once per ``_SUB_THROTTLE_WINDOW_S / _SUB_THROTTLE_MAX``.
_SUB_THROTTLE_MAX = 80
_SUB_THROTTLE_WINDOW_S = 1.0

#: Dhan binary header layout — fixed 16 bytes.
_HEADER_LEN = 16

#: Dhan response codes we know how to decode.
_RC_TICKER = 4
_RC_QUOTE = 7
_RC_DISCONNECT = 50

#: Map of Dhan binary exchange-segment byte → canonical segment string
#: matching :class:`TickData.exchange_segment` values.
_EXS_BYTE_TO_SEGMENT: dict[int, str] = {
    0: "IDX_I",
    1: "NSE_EQ",
    2: "NSE_FNO",
    3: "NSE_CURRENCY",
    4: "BSE_EQ",
    5: "MCX_COMM",
    7: "BSE_CURRENCY",
    8: "BSE_FNO",
}

#: Subscribe request codes. Map our intent ("I want ticker frames")
#: onto Dhan's protocol vocabulary.
_REQ_SUBSCRIBE_TICKER = 15  # Subscribes to Code-4 Ticker frames
_REQ_SUBSCRIBE_QUOTE = 17  # Subscribes to Code-7 Quote frames
_REQ_UNSUBSCRIBE = 16


# ═══════════════════════════════════════════════════════════════════════
# Binary frame decoder
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class _DecodedHeader:
    """Parsed 16-byte Dhan binary header."""

    response_code: int
    message_length: int
    exchange_segment_byte: int
    security_id: int

    @property
    def exchange_segment(self) -> str:
        return _EXS_BYTE_TO_SEGMENT.get(self.exchange_segment_byte, "UNKNOWN")


def _decode_header(buf: bytes) -> _DecodedHeader:
    """Parse the fixed 16-byte Dhan frame header.

    Layout (little-endian):
        offset 0  : uint8  response_code
        offset 1-2: uint16 message_length
        offset 3  : uint8  exchange_segment
        offset 4-7: uint32 security_id
        offset 8-15: reserved / msg-seq (ignored)

    Raises:
        ValueError: ``buf`` is shorter than 16 bytes — corrupt frame.
    """
    if len(buf) < _HEADER_LEN:
        raise ValueError(
            f"Dhan binary frame truncated: got {len(buf)} bytes, "
            f"need at least {_HEADER_LEN} for header."
        )
    rc, length, exs, sid = struct.unpack_from("<BHBI", buf, 0)
    return _DecodedHeader(
        response_code=int(rc),
        message_length=int(length),
        exchange_segment_byte=int(exs),
        security_id=int(sid),
    )


def _decode_binary_frame(
    buf: bytes, *, symbol_for: Callable[[int, str], str | None]
) -> TickData | None:
    """Decode one Dhan binary frame into a :class:`TickData`.

    Returns ``None`` for frames we deliberately skip:
        * Disconnection signal frames (handled at the connection layer).
        * Frame types not in {Ticker, Quote} — index updates, OI, depth.
        * Frames whose ``security_id`` we have no symbol mapping for
          (caller hasn't subscribed yet, or scrip master is stale).

    Args:
        buf: Raw bytes from the WebSocket.
        symbol_for: Callable that resolves ``(security_id, exchange_segment)``
            → trading symbol. The adapter owns this state and passes a
            closure; keeping the function pure makes the decoder
            testable in isolation.

    Raises:
        ValueError: Header truncated, payload truncated, or unknown
            exchange-segment byte. Caller should log and continue
            reading the next frame.
    """
    header = _decode_header(buf)

    if header.response_code == _RC_DISCONNECT:
        # Signalled disconnect — outer connection-loop catches the
        # subsequent socket close. Nothing to publish.
        return None

    if header.response_code not in (_RC_TICKER, _RC_QUOTE):
        # Frame type we don't currently consume (index ticks, OI, full
        # market, 20-depth). Skip cleanly so a Dhan tenant variant that
        # sends mixed types doesn't poison the channel.
        return None

    segment = _EXS_BYTE_TO_SEGMENT.get(header.exchange_segment_byte)
    if segment is None:
        raise ValueError(
            f"Unknown Dhan exchange-segment byte: {header.exchange_segment_byte}"
        )

    symbol = symbol_for(header.security_id, segment)
    if symbol is None:
        # The subscribe was racy or the scrip master is stale. Skipping
        # is correct — once the resolver knows about this security_id
        # the next tick will publish.
        return None

    if header.response_code == _RC_TICKER:
        if len(buf) < _HEADER_LEN + 8:
            raise ValueError(
                f"Dhan Ticker frame truncated: got {len(buf)} bytes, need "
                f"{_HEADER_LEN + 8}."
            )
        (ltp_raw, ltt) = struct.unpack_from("<fI", buf, _HEADER_LEN)
        ltq = 0
        volume = 0
    else:  # _RC_QUOTE
        # 12 mandatory fields after header; payload runs 58 bytes.
        payload_size = 4 + 2 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4  # = 42 bytes
        if len(buf) < _HEADER_LEN + payload_size:
            raise ValueError(
                f"Dhan Quote frame truncated: got {len(buf)} bytes, need "
                f"{_HEADER_LEN + payload_size}."
            )
        # struct format: float, uint16, uint32, float×8
        # ``<fHIfIIIffff`` packs to 42 bytes exactly:
        #   LTP, LTQ, LTT, ATP, Volume, TotalSellQty, TotalBuyQty,
        #   Open, Close, High, Low
        (ltp_raw, ltq_raw, ltt, _atp, vol, _sellq, _buyq, _o, _c, _h, _l) = (
            struct.unpack_from("<fHIfIIIffff", buf, _HEADER_LEN)
        )
        ltq = int(ltq_raw)
        volume = int(vol)

    if not math.isfinite(ltp_raw) or ltp_raw <= 0:
        # Zero/NaN LTP usually means "no trade yet today" (pre-open).
        # The schema rejects ltp <= 0, so we skip rather than raise.
        return None

    timestamp = datetime.fromtimestamp(int(ltt), tz=UTC)
    # Decimal(str(float)) avoids the lossy float→Decimal conversion that
    # would otherwise leak FPU rounding into the published price.
    ltp = Decimal(format(ltp_raw, ".4f"))

    return TickData(
        symbol=symbol,
        exchange_segment=segment,
        ltp=ltp,
        last_traded_quantity=ltq,
        volume=volume,
        timestamp=timestamp,
    )


def _build_subscribe_message(
    request_code: int, instruments: list[tuple[str, str]]
) -> str:
    """Build the JSON SUBSCRIBE/UNSUBSCRIBE payload Dhan expects.

    Args:
        request_code: One of ``_REQ_SUBSCRIBE_TICKER``,
            ``_REQ_SUBSCRIBE_QUOTE``, ``_REQ_UNSUBSCRIBE``.
        instruments: List of ``(exchange_segment, security_id)`` tuples.
            ``security_id`` is sent as a string per Dhan v2 spec even
            though it's numerically a uint32.

    Returns:
        JSON string ready to send over the WebSocket.
    """
    if not instruments:
        raise ValueError("instruments must be a non-empty list.")
    return json.dumps(
        {
            "RequestCode": request_code,
            "InstrumentCount": len(instruments),
            "InstrumentList": [
                {"ExchangeSegment": seg, "SecurityId": str(sid)}
                for seg, sid in instruments
            ],
        }
    )


# ═══════════════════════════════════════════════════════════════════════
# Candle aggregator
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class _Bucket:
    """One in-flight OHLC bar for a (symbol, timeframe) pair.

    Volume is tracked as ``(start_volume, last_volume)`` because Dhan
    ticks report **cumulative day volume**, not per-tick increments.
    The candle's volume is ``max(0, last_volume - start_volume)``.
    """

    symbol: str
    timeframe: Timeframe
    bucket_start: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    start_volume: int
    last_volume: int

    def to_candle(self) -> Candle:
        return Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=self.bucket_start,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=max(0, self.last_volume - self.start_volume),
        )


def _bucket_start(ts: datetime, tf: Timeframe) -> datetime:
    """Snap ``ts`` down to the start of its ``tf`` bucket (UTC)."""
    epoch = int(ts.timestamp())
    snapped = (epoch // tf.seconds) * tf.seconds
    return datetime.fromtimestamp(snapped, tz=UTC)


class _CandleAggregator:
    """Folds ticks into rolling OHLC bars per (symbol, timeframe).

    Stateful but single-threaded: there is exactly one instance per
    adapter, and ``fold()`` is only called from the reader coroutine.
    No locking needed.

    On a bucket roll the current bar is yielded as a finalised
    :class:`Candle`; the new bucket starts with ``open == ltp``.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, Timeframe], _Bucket] = {}

    def fold(self, tick: TickData, timeframes: list[Timeframe]) -> list[Candle]:
        """Apply ``tick`` to every bucket for ``timeframes`` of its symbol.

        Returns the list of bars that closed as a result of this tick
        (one per timeframe whose bucket boundary was crossed). The
        list is usually empty (mid-bucket ticks) and length 1 for an
        in-tick roll; length > 1 only if multiple timeframes happened
        to roll on the same tick (rare).
        """
        closed: list[Candle] = []
        for tf in timeframes:
            key = (tick.symbol, tf)
            new_start = _bucket_start(tick.timestamp, tf)
            existing = self._buckets.get(key)
            if existing is None:
                self._buckets[key] = _Bucket(
                    symbol=tick.symbol,
                    timeframe=tf,
                    bucket_start=new_start,
                    open=tick.ltp,
                    high=tick.ltp,
                    low=tick.ltp,
                    close=tick.ltp,
                    start_volume=tick.volume,
                    last_volume=tick.volume,
                )
                continue
            if new_start > existing.bucket_start:
                # Bucket boundary crossed. Finalise the existing bar
                # (with its current close = previous tick's ltp) and
                # start a fresh bucket from this tick.
                closed.append(existing.to_candle())
                self._buckets[key] = _Bucket(
                    symbol=tick.symbol,
                    timeframe=tf,
                    bucket_start=new_start,
                    open=tick.ltp,
                    high=tick.ltp,
                    low=tick.ltp,
                    close=tick.ltp,
                    start_volume=tick.volume,
                    last_volume=tick.volume,
                )
                continue
            # Mid-bucket tick — update high/low/close + volume marker.
            existing.high = max(existing.high, tick.ltp)
            existing.low = min(existing.low, tick.ltp)
            existing.close = tick.ltp
            existing.last_volume = tick.volume
        return closed

    def drop_symbol(self, symbol: str) -> list[Candle]:
        """Finalise + drop every in-flight bucket for ``symbol``.

        Used on unsubscribe so the last partial bar is published
        rather than silently dropped.
        """
        finalised: list[Candle] = []
        upper = symbol.upper()
        keys = [k for k in self._buckets if k[0] == upper]
        for k in keys:
            finalised.append(self._buckets.pop(k).to_candle())
        return finalised


# ═══════════════════════════════════════════════════════════════════════
# Subscribe-message throttle (token bucket)
# ═══════════════════════════════════════════════════════════════════════


class _MessageThrottle:
    """Simple async token bucket: refills ``capacity`` tokens every
    ``window_seconds``. ``acquire()`` returns immediately if a token
    is available; otherwise sleeps until the next refill.

    Used to keep our SUBSCRIBE/UNSUBSCRIBE rate below Dhan's 100/s
    binding cap. Implemented inline rather than reaching for a Redis
    rate-limit helper because this throttle is purely local (one
    connection = one process) and 80/s is the spec — no cross-worker
    coordination required.
    """

    def __init__(self, capacity: int, window_seconds: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._capacity = capacity
        self._window = window_seconds
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Sleep until at least one token would be available.
                wait = self._window / self._capacity
                await asyncio.sleep(wait)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        refill = elapsed * (self._capacity / self._window)
        self._tokens = min(self._capacity, self._tokens + refill)
        self._last_refill = now


# ═══════════════════════════════════════════════════════════════════════
# Subscription state
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class _Subscription:
    """One symbol the adapter is tracking.

    ``timeframes`` is mutable so adding a new timeframe later doesn't
    require unsubscribe/resubscribe at Dhan's end.
    """

    symbol: str
    security_id: int
    exchange_segment: str
    timeframes: list[Timeframe] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# Type aliases (kept after the dataclasses they reference)
# ═══════════════════════════════════════════════════════════════════════


#: Test seam — the adapter calls this to obtain a websocket connection.
#: Default implementation is ``websockets.asyncio.client.connect``,
#: which returns an async context manager yielding a
#: :class:`ClientConnection` whose ``recv()`` yields ``bytes | str``.
ConnectFactory = Callable[..., Any]


# ═══════════════════════════════════════════════════════════════════════
# Adapter
# ═══════════════════════════════════════════════════════════════════════


class DhanWebSocketAdapter:
    """Long-lived Dhan v2 market-data WebSocket consumer.

    Lifecycle:

        adapter = DhanWebSocketAdapter(
            client_id=...,
            access_token=...,
            user_id=...,
        )
        await adapter.start()              # spawns background reader
        await adapter.subscribe(            # idempotent
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[Timeframe.ONE_MIN, Timeframe.FIVE_MIN],
        )
        ...
        await adapter.unsubscribe("NIFTY")
        await adapter.stop()

    The reader is one ``asyncio.Task`` that:
        1. Opens the websocket via :attr:`_connect_factory`.
        2. Re-issues every active subscription (so reconnects are
           transparent).
        3. Reads frames in a loop and routes them through the decoder
           + aggregator + publish pipeline.
        4. On any exception, increments the reconnect counter, computes
           a backoff delay, sleeps, and retries — forever, until
           :meth:`stop` cancels the task.

    The adapter is **not** thread-safe; treat it as a per-process
    singleton (or per-user singleton if you're hosting multiple
    independent user feeds in one worker).
    """

    def __init__(
        self,
        *,
        client_id: str,
        access_token: str,
        user_id: UUID | str,
        ws_url: str = DHAN_WS_URL,
        connect_factory: ConnectFactory | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not client_id or not client_id.strip():
            raise ValueError("client_id must be non-empty.")
        if not access_token or not access_token.strip():
            raise ValueError("access_token must be non-empty.")
        user_id_str = str(user_id).strip()
        if not user_id_str:
            raise ValueError("user_id must be non-empty.")

        self._client_id = client_id.strip()
        self._access_token = access_token.strip()
        self._user_id = user_id_str
        self._ws_url = ws_url
        self._connect_factory = connect_factory
        self._sleep = sleep

        self._subscriptions: dict[str, _Subscription] = {}
        # security_id → symbol resolver, fed by .subscribe() calls.
        self._sid_to_symbol: dict[tuple[int, str], str] = {}
        self._aggregator = _CandleAggregator()
        self._throttle = _MessageThrottle(
            capacity=_SUB_THROTTLE_MAX, window_seconds=_SUB_THROTTLE_WINDOW_S
        )

        self._ws: ClientConnection | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

        # Reconnect / disconnect-threshold state.
        self._reconnect_attempt = 0
        self._outage_started_monotonic: float | None = None
        self._outage_started_at: datetime | None = None
        self._disconnect_emitted = False

        self._log = _logger.bind(
            user_id=self._user_id,
            client_id=self._client_id,
        )

    # ──────────────────────────────────────────────────────────────────
    # Public lifecycle
    # ──────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Spawn the background reader. Idempotent."""
        if self._reader_task is not None and not self._reader_task.done():
            return
        self._stopping.clear()
        self._reader_task = asyncio.create_task(
            self._connection_loop(),
            name=f"dhan_ws_reader[{self._user_id}]",
        )
        self._log.info("dhan_ws.started")

    async def stop(self) -> None:
        """Signal the reader to exit and close the socket. Idempotent."""
        self._stopping.set()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001 — close-time errors must not leak
                pass
            self._ws = None
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._reader_task = None
        self._log.info("dhan_ws.stopped")

    async def __aenter__(self) -> DhanWebSocketAdapter:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.stop()

    # ──────────────────────────────────────────────────────────────────
    # Subscribe / unsubscribe
    # ──────────────────────────────────────────────────────────────────

    async def subscribe(
        self,
        *,
        symbol: str,
        security_id: int,
        exchange_segment: str,
        timeframes: list[Timeframe],
        request_code: int = _REQ_SUBSCRIBE_QUOTE,
    ) -> None:
        """Subscribe to live ticks + candle aggregation for one symbol.

        Idempotent at the symbol level. Adding new timeframes to an
        already-subscribed symbol is also supported — call again with
        a superset list. The Dhan-side SUBSCRIBE message is only sent
        on the first call per symbol.

        Args:
            symbol: Trading symbol, upper-cased internally.
            security_id: Dhan numeric securityId (caller resolves this
                from the scrip master — this module does NOT duplicate
                that cache).
            exchange_segment: ``NSE_EQ`` / ``NSE_FNO`` / etc.
            timeframes: List of :class:`Timeframe` to aggregate into
                candles. Empty list is allowed — ticks still publish.
            request_code: Dhan SUBSCRIBE request code. Defaults to
                Quote frames (more OHLC data); use Ticker for cheaper
                LTP-only feeds.
        """
        upper = symbol.strip().upper()
        seg = exchange_segment.strip().upper()
        if not upper:
            raise ValueError("symbol must be non-empty.")
        if security_id <= 0:
            raise ValueError(f"security_id must be > 0, got {security_id}.")
        if seg not in _EXS_BYTE_TO_SEGMENT.values():
            raise ValueError(
                f"Unknown exchange_segment {seg!r}. Supported: "
                f"{sorted(set(_EXS_BYTE_TO_SEGMENT.values()))}"
            )

        existing = self._subscriptions.get(upper)
        if existing is not None:
            # Merge new timeframes; don't re-send SUBSCRIBE.
            for tf in timeframes:
                if tf not in existing.timeframes:
                    existing.timeframes.append(tf)
            return

        sub = _Subscription(
            symbol=upper,
            security_id=security_id,
            exchange_segment=seg,
            timeframes=list(timeframes),
        )
        self._subscriptions[upper] = sub
        self._sid_to_symbol[(security_id, seg)] = upper

        if self._ws is not None:
            await self._send_subscription(
                [sub], request_code=request_code, subscribing=True
            )

    async def unsubscribe(self, symbol: str) -> None:
        """Drop ``symbol`` from the active set + finalise its partial bars."""
        upper = symbol.strip().upper()
        sub = self._subscriptions.pop(upper, None)
        if sub is None:
            return
        self._sid_to_symbol.pop((sub.security_id, sub.exchange_segment), None)

        # Flush partial candles for the symbol so the chart shows the
        # last bar's progress at the moment of unsubscribe rather than
        # an open-ended bucket.
        for closed in self._aggregator.drop_symbol(upper):
            await publish_json(
                chart_candles_channel(closed.symbol, closed.timeframe.value),
                closed.model_dump(mode="json"),
            )

        if self._ws is not None:
            try:
                await self._send_subscription(
                    [sub], request_code=_REQ_UNSUBSCRIBE, subscribing=False
                )
            except Exception:  # noqa: BLE001
                # Best-effort unsubscribe; if Dhan never receives it,
                # the worst case is wasted bandwidth until reconnect.
                self._log.warning(
                    "dhan_ws.unsubscribe_send_failed", symbol=upper
                )

    # ──────────────────────────────────────────────────────────────────
    # Connection loop
    # ──────────────────────────────────────────────────────────────────

    async def _connection_loop(self) -> None:
        """Reconnect-forever outer loop. Exits only on :meth:`stop`."""
        while not self._stopping.is_set():
            try:
                async with self._open_connection() as ws:
                    self._ws = ws
                    await self._on_connected()
                    await self._read_loop(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await self._on_disconnect(exc)
                if self._stopping.is_set():
                    break
                delay = _reconnect_delay(self._reconnect_attempt)
                await self._sleep(delay)
            finally:
                self._ws = None

    async def _open_connection(self) -> Any:
        """Build the WebSocket connect call.

        Lazy-imports ``websockets`` so module import works in tests
        even when the lib is absent and a fake ``connect_factory`` is
        injected.
        """
        url = (
            f"{self._ws_url}?version=2&token={self._access_token}"
            f"&clientId={self._client_id}&authType=2"
        )
        if self._connect_factory is None:
            from websockets.asyncio.client import connect as ws_connect
            return ws_connect(
                url,
                ping_interval=_WS_PING_INTERVAL_S,
                ping_timeout=_WS_PING_TIMEOUT_S,
                max_size=2**20,
            )
        return self._connect_factory(url)

    async def _on_connected(self) -> None:
        """Reset reconnect state + re-issue every active subscription."""
        if self._disconnect_emitted:
            # We had crossed the 5-min threshold — emit recovery so the
            # frontend dismisses its banner.
            await self._emit_reconnected_event()
        self._reconnect_attempt = 0
        self._outage_started_monotonic = None
        self._outage_started_at = None
        self._disconnect_emitted = False

        self._log.info("dhan_ws.connected", symbols=list(self._subscriptions))
        if self._subscriptions:
            await self._send_subscription(
                list(self._subscriptions.values()),
                request_code=_REQ_SUBSCRIBE_QUOTE,
                subscribing=True,
            )

    async def _on_disconnect(self, exc: BaseException) -> None:
        """Bookkeeping after a connection drop.

        Increments ``_reconnect_attempt``, opens the outage window
        clock if this is the first failure of an outage, and emits a
        BROKER_DISCONNECTED event once we cross the 5-minute threshold.
        """
        self._reconnect_attempt += 1
        now_mono = time.monotonic()
        now_utc = datetime.now(UTC)
        if self._outage_started_monotonic is None:
            self._outage_started_monotonic = now_mono
            self._outage_started_at = now_utc

        attempt = self._reconnect_attempt
        # Log-spam control: INFO on attempt 1, WARN on every Nth after.
        if attempt == 1:
            self._log.info(
                "dhan_ws.disconnected",
                attempt=attempt,
                error=type(exc).__name__,
                error_message=str(exc),
            )
        elif attempt % _RECONNECT_WARN_EVERY_N == 0:
            self._log.warning(
                "dhan_ws.reconnect_failing",
                attempt=attempt,
                outage_seconds=int(now_mono - (self._outage_started_monotonic or now_mono)),
                error=type(exc).__name__,
            )

        # 5-minute threshold check.
        elapsed = now_mono - self._outage_started_monotonic
        if elapsed >= _DISCONNECT_THRESHOLD_S and not self._disconnect_emitted:
            await self._emit_disconnected_event(
                reason=f"{type(exc).__name__}: {exc}",
                failed_attempts=attempt,
                since=self._outage_started_at or now_utc,
            )
            self._disconnect_emitted = True

    async def _emit_disconnected_event(
        self, *, reason: str, failed_attempts: int, since: datetime
    ) -> None:
        """Publish a BROKER_DISCONNECTED event on every subscribed symbol."""
        for sym in list(self._subscriptions):
            event = BrokerDisconnectedEvent(
                symbol=sym,
                reason=reason,
                failed_attempts=failed_attempts,
                since=since,
            )
            try:
                await publish_json(
                    chart_control_channel(sym), event.model_dump(mode="json")
                )
            except Exception:  # noqa: BLE001
                self._log.warning(
                    "dhan_ws.control_publish_failed",
                    event="BROKER_DISCONNECTED",
                    symbol=sym,
                )

    async def _emit_reconnected_event(self) -> None:
        """Publish exactly one BROKER_RECONNECTED event per symbol on recovery."""
        now = datetime.now(UTC)
        for sym in list(self._subscriptions):
            event = BrokerReconnectedEvent(symbol=sym, at=now)
            try:
                await publish_json(
                    chart_control_channel(sym), event.model_dump(mode="json")
                )
            except Exception:  # noqa: BLE001
                self._log.warning(
                    "dhan_ws.control_publish_failed",
                    event="BROKER_RECONNECTED",
                    symbol=sym,
                )

    # ──────────────────────────────────────────────────────────────────
    # Read loop + frame handling
    # ──────────────────────────────────────────────────────────────────

    async def _read_loop(self, ws: ClientConnection) -> None:
        """Pull frames until the socket closes."""
        async for raw in self._iter_frames(ws):
            if self._stopping.is_set():
                break
            if isinstance(raw, bytes):
                await self._handle_binary_frame(raw)
            elif isinstance(raw, str):
                # Dhan sometimes ACKs subscribe requests as JSON. We
                # log + ignore — the next binary frame is what we care
                # about.
                self._log.debug("dhan_ws.text_frame", body=raw[:200])

    async def _iter_frames(self, ws: ClientConnection) -> AsyncIterator[bytes | str]:
        """Async-iterate the websocket. Extracted for test injection.

        A real ``ClientConnection`` already supports ``async for`` so
        this is just a thin pass-through; the indirection lets us
        substitute a list of pre-canned frames in tests.
        """
        async for raw in ws:
            yield raw

    async def _handle_binary_frame(self, buf: bytes) -> None:
        """Decode → publish tick → fold into candles → publish closes."""
        try:
            tick = _decode_binary_frame(
                buf, symbol_for=self._symbol_for_sid
            )
        except ValueError as exc:
            self._log.warning(
                "dhan_ws.decode_failed",
                error=str(exc),
                buf_len=len(buf),
            )
            return
        if tick is None:
            return

        try:
            await publish_json(
                chart_ticks_channel(tick.symbol), tick.model_dump(mode="json")
            )
        except Exception:  # noqa: BLE001
            self._log.warning("dhan_ws.tick_publish_failed", symbol=tick.symbol)

        sub = self._subscriptions.get(tick.symbol)
        if sub is None or not sub.timeframes:
            return

        closed = self._aggregator.fold(tick, sub.timeframes)
        for candle in closed:
            try:
                await publish_json(
                    chart_candles_channel(candle.symbol, candle.timeframe.value),
                    candle.model_dump(mode="json"),
                )
            except Exception:  # noqa: BLE001
                self._log.warning(
                    "dhan_ws.candle_publish_failed",
                    symbol=candle.symbol,
                    timeframe=candle.timeframe.value,
                )

    def _symbol_for_sid(self, security_id: int, segment: str) -> str | None:
        """Resolver passed into the decoder."""
        return self._sid_to_symbol.get((security_id, segment))

    # ──────────────────────────────────────────────────────────────────
    # Subscribe message dispatch
    # ──────────────────────────────────────────────────────────────────

    async def _send_subscription(
        self,
        subs: list[_Subscription],
        *,
        request_code: int,
        subscribing: bool,
    ) -> None:
        """Throttle + send a SUBSCRIBE or UNSUBSCRIBE message.

        Dhan limits requests to 100/s; we self-cap at 80/s.
        """
        if not subs or self._ws is None:
            return
        await self._throttle.acquire()
        message = _build_subscribe_message(
            request_code,
            [(s.exchange_segment, str(s.security_id)) for s in subs],
        )
        try:
            await self._ws.send(message)
        except Exception as exc:  # noqa: BLE001
            self._log.warning(
                "dhan_ws.subscribe_send_failed",
                subscribing=subscribing,
                count=len(subs),
                error=type(exc).__name__,
            )
            raise


# ═══════════════════════════════════════════════════════════════════════
# Backoff helpers
# ═══════════════════════════════════════════════════════════════════════


def _reconnect_delay(attempt: int) -> float:
    """Return the next reconnect delay in seconds.

    Schedule:
        attempt 0 →  ~0 (instant)
        attempt 1 →  1s + jitter
        attempt 2 →  2s + jitter
        attempt 3 →  4s + jitter
        attempt 4 →  8s + jitter
        attempt 5 → 16s + jitter
        attempt 6 → 32s + jitter
        attempt ≥7 → 60s + jitter (capped)

    Jitter is full ±25% of the base delay so a thundering herd of
    workers waking up at the same moment can't all hammer Dhan in
    lockstep.
    """
    if attempt <= 0:
        return 0.0
    base = min(_RECONNECT_BASE_DELAY_S * (2 ** (attempt - 1)), _RECONNECT_MAX_DELAY_S)
    jitter = random.uniform(-base * _RECONNECT_JITTER_FACTOR, base * _RECONNECT_JITTER_FACTOR)
    return max(0.0, base + jitter)


__all__ = [
    "DHAN_WS_URL",
    "DhanWebSocketAdapter",
]
