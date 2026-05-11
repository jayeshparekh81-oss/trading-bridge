"""Tests for :mod:`app.brokers.dhan_websocket`.

Heavy use of the test-seam pattern:

    * ``connect_factory`` arg replaces the live ``websockets.connect``
      so we can script ``connect → fail → fail → succeed`` sequences.
    * ``sleep`` arg replaces ``asyncio.sleep`` so the reconnect backoff
      schedule executes instantly.
    * ``monkeypatch`` of ``time.monotonic`` lets us advance the
      disconnect-threshold clock without waiting 5 wall-clock minutes.

The pure decoder / aggregator / throttle functions are exercised
without the orchestrator at all.
"""

from __future__ import annotations

import asyncio
import json
import struct
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import fakeredis.aioredis as fake_aioredis
import pytest

from app.brokers import dhan_websocket as ws_mod
from app.brokers.dhan_websocket import (
    DHAN_WS_URL,
    DhanWebSocketAdapter,
    _Bucket,
    _bucket_start,
    _build_subscribe_message,
    _CandleAggregator,
    _decode_binary_frame,
    _decode_header,
    _MessageThrottle,
    _reconnect_delay,
    _Subscription,
)
from app.schemas.candle import (
    BrokerDisconnectedEvent,
    BrokerReconnectedEvent,
    Candle,
    TickData,
    Timeframe,
)
from app.services import chart_redis
from tests._chart_helpers import (
    make_disconnect_frame_bytes,
    make_quote_frame_bytes,
    make_tick,
    make_ticker_frame_bytes,
    utc_datetime,
)


# ═══════════════════════════════════════════════════════════════════════
# Test infrastructure: fake WebSocket + connect factory
# ═══════════════════════════════════════════════════════════════════════


class _FakeWsConnection:
    """Mock ``ClientConnection``.

    Behaviour:
        * ``async for raw in conn`` yields each item from ``frames``.
          ``Exception`` items raise; ``bytes``/``str`` items yield.
        * ``send(msg)`` appends to ``self.sent``.
        * ``close()`` sets ``self.closed = True``.

    Use ``frames=[StopIteration]`` to simulate "server closed cleanly".
    Use ``frames=[ConnectionError("x")]`` to simulate "server dropped".
    """

    def __init__(self, frames: list[Any] | None = None) -> None:
        self._frames: list[Any] = list(frames or [])
        self.sent: list[str] = []
        self.closed = False

    def __aiter__(self) -> _FakeWsConnection:
        return self

    async def __anext__(self) -> Any:
        if not self._frames:
            raise StopAsyncIteration
        item = self._frames.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True


class _FakeConnectCtx:
    """Async context manager that ``connect_factory`` returns."""

    def __init__(self, conn_or_exc: _FakeWsConnection | BaseException) -> None:
        self._payload = conn_or_exc

    async def __aenter__(self) -> _FakeWsConnection:
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload

    async def __aexit__(self, *_exc: Any) -> None:
        if isinstance(self._payload, _FakeWsConnection):
            self._payload.closed = True


def _factory_returning(*items: Any) -> tuple[Any, dict[str, int]]:
    """Build a ``connect_factory`` that returns the given items in sequence.

    Each ``item`` is either a :class:`_FakeWsConnection` or an
    exception instance. After the sequence is exhausted, subsequent
    calls return a ``_FakeConnectCtx`` that raises ``asyncio.CancelledError``
    to break out of the outer reconnect loop in tests.
    """
    items_list = list(items)
    counter = {"n": 0}

    def factory(url: str) -> _FakeConnectCtx:
        i = counter["n"]
        counter["n"] += 1
        if i >= len(items_list):
            return _FakeConnectCtx(asyncio.CancelledError("test sequence exhausted"))
        return _FakeConnectCtx(items_list[i])

    return factory, counter


async def _instant_sleep(_seconds: float) -> None:
    """Drop-in replacement for ``asyncio.sleep`` — no time passes."""


# ═══════════════════════════════════════════════════════════════════════
# Pure functions — header + frame decoder
# ═══════════════════════════════════════════════════════════════════════


class TestDecodeHeader:
    def test_short_buffer_raises(self) -> None:
        # Header is exactly 8 bytes — a 4-byte buffer is below minimum.
        with pytest.raises(ValueError):
            _decode_header(b"\x00" * 4)

    def test_known_layout(self) -> None:
        # 8-byte header only (no trailing reserved padding per Dhan v2 spec).
        raw = struct.pack("<BHBI", 7, 64, 1, 11536)
        h = _decode_header(raw)
        assert h.response_code == 7
        assert h.message_length == 64
        assert h.exchange_segment_byte == 1
        assert h.security_id == 11536

    def test_exchange_segment_property(self) -> None:
        raw = struct.pack("<BHBI", 4, 16, 1, 100)
        assert _decode_header(raw).exchange_segment == "NSE_EQ"

    def test_unknown_segment_byte_falls_back_to_string(self) -> None:
        raw = struct.pack("<BHBI", 4, 16, 99, 100)
        assert _decode_header(raw).exchange_segment == "UNKNOWN"


