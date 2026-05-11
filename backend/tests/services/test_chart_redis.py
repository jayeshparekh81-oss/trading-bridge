"""Tests for :mod:`app.services.chart_redis`.

Uses :class:`fakeredis.aioredis.FakeRedis` (autouse via
``services/conftest.py``) so pub/sub round-trips run in-process
without a live Redis server.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import fakeredis.aioredis as fake_aioredis
import pytest

from app.services import chart_redis
from app.services.chart_redis import (
    _PUBSUB_NOISE_TYPES,
    chart_candles_channel,
    chart_control_channel,
    chart_ticks_channel,
    get_next_message,
    publish_json,
    subscribe,
)


# ═══════════════════════════════════════════════════════════════════════
# Channel naming
# ═══════════════════════════════════════════════════════════════════════


class TestChannelNames:
    @pytest.mark.parametrize(
        ("symbol", "expected"),
        [
            ("NIFTY", "chart:ticks:NIFTY"),
            ("nifty", "chart:ticks:NIFTY"),
            ("  reliance  ", "chart:ticks:RELIANCE"),
            ("RELIANCE\n", "chart:ticks:RELIANCE"),  # strip() removes edge whitespace
            ("NSE:NIFTY", "chart:ticks:NSE:NIFTY"),
            ("NIFTY-FUT", "chart:ticks:NIFTY-FUT"),
            ("M&M", "chart:ticks:M&M"),
            ("BANK_NIFTY", "chart:ticks:BANK_NIFTY"),
            ("BAJAJ-AUTO", "chart:ticks:BAJAJ-AUTO"),
        ],
    )
    def test_ticks_channel_accepts_real_symbols(
        self, symbol: str, expected: str
    ) -> None:
        assert chart_ticks_channel(symbol) == expected

    def test_candles_channel_format(self) -> None:
        assert (
            chart_candles_channel("NIFTY", "5m") == "chart:candles:NIFTY:5m"
        )

    def test_candles_channel_lower_cases_timeframe(self) -> None:
        # Timeframe enum values are lower-case; the helper should
        # normalise either way.
        assert (
            chart_candles_channel("NIFTY", "5M") == "chart:candles:NIFTY:5m"
        )

    def test_control_channel_format(self) -> None:
        assert chart_control_channel("NIFTY") == "chart:control:NIFTY"

    @pytest.mark.parametrize(
        "bad_symbol",
        [
            "",  # empty
            "   ",  # whitespace only (strips to empty → rejected)
            "NIFTY 50",  # internal whitespace
            "NIFTY\t50",  # internal tab
            "NIFTY.NS",  # dot not allowed
            "NIFTY@FUT",  # @ not allowed
            "NIFTY/FUT",  # slash not allowed
        ],
    )
    def test_invalid_symbol_rejected(self, bad_symbol: str) -> None:
        with pytest.raises(ValueError):
            chart_ticks_channel(bad_symbol)

    def test_none_symbol_rejected(self) -> None:
        with pytest.raises(ValueError):
            chart_ticks_channel(None)  # type: ignore[arg-type]

    def test_invalid_timeframe_rejected(self) -> None:
        with pytest.raises(ValueError):
            chart_candles_channel("NIFTY", "")
        with pytest.raises(ValueError):
            chart_candles_channel("NIFTY", "   ")


# ═══════════════════════════════════════════════════════════════════════
# publish_json
# ═══════════════════════════════════════════════════════════════════════


class TestPublishJson:
    @pytest.mark.asyncio
    async def test_publish_returns_subscriber_count(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        # With no subscribers, PUBLISH returns 0.
        n = await publish_json("chart:ticks:NIFTY", {"x": 1})
        assert n == 0

    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscriber(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        channel = chart_ticks_channel("NIFTY")
        pubsub = await subscribe(channel)
        try:
            n = await publish_json(channel, {"ltp": "100.5"})
            assert n == 1
            msg = await get_next_message(pubsub, timeout=1.0)
            assert msg is not None
            assert json.loads(msg["data"]) == {"ltp": "100.5"}
        finally:
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_publish_encodes_decimal_via_default_str(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        from decimal import Decimal

        channel = chart_ticks_channel("NIFTY")
        pubsub = await subscribe(channel)
        try:
            await publish_json(channel, {"ltp": Decimal("100.5")})
            msg = await get_next_message(pubsub, timeout=1.0)
            assert msg is not None
            payload = json.loads(msg["data"])
            # Decimal serialises as a JSON string via default=str.
            assert payload["ltp"] == "100.5"
        finally:
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_publish_with_explicit_client(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        # When a client is passed, the helper does not call get_redis().
        n = await publish_json(
            "chart:ticks:X", {"a": 1}, redis_client=fake_redis
        )
        assert n == 0


# ═══════════════════════════════════════════════════════════════════════
# subscribe
# ═══════════════════════════════════════════════════════════════════════


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_no_channels_raises(self) -> None:
        with pytest.raises(ValueError):
            await subscribe()

    @pytest.mark.asyncio
    async def test_subscribe_to_multiple_channels(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        pubsub = await subscribe(
            chart_candles_channel("NIFTY", "5m"),
            chart_control_channel("NIFTY"),
        )
        try:
            # Publish on each — both should be received.
            await publish_json(
                chart_candles_channel("NIFTY", "5m"), {"event": "candle"}
            )
            await publish_json(
                chart_control_channel("NIFTY"), {"event": "broker_disconnected"}
            )
            seen: list[dict[str, Any]] = []
            for _ in range(2):
                msg = await get_next_message(pubsub, timeout=1.0)
                if msg is not None:
                    seen.append(json.loads(msg["data"]))
            assert {"event": "candle"} in seen
            assert {"event": "broker_disconnected"} in seen
        finally:
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_subscribe_uses_explicit_client(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        pubsub = await subscribe(
            "chart:ticks:X", redis_client=fake_redis
        )
        try:
            assert pubsub is not None
        finally:
            await pubsub.aclose()


# ═══════════════════════════════════════════════════════════════════════
# get_next_message — filter semantics
# ═══════════════════════════════════════════════════════════════════════


class TestGetNextMessage:
    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        pubsub = await subscribe("chart:ticks:QUIET")
        try:
            msg = await get_next_message(pubsub, timeout=0.05)
            assert msg is None
        finally:
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_skips_subscribe_confirm_frame(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        # Right after subscribe, Redis emits a {'type': 'subscribe', ...}
        # confirmation frame. get_next_message must skip it transparently.
        channel = chart_ticks_channel("NIFTY")
        pubsub = await subscribe(channel)
        try:
            await publish_json(channel, {"x": 1})
            msg = await get_next_message(pubsub, timeout=1.0)
            assert msg is not None
            assert msg["type"] == "message"
        finally:
            await pubsub.aclose()

    def test_noise_types_constant_covers_required_set(self) -> None:
        # ENHANCEMENT 2 contract: subscribe / unsubscribe / pong are
        # all filtered. pmessage is NOT in the set (must pass through).
        assert "subscribe" in _PUBSUB_NOISE_TYPES
        assert "unsubscribe" in _PUBSUB_NOISE_TYPES
        assert "psubscribe" in _PUBSUB_NOISE_TYPES
        assert "punsubscribe" in _PUBSUB_NOISE_TYPES
        assert "pong" in _PUBSUB_NOISE_TYPES
        assert "pmessage" not in _PUBSUB_NOISE_TYPES
        assert "message" not in _PUBSUB_NOISE_TYPES

    @pytest.mark.asyncio
    async def test_pmessage_passthrough(
        self,
        fake_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """pmessage (pattern-subscribe data) MUST flow through.

        We construct a fake pubsub-like object that returns a pmessage
        frame on first call, then None — verifies the filter does not
        accidentally drop pattern-subscribe data on its way to wildcard
        ops dashboards.
        """

        class _FakePubSub:
            def __init__(self) -> None:
                self._frames = [
                    {"type": "subscribe", "channel": "ignored", "data": 1},
                    {
                        "type": "pmessage",
                        "pattern": "chart:ticks:*",
                        "channel": "chart:ticks:NIFTY",
                        "data": json.dumps({"x": 1}),
                    },
                    None,
                ]

            async def get_message(
                self, *, ignore_subscribe_messages: bool, timeout: float | None
            ) -> dict[str, Any] | None:
                return self._frames.pop(0) if self._frames else None

        fake = _FakePubSub()
        msg = await get_next_message(fake, timeout=0.1)  # type: ignore[arg-type]
        assert msg is not None
        assert msg["type"] == "pmessage"
        assert msg["channel"] == "chart:ticks:NIFTY"

    @pytest.mark.asyncio
    async def test_pong_filtered(self) -> None:
        """``pong`` frames (from idle PING keepalives) are dropped."""

        class _FakePubSub:
            def __init__(self) -> None:
                self._frames = [
                    {"type": "pong", "data": "PONG"},
                    {
                        "type": "message",
                        "channel": "chart:ticks:NIFTY",
                        "data": json.dumps({"x": 1}),
                    },
                ]

            async def get_message(
                self, *, ignore_subscribe_messages: bool, timeout: float | None
            ) -> dict[str, Any] | None:
                return self._frames.pop(0) if self._frames else None

        msg = await get_next_message(_FakePubSub(), timeout=0.1)  # type: ignore[arg-type]
        assert msg is not None
        assert msg["type"] == "message"
        assert msg["channel"] == "chart:ticks:NIFTY"


# ═══════════════════════════════════════════════════════════════════════
# Module-level safety
# ═══════════════════════════════════════════════════════════════════════


def test_public_api_surface() -> None:
    """Ensure the public surface listed in __all__ is callable.

    Catches the regression where someone deletes a symbol from the
    module but leaves it in __all__ (or vice-versa).
    """
    for name in chart_redis.__all__:
        assert hasattr(chart_redis, name), f"__all__ lists {name!r} but module lacks it."


def test_namespace_is_chart() -> None:
    """Smoke-check: the namespace prefix is ``chart:`` everywhere."""
    assert chart_ticks_channel("X").startswith("chart:")
    assert chart_candles_channel("X", "1m").startswith("chart:")
    assert chart_control_channel("X").startswith("chart:")


@pytest.mark.asyncio
async def test_publish_subscribe_e2e_with_concurrency(
    fake_redis: fake_aioredis.FakeRedis,
) -> None:
    """Two concurrent publishers fan out to one subscriber correctly."""
    channel = chart_ticks_channel("NIFTY")
    pubsub = await subscribe(channel)
    try:

        async def _pub(n: int) -> None:
            for i in range(n):
                await publish_json(channel, {"i": i})

        await asyncio.gather(_pub(3), _pub(3))

        received = 0
        for _ in range(10):
            msg = await get_next_message(pubsub, timeout=0.2)
            if msg is None:
                break
            received += 1
        assert received == 6
    finally:
        await pubsub.aclose()
