"""Tests for the at-least-once broker-order idempotency guard (M5).

Incident 2026-05-20 follow-up: `place_strategy_orders` / `execute_exit` had
no signal-level idempotency, so a Celery retry after an *ambiguous* failure
(Dhan accepted the order but the response was lost) could place a duplicate
LIVE order. The guard claims a per-(signal, action) Redis slot immediately
before the broker call, after the symbol/funds pre-checks.

These drive `_live_place_order` directly (the entry chokepoint) with a fake
broker + fakeredis, asserting the broker.place_order call count, plus the
helper's own semantics.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fakeredis import aioredis as fake_aioredis

from app.core import signal_idempotency
from app.core.exceptions import (
    BrokerConnectionError,
    BrokerInvalidSymbolError,
    DuplicateOrderSuppressedError,
)
from app.schemas.broker import (
    BrokerName,
    OrderFill,
    OrderResponse,
    OrderSide,
    OrderStatus,
)
from app.services import strategy_executor

pytestmark = pytest.mark.asyncio


class _FakeBroker:
    """Minimal broker exposing only what `_live_place_order` touches."""

    def __init__(
        self,
        *,
        place_raises: Exception | None = None,
        validate_raises: Exception | None = None,
    ) -> None:
        self.broker_name = BrokerName.DHAN
        self.place_calls = 0
        self.validate_calls = 0
        self._place_raises = place_raises
        self._validate_raises = validate_raises

    async def is_session_valid(self) -> bool:
        return True

    async def login(self) -> bool:
        return True

    async def validate_symbol(self, symbol: str, exchange: Any) -> None:
        self.validate_calls += 1
        if self._validate_raises is not None:
            raise self._validate_raises

    async def get_funds(self) -> Decimal:
        return Decimal("10000000")  # 1 cr — clears any pre-trade floor

    async def place_order(self, order: Any) -> OrderResponse:
        self.place_calls += 1
        if self._place_raises is not None:
            raise self._place_raises
        return OrderResponse(
            broker_order_id="OID-1",
            status=OrderStatus.PENDING,
            message="",
            raw_response={},
        )

    async def confirm_fill(
        self, broker_order_id: str, *, expected_qty: int = 0, **_: Any
    ) -> OrderFill:
        # Terminal COMPLETE fill so the executor's fill-gate passes.
        return OrderFill(
            broker_order_id=str(broker_order_id),
            order_status=OrderStatus.COMPLETE,
            filled_qty=expected_qty or 10**6,
            avg_price=Decimal("100"),
        )


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> fake_aioredis.FakeRedis:
    """Shared FakeRedis wired in as the process redis singleton so the claim
    persists across calls within a test."""
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: client)
    return client


async def _place(broker: _FakeBroker, signal_id: Any) -> Any:
    return await strategy_executor._live_place_order(
        broker=broker,
        user_id=uuid4(),
        symbol="BSE-MAY2026-FUT",
        side=OrderSide.BUY,
        quantity=1,
        lot_size=1,
        signal_id=signal_id,
        action_kind="entry",
    )


class TestIdempotencyWire:
    async def test_retry_after_success_no_duplicate(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        broker = _FakeBroker()
        sid = uuid4()
        await _place(broker, sid)  # 1st attempt places
        with pytest.raises(DuplicateOrderSuppressedError):
            await _place(broker, sid)  # retry → slot held → suppressed
        assert broker.place_calls == 1

    async def test_retry_after_ambiguous_post_send_blocks_retry(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        """The key case: order possibly reached the broker, response lost."""
        broker = _FakeBroker(place_raises=BrokerConnectionError("timeout", broker_name="dhan"))
        sid = uuid4()
        with pytest.raises(BrokerConnectionError):
            await _place(broker, sid)  # claim taken, then place raises (ambiguous)
        with pytest.raises(DuplicateOrderSuppressedError):
            await _place(broker, sid)  # retry suppressed — claim retained
        assert broker.place_calls == 1  # never placed twice

    async def test_retry_after_validation_error_fresh_execute(
        self, fake_redis: fake_aioredis.FakeRedis
    ) -> None:
        """Pre-send failure happens BEFORE the claim → a retry re-executes."""
        bad = _FakeBroker(validate_raises=BrokerInvalidSymbolError("nope", broker_name="dhan"))
        sid = uuid4()
        with pytest.raises(BrokerInvalidSymbolError):
            await _place(bad, sid)
        assert bad.place_calls == 0  # never reached the broker call / claim

        good = _FakeBroker()  # retry: validation now passes
        await _place(good, sid)
        assert good.place_calls == 1  # fresh execute — claim was never taken

    async def test_distinct_signals_no_collision(self, fake_redis: fake_aioredis.FakeRedis) -> None:
        broker = _FakeBroker()
        await _place(broker, uuid4())
        await _place(broker, uuid4())
        assert broker.place_calls == 2


class TestHelper:
    async def test_claim_then_duplicate(self) -> None:
        r = fake_aioredis.FakeRedis(decode_responses=True)
        sid = uuid4()
        assert await signal_idempotency.check_and_set_signal_idempotent(r, sid, "entry") is True
        assert await signal_idempotency.check_and_set_signal_idempotent(r, sid, "entry") is False

    async def test_release_allows_reclaim(self) -> None:
        r = fake_aioredis.FakeRedis(decode_responses=True)
        sid = uuid4()
        assert await signal_idempotency.check_and_set_signal_idempotent(r, sid, "entry") is True
        await signal_idempotency.release_signal_idempotent(r, sid, "entry")
        assert await signal_idempotency.check_and_set_signal_idempotent(r, sid, "entry") is True

    async def test_distinct_action_kinds_independent(self) -> None:
        r = fake_aioredis.FakeRedis(decode_responses=True)
        sid = uuid4()
        assert await signal_idempotency.check_and_set_signal_idempotent(r, sid, "entry") is True
        assert await signal_idempotency.check_and_set_signal_idempotent(r, sid, "exit") is True

    async def test_zero_ttl_rejected(self) -> None:
        r = fake_aioredis.FakeRedis(decode_responses=True)
        with pytest.raises(ValueError):
            await signal_idempotency.check_and_set_signal_idempotent(
                r, uuid4(), "entry", ttl_seconds=0
            )