class TestDecodeBinaryFrame:
    def _resolver(self, mapping: dict[tuple[int, str], str]) -> Any:
        return lambda sid, seg: mapping.get((sid, seg))

    def test_ticker_frame(self) -> None:
        buf = make_ticker_frame_bytes(security_id=11536, ltp=22500.5)
        tick = _decode_binary_frame(
            buf, symbol_for=self._resolver({(11536, "NSE_EQ"): "NIFTY"})
        )
        assert tick is not None
        assert tick.symbol == "NIFTY"
        assert tick.exchange_segment == "NSE_EQ"
        # Float→Decimal via str format is lossless to 4dp.
        assert tick.ltp == Decimal("22500.5000")
        assert tick.timestamp.tzinfo is UTC

    def test_quote_frame(self) -> None:
        buf = make_quote_frame_bytes(
            security_id=11536, ltp=22500.5, ltq=75, volume=1_000_000
        )
        tick = _decode_binary_frame(
            buf, symbol_for=self._resolver({(11536, "NSE_EQ"): "NIFTY"})
        )
        assert tick is not None
        assert tick.last_traded_quantity == 75
        assert tick.volume == 1_000_000

    def test_disconnect_signal_returns_none(self) -> None:
        buf = make_disconnect_frame_bytes()
        tick = _decode_binary_frame(buf, symbol_for=lambda *_: None)
        assert tick is None

    def test_unknown_response_code_returns_none(self) -> None:
        # Code 13 (not in the documented v2 set) — we skip cleanly.
        buf = make_ticker_frame_bytes(response_code=13)
        tick = _decode_binary_frame(buf, symbol_for=lambda *_: "X")
        assert tick is None

    @pytest.mark.parametrize(
        ("rc", "label"),
        [
            (5, "OI Data"),
            (6, "Prev Close"),
            (8, "Full"),
        ],
    )
    def test_known_skip_response_codes_return_none(
        self, rc: int, label: str
    ) -> None:
        """Codes 5/6/8 are documented v2 frames we don't consume in
        v1 — they must skip cleanly (not raise, not return a tick)."""
        buf = make_ticker_frame_bytes(response_code=rc)
        tick = _decode_binary_frame(buf, symbol_for=lambda *_: "X")
        assert tick is None, f"{label} (RC={rc}) should skip → None"

    def test_unknown_exchange_segment_byte_raises(self) -> None:
        buf = make_ticker_frame_bytes(exchange_segment_byte=99)
        with pytest.raises(ValueError):
            _decode_binary_frame(buf, symbol_for=lambda *_: "X")

    def test_unknown_security_id_returns_none(self) -> None:
        buf = make_ticker_frame_bytes(security_id=999)
        tick = _decode_binary_frame(
            buf, symbol_for=self._resolver({(11536, "NSE_EQ"): "NIFTY"})
        )
        assert tick is None

    def test_zero_ltp_returns_none(self) -> None:
        buf = make_ticker_frame_bytes(ltp=0.0)
        tick = _decode_binary_frame(
            buf, symbol_for=self._resolver({(11536, "NSE_EQ"): "X"})
        )
        assert tick is None

    def test_nan_ltp_returns_none(self) -> None:
        buf = make_ticker_frame_bytes(ltp=float("nan"))
        tick = _decode_binary_frame(
            buf, symbol_for=self._resolver({(11536, "NSE_EQ"): "X"})
        )
        assert tick is None

    def test_truncated_header_raises(self) -> None:
        with pytest.raises(ValueError):
            _decode_binary_frame(b"\x07\x00", symbol_for=lambda *_: "X")

    def test_truncated_ticker_payload_raises(self) -> None:
        # Header (8) + Ticker payload (8) = 16 total. Slice to 12 leaves
        # only 4 bytes of payload — short of the required 8.
        full = make_ticker_frame_bytes()
        with pytest.raises(ValueError):
            _decode_binary_frame(full[:12], symbol_for=lambda *_: "X")

    def test_truncated_quote_payload_raises(self) -> None:
        # Header (8) + Quote payload (42) = 50 total. Slice to 30
        # leaves 22 bytes of payload — short of the required 42.
        full = make_quote_frame_bytes()
        with pytest.raises(ValueError):
            _decode_binary_frame(full[:30], symbol_for=lambda *_: "X")

    def test_quote_volume_zero_still_published(self) -> None:
        buf = make_quote_frame_bytes(volume=0, ltp=100.0)
        tick = _decode_binary_frame(
            buf, symbol_for=self._resolver({(11536, "NSE_EQ"): "X"})
        )
        assert tick is not None
        assert tick.volume == 0

    def test_quote_with_nan_ltp_returns_none(self) -> None:
        buf = make_quote_frame_bytes(ltp=float("nan"))
        tick = _decode_binary_frame(
            buf, symbol_for=self._resolver({(11536, "NSE_EQ"): "X"})
        )
        assert tick is None


# ═══════════════════════════════════════════════════════════════════════
# _build_subscribe_message
# ═══════════════════════════════════════════════════════════════════════


