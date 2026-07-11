"""Dhan v2 20-level Market Depth WebSocket client (Module R1).

A SEPARATE feed from R0's Live Market Feed:
  * endpoint  wss://depth-api-feed.dhan.co/twentydepth  (different host)
  * subscribe RequestCode 23, JSON, up to 50 instruments per connection
  * responses are binary bid/ask packets (see recorder.depth_parser)
  * server pings every ~10s; a 40s idle triggers a server-side close, so we let
    the websockets library answer pings and reconnect on any drop

Reuses R0's reconnect/backoff shape. Holds a read-only Data-API token and NEVER
places orders.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable, Optional

import websockets

from recorder.depth_parser import parse_depth_frame

log = logging.getLogger("recorder.depth_feed")

WSS_URL = "wss://depth-api-feed.dhan.co/twentydepth"
REQ_20DEPTH = 23
REQ_DISCONNECT = 12
MAX_INSTRUMENTS_PER_MSG = 50          # Dhan hard cap for 20-depth
BACKOFF_SCHEDULE = [1, 2, 5, 10, 30]

PacketCb = Callable[[dict, int], None]                 # (parsed_depth, ts_recv_ns)
EventCb = Callable[[str, str, Optional[float]], None]  # (kind, detail, value_num)


class DepthFeedClient:
    def __init__(self, client_id: str, access_token: str,
                 instruments: list[tuple[str, int]], *,
                 on_packet: PacketCb, on_event: EventCb = lambda *_: None,
                 ping_interval: float = 15.0, ping_timeout: float = 10.0):
        self.client_id = client_id
        self.access_token = access_token
        self.instruments = instruments        # [(exchange_segment_str, security_id), ...]
        self.on_packet = on_packet
        self.on_event = on_event
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self._ws = None
        self._last_disconnect_ns: Optional[int] = None

    @property
    def url(self) -> str:
        return (f"{WSS_URL}?token={self.access_token}"
                f"&clientId={self.client_id}&authType=2")

    def _messages_for(self, instruments: list[tuple[str, int]]) -> list[str]:
        msgs = []
        for i in range(0, len(instruments), MAX_INSTRUMENTS_PER_MSG):
            chunk = instruments[i:i + MAX_INSTRUMENTS_PER_MSG]
            msgs.append(json.dumps({
                "RequestCode": REQ_20DEPTH,
                "InstrumentCount": len(chunk),
                "InstrumentList": [
                    {"ExchangeSegment": seg, "SecurityId": str(sid)} for seg, sid in chunk
                ],
            }))
        return msgs

    async def _subscribe(self, ws) -> None:
        if not self.instruments:
            return
        for msg in self._messages_for(self.instruments):
            await ws.send(msg)
        self.on_event("SUBSCRIBE", f"{len(self.instruments)} instruments (20-depth)", None)

    async def run(self, stop_event: asyncio.Event) -> None:
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
                    attempt = 0
                    async for message in ws:
                        if isinstance(message, (bytes, bytearray)):
                            ts = time.time_ns()
                            for parsed in parse_depth_frame(bytes(message)):
                                self.on_packet(parsed, ts)
                        else:
                            log.info("text message from depth feed: %s", str(message)[:200])
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - reconnect on any failure
                log.warning("depth feed error: %s: %s", type(exc).__name__, exc)
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


class DepthConnectionManager:
    """Runs up to N depth connections (50 instruments each; Dhan allows 5 total).

    18 instruments fit in a single connection, so ``n`` defaults to 1. Each
    connection has its own reconnect loop so one drop can't take the recorder down.
    """

    def __init__(self, n: int, client_id: str, access_token: str, *,
                 on_packet: PacketCb, on_event: EventCb,
                 ping_interval: float = 15.0, ping_timeout: float = 10.0):
        n = max(1, min(int(n), 5))
        self.n = n
        self.clients = [
            DepthFeedClient(
                client_id, access_token, [], on_packet=on_packet,
                on_event=(lambda kind, detail, val, i=idx:
                          on_event(kind, f"[depth conn{i}] {detail}", val)),
                ping_interval=ping_interval, ping_timeout=ping_timeout,
            )
            for idx in range(n)
        ]

    def assign(self, idx: int, instruments: list[tuple[str, int]]) -> None:
        self.clients[idx % self.n].instruments.extend(instruments)

    async def run(self, stop_event: asyncio.Event) -> None:
        await asyncio.gather(*(c.run(stop_event) for c in self.clients))

    async def close(self) -> None:
        await asyncio.gather(*(c.close() for c in self.clients), return_exceptions=True)
