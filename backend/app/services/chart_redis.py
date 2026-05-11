"""Chart-module Redis pub/sub helpers — channel naming + publish/subscribe.

The chart module fans real-time ticks + aggregated candles + control
events out to many websocket subscribers via Redis pub/sub. Keeping the
channel naming + JSON encoding here ensures every producer/consumer
uses the same shape.

**Why this lives in its own module:** the chart module ships on a
feature branch (`feat/charting-module`) developed in parallel with the
strategy_engine work. Adding pub/sub helpers directly to
`app.core.redis_client` would touch a file the other parallel session
also depends on. This module re-exports a thin chart-specific surface
that imports the existing Redis connection pool from
:mod:`app.core.redis_client` without modifying it.

Channels:

    chart:ticks:{symbol}                — raw TickData JSON
    chart:candles:{symbol}:{timeframe}  — aggregated Candle JSON
    chart:control:{symbol}              — control plane (BROKER_DISCONNECTED, …)

Yahan teen layers ek hi naming convention follow karte hain — adapter
publish karega, REST/WS API subscribe karega, frontend ko same shape
milega.

Tests inject a fake Redis (``fakeredis.aioredis.FakeRedis``) by either:
    * Passing ``redis_client=<fake>`` to the public helpers, OR
    * Monkeypatching ``app.core.redis_client.get_redis`` (per project
      convention — see ``tests/test_dhan_broker.py``).

READ-SIDE CONTRACT
------------------
Consumers MUST deserialise pub/sub payloads using
``Model.model_validate_json(bytes_data)`` — **not**
``json.loads(bytes_data)`` followed by ``Model.model_validate(dict)``.

Why this matters in Pydantic v2 *strict* mode (which every chart-module
schema enables): strict ``model_validate`` rejects ``"42.5"`` as a
``Decimal`` because a string is not the strict-mode type for ``Decimal``;
``model_validate_json`` is aware that JSON has no native Decimal type
and accepts the string form losslessly. Same trap applies to
``datetime`` (strict ``model_validate`` rejects ISO-8601 strings,
``model_validate_json`` accepts them).

The bug surfaces at runtime, not at import time, and only on payloads
that exercise the Decimal/datetime fields — so it is the kind of
mistake a 70%-coverage test suite will miss. Codify
``model_validate_json`` everywhere on the read side and this entire
class of bug evaporates.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.core.redis_client import get_redis

if TYPE_CHECKING:
    import redis.asyncio as aioredis


_logger = get_logger("services.chart_redis")


# ═══════════════════════════════════════════════════════════════════════
# Channel naming — single source of truth
# ═══════════════════════════════════════════════════════════════════════


#: Top-level namespace. Distinct from ``cache:`` / ``rate:`` / ``kill:``
#: in :mod:`app.core.redis_client` so an ops ``SCAN chart:*`` cleanly
#: enumerates every chart key without colliding with order-flow state.
_NS_CHART = "chart"

#: Sub-channels inside the chart namespace. Kept as constants so a typo
#: in one producer can't drift from its subscriber's name.
_SUB_TICKS = "ticks"
_SUB_CANDLES = "candles"
_SUB_CONTROL = "control"


#: Allowed character classes inside a symbol after normalisation. Covers
#: the real-world shapes the chart module has to route on:
#:     * ``NIFTY``, ``RELIANCE``       — plain equity symbols
#:     * ``NSE:NIFTY``, ``MCX:CRUDEOIL`` — exchange-prefixed
#:     * ``NIFTY-FUT``, ``BANKNIFTY-25JAN-FUT`` — derivative contracts
#:     * ``BAJAJ-AUTO``, ``M&M``        — punctuation in cash symbols
#:     * ``BANK_NIFTY``                — underscored aliases
#: Whitespace is explicitly rejected so a stray newline / tab never
#: leaks into a channel name.
_SYMBOL_ALLOWED = re.compile(r"^[A-Z0-9:&_\-]+$")


def _normalize_symbol(symbol: str) -> str:
    """Symbols are stored upper-case across the project (Dhan, Fyers, schema).

    Accepts uppercase alphanumerics plus ``:``, ``-``, ``&``, ``_`` —
    enough to cover exchange prefixes (``NSE:NIFTY``), derivative
    contracts (``NIFTY-FUT``), and punctuated cash symbols (``M&M``,
    ``BAJAJ-AUTO``). Whitespace inside the input is rejected outright
    so an accidental newline or tab can never end up inside a channel
    name (which Redis would happily accept, then fail to ``UNSUBSCRIBE``
    cleanly on shutdown).

    The helper raises rather than silently coercing the empty string so
    a caller that forgot to pass a symbol fails fast at the producer,
    not later in a subscriber.
    """
    if symbol is None:
        raise ValueError("symbol must be a non-empty string.")
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("symbol must be a non-empty string.")
    if not _SYMBOL_ALLOWED.match(cleaned):
        raise ValueError(
            f"symbol {symbol!r} contains characters outside [A-Z0-9:&_-] "
            "(whitespace and other punctuation are not allowed)."
        )
    return cleaned


def _normalize_timeframe(timeframe: str) -> str:
    """Timeframes are short lower-case tokens (``1m``, ``5m``, ``1d``)
    matching the :class:`Timeframe` enum values in :mod:`app.schemas.candle`.

    We treat the input as opaque here — this module deliberately does
    not import the enum to keep the dependency arrow one-way (schema →
    services, never the reverse) and to avoid pulling Pydantic into
    every pub/sub caller.
    """
    cleaned = timeframe.strip().lower()
    if not cleaned:
        raise ValueError("timeframe must be a non-empty string.")
    return cleaned


def chart_ticks_channel(symbol: str) -> str:
    """Canonical channel name for raw ticks of ``symbol``.

    Example: ``chart_ticks_channel("reliance")`` → ``"chart:ticks:RELIANCE"``.
    """
    return f"{_NS_CHART}:{_SUB_TICKS}:{_normalize_symbol(symbol)}"


def chart_candles_channel(symbol: str, timeframe: str) -> str:
    """Canonical channel name for aggregated candles.

    Example: ``chart_candles_channel("nifty", "5m")`` →
    ``"chart:candles:NIFTY:5m"``.
    """
    return (
        f"{_NS_CHART}:{_SUB_CANDLES}:"
        f"{_normalize_symbol(symbol)}:{_normalize_timeframe(timeframe)}"
    )


def chart_control_channel(symbol: str) -> str:
    """Canonical channel name for control events (disconnect, reconnect, …).

    Control events are scoped per-symbol so the live WS handler can
    subscribe to ``chart:control:NIFTY`` alongside its data channels
    without seeing disconnect events for unrelated symbols.
    """
    return f"{_NS_CHART}:{_SUB_CONTROL}:{_normalize_symbol(symbol)}"


# ═══════════════════════════════════════════════════════════════════════
# Publish
# ═══════════════════════════════════════════════════════════════════════


async def publish_json(
    channel: str,
    payload: Any,
    *,
    redis_client: aioredis.Redis | None = None,
) -> int:
    """Publish ``payload`` (JSON-encoded with ``default=str``) on ``channel``.

    The ``default=str`` fallback covers :class:`~decimal.Decimal` and
    :class:`~datetime.datetime` cleanly — both serialise to their string
    form, matching what the rest of the chart module's JSON
    deserialisers expect (Pydantic v2 parses ``Decimal`` from strings
    losslessly and ISO datetimes from strings reliably).

    Args:
        channel: Fully-qualified Redis channel name. Produced by the
            ``chart_*_channel`` helpers above — never hand-built.
        payload: Any JSON-serialisable value. Pydantic models should be
            passed as ``model.model_dump(mode="json")`` so they survive
            the round-trip back through a strict subscriber.
        redis_client: Optional injection point for tests. Defaults to
            the process-wide async client.

    Returns:
        The integer reply from Redis' ``PUBLISH`` command — the number
        of subscribers that received the message. Useful for monitoring
        and back-pressure decisions; callers may ignore it.

    Raises:
        TypeError: If ``payload`` is not JSON-serialisable even after
            the ``default=str`` fallback.
    """
    client = redis_client or get_redis()
    body = json.dumps(payload, default=str)
    delivered = await client.publish(channel, body)
    return int(delivered)


# ═══════════════════════════════════════════════════════════════════════
# Subscribe
# ═══════════════════════════════════════════════════════════════════════


async def subscribe(
    *channels: str,
    redis_client: aioredis.Redis | None = None,
) -> aioredis.client.PubSub:
    """Open a pub/sub connection subscribed to one or more channels.

    Returns the underlying :class:`redis.asyncio.client.PubSub` handle —
    callers consume via ``await pubsub.get_message(...)`` or the
    ``listen()`` async iterator and **must** ``await pubsub.aclose()``
    on teardown. We expose the raw handle (rather than wrapping it in
    our own iterator) so cancellation semantics stay aligned with what
    redis-py's own pub/sub state machine guarantees — wrapping it tends
    to leak the underlying connection back to the pool in an unclean
    state.

    Args:
        *channels: One or more fully-qualified channel names. At least
            one is required; subscribing to zero channels is silently
            useless and almost always a bug, so we raise ``ValueError``.
        redis_client: Optional injection point for tests.

    Returns:
        A subscribed :class:`PubSub` instance ready for reads.

    Raises:
        ValueError: If no channels were passed.

    Example:
        ::

            pubsub = await subscribe(
                chart_ticks_channel("NIFTY"),
                chart_control_channel("NIFTY"),
            )
            try:
                async for msg in pubsub.listen():
                    if msg["type"] != "message":
                        continue
                    handle(msg["data"])
            finally:
                await pubsub.aclose()
    """
    if not channels:
        raise ValueError("subscribe requires at least one channel.")

    client = redis_client or get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(*channels)
    _logger.info(
        "chart_redis.subscribed",
        channels=list(channels),
        count=len(channels),
    )
    return pubsub


# ═══════════════════════════════════════════════════════════════════════
# Convenience: subscribe + iterate
# ═══════════════════════════════════════════════════════════════════════


#: Redis pub/sub frame types we silently drop from :func:`get_next_message`.
#: This is intentionally a **deny-list**, not an allow-list, because we
#: want future frame types (notably ``pmessage`` for pattern subscribes —
#: e.g. ``PSUBSCRIBE chart:ticks:*`` for a wildcard symbol monitor) to
#: pass through to callers without needing a code change here. Only
#: confirm/control frames Redis emits as part of the pub/sub state
#: machine itself are dropped:
#:
#:     subscribe   — confirmation of ``SUBSCRIBE <channel>``
#:     unsubscribe — confirmation of ``UNSUBSCRIBE <channel>``
#:     psubscribe  — confirmation of ``PSUBSCRIBE <pattern>``
#:     punsubscribe — confirmation of ``PUNSUBSCRIBE <pattern>``
#:     pong        — reply to ``PING`` (kept-alive connections)
_PUBSUB_NOISE_TYPES = frozenset(
    {"subscribe", "unsubscribe", "psubscribe", "punsubscribe", "pong"}
)


async def get_next_message(
    pubsub: aioredis.client.PubSub,
    *,
    timeout: float | None = 1.0,
) -> dict[str, Any] | None:
    """Read one message off ``pubsub`` with a bounded wait.

    Thin wrapper around ``pubsub.get_message`` that:
        * Drops the Redis pub/sub *control* frames (``subscribe`` /
          ``unsubscribe`` / ``psubscribe`` / ``punsubscribe`` / ``pong``)
          which consumers almost always want to skip.
        * **Lets ``pmessage`` (pattern-subscribe data) through unchanged**
          so future wildcard subscribers (e.g. ``PSUBSCRIBE chart:ticks:*``
          for an ops dashboard) work without modification.
        * Returns ``None`` on timeout instead of letting the underlying
          ``None`` leak silently — explicit return makes calling code
          easier to type-check.

    The chart WS handler uses this in a loop so it can also service
    websocket pings + heartbeat sends without blocking forever on a
    quiet symbol.
    """
    while True:
        # We pass ``ignore_subscribe_messages=False`` so we see every
        # frame and apply our own filter — this keeps the
        # control-vs-data semantics owned by ONE function (this one),
        # not split across redis-py's flag plus our own check.
        msg = await pubsub.get_message(
            ignore_subscribe_messages=False, timeout=timeout
        )
        if msg is None:
            return None
        if msg.get("type") in _PUBSUB_NOISE_TYPES:
            continue
        # Everything else (``message`` from SUBSCRIBE, ``pmessage`` from
        # PSUBSCRIBE, future frame types) flows through to the caller.
        return msg


__all__ = [
    "chart_candles_channel",
    "chart_control_channel",
    "chart_ticks_channel",
    "get_next_message",
    "publish_json",
    "subscribe",
]