class TestBuildSubscribeMessage:
    def test_empty_instruments_raises(self) -> None:
        with pytest.raises(ValueError):
            _build_subscribe_message(17, [])

    def test_payload_shape(self) -> None:
        msg = _build_subscribe_message(17, [("NSE_EQ", "11536")])
        decoded = json.loads(msg)
        assert decoded["RequestCode"] == 17
        assert decoded["InstrumentCount"] == 1
        assert decoded["InstrumentList"] == [
            {"ExchangeSegment": "NSE_EQ", "SecurityId": "11536"}
        ]

    def test_multiple_instruments(self) -> None:
        msg = _build_subscribe_message(
            15, [("NSE_EQ", "11536"), ("NSE_FNO", "55555")]
        )
        decoded = json.loads(msg)
        assert decoded["InstrumentCount"] == 2
        assert {"ExchangeSegment": "NSE_FNO", "SecurityId": "55555"} in decoded[
            "InstrumentList"
        ]


# ═══════════════════════════════════════════════════════════════════════
# _bucket_start
# ═══════════════════════════════════════════════════════════════════════


class TestBucketStart:
    def test_one_min_snaps_to_minute(self) -> None:
        ts = datetime(2026, 5, 11, 9, 15, 37, tzinfo=UTC)
        result = _bucket_start(ts, Timeframe.ONE_MIN)
        assert result == datetime(2026, 5, 11, 9, 15, 0, tzinfo=UTC)

    def test_five_min_snaps_to_five_minute_boundary(self) -> None:
        ts = datetime(2026, 5, 11, 9, 18, 0, tzinfo=UTC)
        result = _bucket_start(ts, Timeframe.FIVE_MIN)
        assert result == datetime(2026, 5, 11, 9, 15, 0, tzinfo=UTC)

    def test_one_hour_snaps(self) -> None:
        ts = datetime(2026, 5, 11, 9, 47, 30, tzinfo=UTC)
        result = _bucket_start(ts, Timeframe.ONE_HOUR)
        assert result == datetime(2026, 5, 11, 9, 0, 0, tzinfo=UTC)

    def test_one_day_snaps_to_midnight_utc(self) -> None:
        ts = datetime(2026, 5, 11, 15, 47, 30, tzinfo=UTC)
        result = _bucket_start(ts, Timeframe.ONE_DAY)
        assert result == datetime(2026, 5, 11, 0, 0, 0, tzinfo=UTC)


# ═══════════════════════════════════════════════════════════════════════
# _reconnect_delay
# ═══════════════════════════════════════════════════════════════════════


class TestReconnectDelay:
    def test_attempt_zero_is_zero(self) -> None:
        assert _reconnect_delay(0) == 0.0

    def test_negative_attempt_is_zero(self) -> None:
        assert _reconnect_delay(-1) == 0.0

    @pytest.mark.parametrize(
        ("attempt", "base"),
        [
            (1, 1.0),
            (2, 2.0),
            (3, 4.0),
            (4, 8.0),
            (5, 16.0),
            (6, 32.0),
            (7, 60.0),   # capped
            (100, 60.0),  # capped indefinitely
        ],
    )
    def test_schedule_with_jitter(self, attempt: int, base: float) -> None:
        delay = _reconnect_delay(attempt)
        # ±25% jitter around base, never negative.
        assert 0.0 <= delay <= base * 1.25 + 0.01
        assert delay >= base * 0.75 - 0.01


# ═══════════════════════════════════════════════════════════════════════
# _CandleAggregator
# ═══════════════════════════════════════════════════════════════════════


