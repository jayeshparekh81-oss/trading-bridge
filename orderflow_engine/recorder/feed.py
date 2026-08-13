"""Dhan v2 Live Market Feed WebSocket client (raw websockets + own parser).

Responsibilities:
  * connect with token/clientId in the URL query (v2 auth)
  * subscribe the configured instrument list in FULL mode (chunks of <=100)
  * receive binary frames, split + parse them, stamp ts_recv_ns at receipt,
    and hand each parsed packet to the caller
  * auto-reconnect with exponential backoff (1->2->5->10->30s), resubscribe,
    and report downtime
  * rely on the websockets library for ping/pong; guard the 40s idle close

It holds a read-only Data-API token and NEVER places orders.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable, Optional

import websockets

from recorder.parser import REQ_FULL, REQ_QUOTE, parse_frame

log = logging.getLogger("recorder.feed")

WSS_URL = "wss://api-feed.dhan.co"
MAX_INSTRUMENTS_PER_MSG = 100
BACKOFF_SCHEDULE = [1, 2, 5, 10, 30]

# 2026-07-14 IDX_I zero-packet fix: index instruments have no order book, so
# Dhan emits NO Full(21) packet for them — they stream only via Quote(17)/
# Ticker(15). Subscribe IDX_I in Quote(17) (carries LTP); every other segment
# keeps this client's request_code (Full/21) unchanged.
IDX_SEGMENT = "IDX_I"
INDEX_REQUEST_CODE = REQ_QUOTE

# Callback signatures
PacketCb = Callable[[dict, int], None]          # (parsed_packet, ts_recv_ns)
EventCb = Callable[[str, str, Optional[float]], None]  # (kind, detail, value_num)


class FeedClient:
    def __init__(self, client_id: str, access_token: str,
                 instruments: list[tuple[str, int]], *,
                 on_packet: PacketCb, on_event: EventCb = lambda *_: None,
                 request_code: int = REQ_FULL,
                 ping_interval: float = 15.0, ping_timeout: float = 10.0):
        self.client_id = client_id
        self.access_token = access_token
        self.instruments = instruments        # [(exchange_segment_str, security_id), ...]
        self.on_packet = on_packet
        self.on_event = on_event
        self.request_code = request_code
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self._ws = None
        self._last_disconnect_ns: Optional[int] = None

    @property
    def url(self) -> str:
        return (f"{WSS_URL}?version=2&token={self.access_token}"
                f"&clientId={self.client_id}&authType=2")

    def _subscribe_messages(self) -> list[str]:
        return self._messages_for(self.instruments)

    def _messages_for(self, instruments: list[tuple[str, int]]) -> list[str]:
        # Group by subscription mode: IDX_I -> Quote(17) (indices have no Full
        # feed), every other segment keeps self.request_code (Full/21). A list
        # with no IDX_I instrument yields byte-identical messages to before, so
        # futures/options/equities are unaffected. Relative order is preserved
        # within each mode group; subscription order does not matter to Dhan.
        by_code: dict[int, list[tuple[str, int]]] = {}
        for seg, sid in instruments:
            code = INDEX_REQUEST_CODE if seg == IDX_SEGMENT else self.request_code
            by_code.setdefault(code, []).append((seg, sid))
        msgs = []
        for code, group in by_code.items():
            for i in range(0, len(group), MAX_INSTRUMENTS_PER_MSG):
                chunk = group[i:i + MAX_INSTRUMENTS_PER_MSG]
                msgs.append(json.dumps({
                    "RequestCode": code,
                    "InstrumentCount": len(chunk),
                    "InstrumentList": [
                        {"ExchangeSegment": seg, "SecurityId": str(sid)} for seg, sid in chunk
                    ],
                }))
        return msgs

    async def _subscribe(self, ws) -> None:
        if not self.instruments:
            return  # empty connection; instruments will be added dynamically
        for msg in self._subscribe_messages():
            await ws.send(msg)
        self.on_event("SUBSCRIBE", f"{len(self.instruments)} instruments (code {self.request_code})", None)

    async def add_instruments(self, new: list[tuple[str, int]]) -> None:
        """Dynamically subscribe more instruments on the live connection.

        Also appends them to ``self.instruments`` so a later reconnect resubscribes
        the full set. Safe to call before connect (queued until the socket opens).
        Skips ids already subscribed.
        """
        existing = {(seg, sid) for seg, sid in self.instruments}
        fresh = [x for x in new if x not in existing]
        if not fresh:
            return
        self.instruments.extend(fresh)
        if self._ws is not None:
            for msg in self._messages_for(fresh):
                await self._ws.send(msg)
            self.on_event("SUBSCRIBE", f"+{len(fresh)} instruments (dynamic)", float(len(fresh)))

    async def run(self, stop_event: asyncio.Event) -> None:
        """Connect/receive loop with reconnection until ``stop_event`` is set."""
        attempt = 0
        while not stop_event.is_set():
            try:
                async with websockets.connect(
                    self.url, ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout, max_size=None, close_timeout=5,
                ) as ws:
                    self._ws = ws
                    if self._last_disconnect_ns is not None:
                        downtime = (time.time_ns() - self._last_disconnect_ns) / 1e9
                        self.on_event("RECONNECT", "resubscribed after drop", downtime)
                        self._last_disconnect_ns = None
                    await self._subscribe(ws)
                    attempt = 0  # successful connect resets backoff
                    async for message in ws:
                        if isinstance(message, (bytes, bytearray)):
                            ts = time.time_ns()
                            for parsed in parse_frame(bytes(message)):
                                self.on_packet(parsed, ts)
                        else:
                            log.info("text message from feed: %s", str(message)[:200])
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - reconnect on any failure
                log.warning("feed connection error: %s: %s", type(exc).__name__, exc)
            finally:
                self._ws = None

            if stop_event.is_set():
                break
            if self._last_disconnect_ns is None:
                self._last_disconnect_ns = time.time_ns()
            delay = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
            attempt += 1
            self.on_event("DISCONNECT", f"reconnecting in {delay}s (attempt {attempt})", float(delay))
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass


class ConnectionManager:
    """Runs up to N independent FeedClient connections (Dhan allows 5).

    Instruments are assigned to a connection index; each connection has its own
    reconnect loop, so one drop doesn't take down the whole recorder. Supports
    dynamically adding instruments to a specific connection (used to subscribe
    option strikes once ATM is known at open).
    """

    def __init__(self, n: int, client_id: str, access_token: str, *,
                 on_packet: PacketCb, on_event, request_code: int = REQ_FULL,
                 ping_interval: float = 15.0, ping_timeout: float = 10.0):
        n = max(1, min(int(n), 5))
        self.n = n
        self.clients = [
            FeedClient(
                client_id, access_token, [], on_packet=on_packet,
                on_event=(lambda kind, detail, val, i=idx:
                          on_event(kind, f"[conn{i}] {detail}", val)),
                request_code=request_code, ping_interval=ping_interval,
                ping_timeout=ping_timeout,
            )
            for idx in range(n)
        ]

    def assign(self, idx: int, instruments: list[tuple[str, int]]) -> None:
        """Statically assign instruments to a connection before run()."""
        self.clients[idx % self.n].instruments.extend(instruments)

    async def add(self, idx: int, instruments: list[tuple[str, int]]) -> None:
        await self.clients[idx % self.n].add_instruments(instruments)

    async def run(self, stop_event: asyncio.Event) -> None:
        await asyncio.gather(*(c.run(stop_event) for c in self.clients))

    async def close(self) -> None:
        await asyncio.gather(*(c.close() for c in self.clients), return_exceptions=True)