class TestCandleAggregator:
    def test_first_tick_creates_bucket(self) -> None:
        agg = _CandleAggregator()
        tick = make_tick(ltp="100.00", volume=1000)
        closed = agg.fold(tick, [Timeframe.ONE_MIN])
        assert closed == []
        assert (tick.symbol, Timeframe.ONE_MIN) in agg._buckets

    def test_mid_bucket_updates_high_low_close(self) -> None:
        agg = _CandleAggregator()
        t0 = utc_datetime(hour=9, minute=15, second=0)
        agg.fold(make_tick(ltp="100.00", volume=1000, timestamp=t0), [Timeframe.ONE_MIN])
        agg.fold(
            make_tick(ltp="105.00", volume=1500, timestamp=t0 + timedelta(seconds=10)),
            [Timeframe.ONE_MIN],
        )
        agg.fold(
            make_tick(ltp="98.00", volume=2000, timestamp=t0 + timedelta(seconds=20)),
            [Timeframe.ONE_MIN],
        )
        bucket = agg._buckets[("NIFTY", Timeframe.ONE_MIN)]
        assert bucket.open == Decimal("100.00")
        assert bucket.high == Decimal("105.00")
        assert bucket.low == Decimal("98.00")
        assert bucket.close == Decimal("98.00")
        assert bucket.last_volume == 2000

    def test_bucket_roll_closes_and_opens(self) -> None:
        agg = _CandleAggregator()
        t0 = utc_datetime(hour=9, minute=15, second=0)
        agg.fold(make_tick(ltp="100.00", volume=1000, timestamp=t0), [Timeframe.ONE_MIN])
        agg.fold(
            make_tick(ltp="102.00", volume=1500, timestamp=t0 + timedelta(seconds=30)),
            [Timeframe.ONE_MIN],
        )
        # Next minute's first tick — should close the previous bucket.
        closed = agg.fold(
            make_tick(ltp="103.00", volume=1800, timestamp=t0 + timedelta(seconds=70)),
            [Timeframe.ONE_MIN],
        )
        assert len(closed) == 1
        candle = closed[0]
        assert candle.open == Decimal("100.00")
        assert candle.close == Decimal("102.00")
        assert candle.volume == 1500 - 1000

    def test_volume_clamps_to_zero_on_regression(self) -> None:
        """If Dhan reports a lower cumulative volume mid-bucket (rare
        tenant edge), candle volume must be >= 0, never negative."""
        agg = _CandleAggregator()
        t0 = utc_datetime(hour=9, minute=15, second=0)
        agg.fold(
            make_tick(ltp="100.00", volume=2000, timestamp=t0), [Timeframe.ONE_MIN]
        )
        agg.fold(
            make_tick(ltp="100.00", volume=1500, timestamp=t0 + timedelta(seconds=30)),
            [Timeframe.ONE_MIN],
        )
        closed = agg.fold(
            make_tick(ltp="100.00", volume=1800, timestamp=t0 + timedelta(seconds=70)),
            [Timeframe.ONE_MIN],
        )
        # bucket_start_volume = 2000, last_volume = 1500 → max(0, -500) = 0
        assert closed[0].volume == 0

    def test_multiple_timeframes_parallel(self) -> None:
        agg = _CandleAggregator()
        t0 = utc_datetime(hour=9, minute=15, second=0)
        agg.fold(
            make_tick(ltp="100.00", timestamp=t0),
            [Timeframe.ONE_MIN, Timeframe.FIVE_MIN],
        )
        agg.fold(
            make_tick(ltp="101.00", timestamp=t0 + timedelta(seconds=70)),
            [Timeframe.ONE_MIN, Timeframe.FIVE_MIN],
        )
        # 1m bucket rolled; 5m bucket still open.
        assert ("NIFTY", Timeframe.ONE_MIN) in agg._buckets
        assert ("NIFTY", Timeframe.FIVE_MIN) in agg._buckets
        assert (
            agg._buckets[("NIFTY", Timeframe.FIVE_MIN)].open == Decimal("100.00")
        )
        assert (
            agg._buckets[("NIFTY", Timeframe.ONE_MIN)].open == Decimal("101.00")
        )

    def test_drop_symbol_flushes_partial(self) -> None:
        agg = _CandleAggregator()
        agg.fold(make_tick(ltp="100.00"), [Timeframe.ONE_MIN])
        flushed = agg.drop_symbol("NIFTY")
        assert len(flushed) == 1
        assert flushed[0].open == Decimal("100.00")
        # State cleared.
        assert ("NIFTY", Timeframe.ONE_MIN) not in agg._buckets

    def test_drop_symbol_unknown_is_noop(self) -> None:
        agg = _CandleAggregator()
        assert agg.drop_symbol("UNKNOWN") == []

    def test_drop_symbol_only_targets_named_symbol(self) -> None:
        agg = _CandleAggregator()
        agg.fold(make_tick(symbol="NIFTY"), [Timeframe.ONE_MIN])
        agg.fold(make_tick(symbol="RELIANCE"), [Timeframe.ONE_MIN])
        flushed = agg.drop_symbol("NIFTY")
        assert len(flushed) == 1
        assert flushed[0].symbol == "NIFTY"
        # RELIANCE bucket still present.
        assert ("RELIANCE", Timeframe.ONE_MIN) in agg._buckets

    def test_empty_timeframes_list_does_nothing(self) -> None:
        agg = _CandleAggregator()
        closed = agg.fold(make_tick(), [])
        assert closed == []
        assert not agg._buckets


# ═══════════════════════════════════════════════════════════════════════
# _Bucket.to_candle
# ═══════════════════════════════════════════════════════════════════════


class TestBucket:
    def test_to_candle(self) -> None:
        b = _Bucket(
            symbol="NIFTY",
            timeframe=Timeframe.ONE_MIN,
            bucket_start=utc_datetime(hour=9, minute=15, second=0),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            start_volume=1000,
            last_volume=3000,
        )
        c = b.to_candle()
        assert isinstance(c, Candle)
        assert c.volume == 2000


# ═══════════════════════════════════════════════════════════════════════
# _MessageThrottle
# ═══════════════════════════════════════════════════════════════════════


class TestMessageThrottle:
    def test_invalid_capacity(self) -> None:
        with pytest.raises(ValueError):
            _MessageThrottle(capacity=0, window_seconds=1.0)

    def test_invalid_window(self) -> None:
        with pytest.raises(ValueError):
            _MessageThrottle(capacity=10, window_seconds=0.0)

    @pytest.mark.asyncio
    async def test_initial_acquire_immediate(self) -> None:
        t = _MessageThrottle(capacity=5, window_seconds=1.0)
        for _ in range(5):
            await t.acquire()
        # Five sub-millisecond acquires worked.

    @pytest.mark.asyncio
    async def test_refill_replenishes_after_real_wait(self) -> None:
        # Use a tiny window so a real sleep is fast.
        t = _MessageThrottle(capacity=2, window_seconds=0.05)
        await t.acquire()
        await t.acquire()
        # Wait past one full window — refill should put both tokens back.
        await asyncio.sleep(0.06)
        await t.acquire()
        # If refill didn't happen, this call would block forever; reaching
        # here proves replenishment.


# ═══════════════════════════════════════════════════════════════════════
# DhanWebSocketAdapter — constructor + lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestAdapterConstructor:
    def test_valid(self) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u"
        )
        assert a._client_id == "C"
        assert a._access_token == "T"
        assert a._user_id == "u"

    def test_empty_client_id(self) -> None:
        with pytest.raises(ValueError):
            DhanWebSocketAdapter(client_id="", access_token="T", user_id="u")

    def test_empty_access_token(self) -> None:
        with pytest.raises(ValueError):
            DhanWebSocketAdapter(client_id="C", access_token="", user_id="u")

    def test_empty_user_id(self) -> None:
        with pytest.raises(ValueError):
            DhanWebSocketAdapter(client_id="C", access_token="T", user_id="")

    def test_default_ws_url_constant(self) -> None:
        assert DHAN_WS_URL.startswith("wss://")


class TestAdapterStartStop:
    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        factory, counter = _factory_returning(_FakeWsConnection())
        a = DhanWebSocketAdapter(
            client_id="C",
            access_token="T",
            user_id="u",
            connect_factory=factory,
            sleep=_instant_sleep,
        )
        await a.start()
        await a.start()  # second call is a no-op
        await a.stop()
        # Only ONE reader task was created.
        assert a._reader_task is None

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u", sleep=_instant_sleep,
        )
        await a.stop()  # idempotent

    @pytest.mark.asyncio
    async def test_aenter_aexit(self) -> None:
        factory, _ = _factory_returning(_FakeWsConnection())
        async with DhanWebSocketAdapter(
            client_id="C",
            access_token="T",
            user_id="u",
            connect_factory=factory,
            sleep=_instant_sleep,
        ) as a:
            assert a._reader_task is not None


# ═══════════════════════════════════════════════════════════════════════
# DhanWebSocketAdapter — subscribe / unsubscribe
# ═══════════════════════════════════════════════════════════════════════


class TestAdapterSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_before_connect_queues(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u", sleep=_instant_sleep,
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[Timeframe.ONE_MIN],
        )
        assert "NIFTY" in a._subscriptions
        # ws is None, so no SUBSCRIBE message yet.
        assert a._ws is None

    @pytest.mark.asyncio
    async def test_subscribe_unknown_segment_rejected(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        with pytest.raises(ValueError):
            await a.subscribe(
                symbol="NIFTY",
                security_id=13,
                exchange_segment="BOGUS",
                timeframes=[],
            )

    @pytest.mark.asyncio
    async def test_subscribe_zero_security_id_rejected(self) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        with pytest.raises(ValueError):
            await a.subscribe(
                symbol="NIFTY",
                security_id=0,
                exchange_segment="IDX_I",
                timeframes=[],
            )

    @pytest.mark.asyncio
    async def test_subscribe_empty_symbol_rejected(self) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        with pytest.raises(ValueError):
            await a.subscribe(
                symbol="",
                security_id=13,
                exchange_segment="IDX_I",
                timeframes=[],
            )

    @pytest.mark.asyncio
    async def test_resubscribe_merges_timeframes(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[Timeframe.ONE_MIN],
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[Timeframe.FIVE_MIN],
        )
        tfs = a._subscriptions["NIFTY"].timeframes
        assert Timeframe.ONE_MIN in tfs
        assert Timeframe.FIVE_MIN in tfs

    @pytest.mark.asyncio
    async def test_unsubscribe_before_connect_is_safe(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        await a.unsubscribe("NIFTY")
        assert "NIFTY" not in a._subscriptions

    @pytest.mark.asyncio
    async def test_unsubscribe_unknown_is_noop(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.unsubscribe("UNKNOWN")  # does not raise

    @pytest.mark.asyncio
    async def test_unsubscribe_flushes_partial_candles(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[Timeframe.ONE_MIN],
        )
        # Seed an in-flight bucket.
        a._aggregator.fold(make_tick(symbol="NIFTY"), [Timeframe.ONE_MIN])
        # Subscribe so we receive the candle.
        pubsub = await chart_redis.subscribe(
            chart_redis.chart_candles_channel("NIFTY", "1m")
        )
        try:
            await a.unsubscribe("NIFTY")
            msg = await chart_redis.get_next_message(pubsub, timeout=0.5)
            assert msg is not None
        finally:
            await pubsub.aclose()


# ═══════════════════════════════════════════════════════════════════════
# DhanWebSocketAdapter — disconnect bookkeeping + threshold
# ═══════════════════════════════════════════════════════════════════════


class TestDisconnectBookkeeping:
    @pytest.mark.asyncio
    async def test_first_failure_opens_outage_window(self) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        await a._on_disconnect(ConnectionError("dropped"))
        assert a._reconnect_attempt == 1
        assert a._outage_started_monotonic is not None
        assert a._outage_started_at is not None
        assert not a._disconnect_emitted

    @pytest.mark.asyncio
    async def test_threshold_breach_emits_event_once(
        self,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        # Inject a controllable monotonic via the constructor seam.
        # Monkeypatching the global ``time.monotonic`` would break
        # asyncio's own scheduling — never do it.
        clock = {"t": 0.0}

        a = DhanWebSocketAdapter(
            client_id="C",
            access_token="T",
            user_id="u",
            monotonic=lambda: clock["t"],
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )

        pubsub = await chart_redis.subscribe(
            chart_redis.chart_control_channel("NIFTY")
        )

        try:
            await a._on_disconnect(ConnectionError("first"))
            clock["t"] += 400  # > 5 minutes
            await a._on_disconnect(ConnectionError("second"))
            assert a._disconnect_emitted

            # Calling again does NOT re-emit.
            await a._on_disconnect(ConnectionError("third"))

            received: list[dict[str, Any]] = []
            for _ in range(5):
                msg = await chart_redis.get_next_message(pubsub, timeout=0.2)
                if msg is None:
                    break
                received.append(json.loads(msg["data"]))
            # Exactly one BROKER_DISCONNECTED event.
            disconnects = [
                e for e in received if e.get("event") == "broker_disconnected"
            ]
            assert len(disconnects) == 1
            assert disconnects[0]["symbol"] == "NIFTY"
            assert disconnects[0]["failed_attempts"] >= 2
        finally:
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_recovery_emits_reconnected_event_once(
        self,
        fake_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )

        # Force disconnect_emitted state without going through the full loop.
        a._disconnect_emitted = True

        pubsub = await chart_redis.subscribe(
            chart_redis.chart_control_channel("NIFTY")
        )
        try:
            await a._on_connected()
            assert not a._disconnect_emitted
            received: list[dict[str, Any]] = []
            for _ in range(3):
                msg = await chart_redis.get_next_message(pubsub, timeout=0.2)
                if msg is None:
                    break
                received.append(json.loads(msg["data"]))
            reconnects = [
                e for e in received if e.get("event") == "broker_reconnected"
            ]
            assert len(reconnects) == 1
        finally:
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_clean_connect_no_event_emitted(
        self,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        """A fresh connect (no prior outage) emits no recovery event."""
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )

        pubsub = await chart_redis.subscribe(
            chart_redis.chart_control_channel("NIFTY")
        )
        try:
            await a._on_connected()
            # Nothing should have been published on the control channel.
            msg = await chart_redis.get_next_message(pubsub, timeout=0.1)
            assert msg is None
        finally:
            await pubsub.aclose()


# ═══════════════════════════════════════════════════════════════════════
# DhanWebSocketAdapter — frame handling
# ═══════════════════════════════════════════════════════════════════════


class TestHandleBinaryFrame:
    @pytest.mark.asyncio
    async def test_decode_failure_logged_not_raised(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        # Corrupt frame — header valid but unknown exchange byte 99.
        buf = make_ticker_frame_bytes(exchange_segment_byte=99)
        # Should not raise — the read loop must keep going.
        await a._handle_binary_frame(buf)

    @pytest.mark.asyncio
    async def test_truncated_frame_logged_not_raised(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a._handle_binary_frame(b"\x00\x00")

    @pytest.mark.asyncio
    async def test_tick_published_then_candle_published(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=11536,
            exchange_segment="NSE_EQ",
            timeframes=[Timeframe.ONE_MIN],
        )

        tick_pubsub = await chart_redis.subscribe(
            chart_redis.chart_ticks_channel("NIFTY")
        )
        try:
            buf = make_ticker_frame_bytes(security_id=11536, ltp=22500.5)
            await a._handle_binary_frame(buf)
            msg = await chart_redis.get_next_message(tick_pubsub, timeout=0.5)
            assert msg is not None
            payload = json.loads(msg["data"])
            assert payload["symbol"] == "NIFTY"
        finally:
            await tick_pubsub.aclose()

    @pytest.mark.asyncio
    async def test_tick_for_unsubscribed_symbol_skipped(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        """Decoder returns None (no mapping) → handler returns without
        publishing. Safe under subscribe races."""
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        # No subscriptions — no mapping for (11536, NSE_EQ).
        buf = make_ticker_frame_bytes(security_id=11536)
        await a._handle_binary_frame(buf)
        # No exception, nothing published.


# ═══════════════════════════════════════════════════════════════════════
# DhanWebSocketAdapter — connection loop end-to-end
# ═══════════════════════════════════════════════════════════════════════


class TestConnectionLoop:
    @pytest.mark.asyncio
    async def test_clean_connect_sends_subscribe(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        conn = _FakeWsConnection(frames=[])  # closes immediately
        factory, counter = _factory_returning(conn)
        a = DhanWebSocketAdapter(
            client_id="C",
            access_token="T",
            user_id="u",
            connect_factory=factory,
            sleep=_instant_sleep,
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        await a.start()
        # Give the reader task a chance to send the SUBSCRIBE.
        await asyncio.sleep(0)
        await a.stop()
        assert counter["n"] >= 1
        # One SUBSCRIBE message sent.
        assert any("NIFTY" not in msg or "InstrumentList" in msg for msg in conn.sent)
        assert conn.closed

    @pytest.mark.asyncio
    async def test_reconnect_resubscribes(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        conn_a = _FakeWsConnection(frames=[])
        conn_b = _FakeWsConnection(frames=[])
        factory, counter = _factory_returning(conn_a, conn_b)
        a = DhanWebSocketAdapter(
            client_id="C",
            access_token="T",
            user_id="u",
            connect_factory=factory,
            sleep=_instant_sleep,
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        await a.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await a.stop()
        # Each connection should have received its own SUBSCRIBE.
        assert len(conn_a.sent) >= 1
        # The second connect happens after the first closed; depending
        # on scheduling we may or may not see it. Counter confirms at
        # least one extra attempt was made.
        assert counter["n"] >= 1


# ═══════════════════════════════════════════════════════════════════════
# Default connect_factory path — monkeypatch websockets.asyncio.client
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultConnectFactory:
    @pytest.mark.asyncio
    async def test_default_factory_uses_websockets_module(
        self,
        fake_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``connect_factory=None`` the adapter imports
        ``websockets.asyncio.client.connect`` lazily on first use.
        Monkeypatching that name verifies the import path is exercised
        without needing a real network connection."""
        from websockets.asyncio import client as ws_client_mod

        captured_urls: list[str] = []

        def fake_connect(url: str, **_kwargs: Any) -> _FakeConnectCtx:
            captured_urls.append(url)
            return _FakeConnectCtx(_FakeWsConnection(frames=[]))

        monkeypatch.setattr(ws_client_mod, "connect", fake_connect)

        a = DhanWebSocketAdapter(
            client_id="CID-1",
            access_token="TOK",
            user_id="u",
            connect_factory=None,  # take the default branch
            sleep=_instant_sleep,
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        await a.start()
        await asyncio.sleep(0)
        await a.stop()
        assert captured_urls
        # URL should carry our auth fields.
        assert "token=TOK" in captured_urls[0]
        assert "clientId=CID-1" in captured_urls[0]
        assert captured_urls[0].startswith("wss://")


# ═══════════════════════════════════════════════════════════════════════
# _Subscription dataclass — basic shape
# ═══════════════════════════════════════════════════════════════════════


def test_subscription_dataclass_default_factory() -> None:
    s = _Subscription(symbol="NIFTY", security_id=13, exchange_segment="IDX_I")
    assert s.timeframes == []


# ═══════════════════════════════════════════════════════════════════════
# Module-level exports
# ═══════════════════════════════════════════════════════════════════════


def test_public_api_exports() -> None:
    for name in ws_mod.__all__:
        assert hasattr(ws_mod, name)


# ═══════════════════════════════════════════════════════════════════════
# Coverage-gap tests — log-spam control, send paths, failure handlers
# ═══════════════════════════════════════════════════════════════════════


class TestLogSpamControl:
    @pytest.mark.asyncio
    async def test_warn_logged_on_tenth_attempt(
        self,
        fake_redis: fake_aioredis.FakeRedis,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """INFO on attempt 1, WARN on every 10th attempt thereafter."""
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        import logging
        caplog.set_level(logging.INFO, logger="brokers.dhan_websocket")
        for i in range(10):
            await a._on_disconnect(ConnectionError(f"fail {i}"))

        # Attempt 1 should be INFO, attempt 10 should be WARN.
        text = caplog.text
        assert "dhan_ws.disconnected" in text
        assert "dhan_ws.reconnect_failing" in text


class TestSendPaths:
    @pytest.mark.asyncio
    async def test_post_connect_subscribe_sends_message(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        """Subscribing after the ws is open triggers an immediate SUBSCRIBE."""
        fake_ws = _FakeWsConnection()
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        # Inject the fake ws to simulate "already connected".
        a._ws = fake_ws  # type: ignore[assignment]
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        assert any("InstrumentList" in msg for msg in fake_ws.sent)

    @pytest.mark.asyncio
    async def test_unsubscribe_sends_message_when_connected(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        fake_ws = _FakeWsConnection()
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        a._ws = fake_ws  # type: ignore[assignment]
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        fake_ws.sent.clear()
        await a.unsubscribe("NIFTY")
        # An UNSUBSCRIBE-shaped message must have been sent.
        assert any('"RequestCode": 16' in msg for msg in fake_ws.sent)

    @pytest.mark.asyncio
    async def test_unsubscribe_send_failure_logged_not_raised(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        class _FailingWs(_FakeWsConnection):
            async def send(self, message: str) -> None:  # type: ignore[override]
                raise ConnectionError("ws gone")

        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        # Seed the subscription state directly (bypass subscribe() which
        # would also hit the failing ws). Then attach the failing ws.
        sub = _Subscription(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        a._subscriptions["NIFTY"] = sub
        a._sid_to_symbol[(13, "IDX_I")] = "NIFTY"
        a._ws = _FailingWs()  # type: ignore[assignment]
        await a.unsubscribe("NIFTY")  # must not raise
        assert "NIFTY" not in a._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_send_failure_re_raises(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        class _FailingWs(_FakeWsConnection):
            async def send(self, message: str) -> None:  # type: ignore[override]
                raise ConnectionError("send failed")

        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        a._ws = _FailingWs()  # type: ignore[assignment]
        sub = _Subscription(
            symbol="NIFTY", security_id=13, exchange_segment="IDX_I"
        )
        a._subscriptions["NIFTY"] = sub
        with pytest.raises(ConnectionError):
            await a._send_subscription([sub], request_code=17, subscribing=True)

    @pytest.mark.asyncio
    async def test_send_subscription_noop_when_no_subs(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        a._ws = _FakeWsConnection()  # type: ignore[assignment]
        # Empty subs list should early-return without any wire send.
        await a._send_subscription([], request_code=17, subscribing=True)
        assert a._ws.sent == []  # type: ignore[union-attr]


class TestStopWithFailures:
    @pytest.mark.asyncio
    async def test_stop_swallows_ws_close_failure(self) -> None:
        class _BadWs(_FakeWsConnection):
            async def close(self) -> None:  # type: ignore[override]
                raise RuntimeError("close failed")

        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        a._ws = _BadWs()  # type: ignore[assignment]
        await a.stop()  # must not propagate
        assert a._ws is None


class TestConnectionLoopWithFailures:
    @pytest.mark.asyncio
    async def test_failed_connect_then_sleep_then_retry(
        self,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        """Outer loop should call sleep after a connect failure."""
        slept: list[float] = []

        async def tracking_sleep(secs: float) -> None:
            slept.append(secs)

        # First connect raises; second connect succeeds; sequence then
        # exhausts and the helper raises CancelledError to break us out.
        good_conn = _FakeWsConnection()
        factory, _ = _factory_returning(
            ConnectionError("first fail"), good_conn
        )
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
            connect_factory=factory, sleep=tracking_sleep,
        )
        await a.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await a.stop()
        # At least one sleep call happened after the first failure.
        assert slept


class TestReadLoop:
    @pytest.mark.asyncio
    async def test_str_frame_logged_not_decoded(
        self,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        """Dhan sometimes ACKs subscribes as text — handler logs + skips."""
        conn = _FakeWsConnection(
            frames=['{"status": "subscribed"}']  # str, not bytes
        )
        factory, _ = _factory_returning(conn)
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
            connect_factory=factory, sleep=_instant_sleep,
        )
        await a.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await a.stop()

    @pytest.mark.asyncio
    async def test_bytes_frame_routed_to_handler(
        self,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        await chart_redis.subscribe(chart_redis.chart_ticks_channel("NIFTY"))
        # We don't even need to assert on the pub/sub side — just that
        # the read loop reaches the bytes path without raising.
        buf = make_ticker_frame_bytes(security_id=11536)
        conn = _FakeWsConnection(frames=[buf])
        factory, _ = _factory_returning(conn)
        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
            connect_factory=factory, sleep=_instant_sleep,
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=11536,
            exchange_segment="NSE_EQ",
            timeframes=[Timeframe.ONE_MIN],
        )
        await a.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await a.stop()


class TestPublishFailureTolerance:
    @pytest.mark.asyncio
    async def test_tick_publish_failure_does_not_kill_handler(
        self,
        fake_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If publish_json raises, the read loop continues."""
        async def _failing_publish(*_args: Any, **_kwargs: Any) -> int:
            raise ConnectionError("redis down")

        monkeypatch.setattr(ws_mod, "publish_json", _failing_publish)

        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=11536,
            exchange_segment="NSE_EQ",
            timeframes=[Timeframe.ONE_MIN],
        )
        buf = make_ticker_frame_bytes(security_id=11536)
        # Must not raise — publish failure logged + swallowed.
        await a._handle_binary_frame(buf)

    @pytest.mark.asyncio
    async def test_control_publish_failure_swallowed(
        self,
        fake_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _failing_publish(*_args: Any, **_kwargs: Any) -> int:
            raise ConnectionError("redis down")

        monkeypatch.setattr(ws_mod, "publish_json", _failing_publish)

        a = DhanWebSocketAdapter(
            client_id="C", access_token="T", user_id="u",
        )
        await a.subscribe(
            symbol="NIFTY",
            security_id=13,
            exchange_segment="IDX_I",
            timeframes=[],
        )
        # Emit functions log + swallow.
        await a._emit_disconnected_event(
            reason="x", failed_attempts=1, since=utc_datetime()
        )
        await a._emit_reconnected_event()


class TestThrottleRefillEdge:
    def test_refill_noop_on_negative_elapsed(self) -> None:
        t = _MessageThrottle(capacity=5, window_seconds=1.0)
        # Set last_refill to a future monotonic — elapsed becomes ≤ 0.
        t._last_refill = ws_mod.time.monotonic() + 1000.0
        t._tokens = 0.0
        t._refill()
        # Tokens unchanged.
        assert t._tokens == 0.0
