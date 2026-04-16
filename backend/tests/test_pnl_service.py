"""Tests for :mod:`app.services.pnl_service`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import uuid4

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.schemas.broker import Exchange, Position, ProductType
from app.services import pnl_service


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def _pos(symbol: str, qty: int, unrealized: str) -> Position:
    return Position(
        symbol=symbol,
        exchange=Exchange.NSE,
        quantity=qty,
        avg_price=Decimal("100"),
        ltp=Decimal("105"),
        unrealized_pnl=Decimal(unrealized),
        product_type=ProductType.INTRADAY,
    )


class TestRealized:
    async def test_record_and_read(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        total = await pnl_service.record_realized_pnl(
            uid, Decimal("500"), redis_conn=redis
        )
        assert total == Decimal("500")
        assert await pnl_service.get_realized_pnl(uid, redis_conn=redis) == Decimal(
            "500"
        )

    async def test_incremental(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        await pnl_service.record_realized_pnl(
            uid, Decimal("100"), redis_conn=redis
        )
        await pnl_service.record_realized_pnl(
            uid, Decimal("-40"), redis_conn=redis
        )
        assert await pnl_service.get_realized_pnl(uid, redis_conn=redis) == Decimal(
            "60"
        )

    async def test_rejects_non_decimal(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        with pytest.raises(TypeError):
            await pnl_service.record_realized_pnl(
                uuid4(), 100, redis_conn=redis  # type: ignore[arg-type]
            )


class TestPositions:
    async def test_update_and_read(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        positions = [_pos("RELIANCE", 10, "150"), _pos("INFY", -5, "-20")]
        await pnl_service.update_position_cache(uid, positions, redis_conn=redis)
        got = await pnl_service.get_positions_from_cache(uid, redis_conn=redis)
        assert len(got) == 2
        symbols = {p["symbol"] for p in got}
        assert symbols == {"RELIANCE", "INFY"}
        # Decimal values render as strings — preserves precision.
        assert got[0]["avg_price"] == "100"


class TestUnrealized:
    async def test_sums_cached_entries(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await pnl_service.update_position_cache(
            uid,
            [_pos("A", 10, "100"), _pos("B", -5, "-40")],
            redis_conn=redis,
        )
        total = await pnl_service.calculate_unrealized_pnl(uid, redis_conn=redis)
        assert total == Decimal("60")

    async def test_missing_cache_is_zero(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert await pnl_service.calculate_unrealized_pnl(
            uuid4(), redis_conn=redis
        ) == Decimal("0")

    async def test_skips_bad_entries(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await redis.set(
            f"pos:{uid}",
            '[{"unrealized_pnl": "50"}, {"unrealized_pnl": "xyz"}, {}]',
        )
        total = await pnl_service.calculate_unrealized_pnl(uid, redis_conn=redis)
        assert total == Decimal("50")


class TestDailyPnl:
    async def test_realized_plus_unrealized(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await pnl_service.record_realized_pnl(
            uid, Decimal("200"), redis_conn=redis
        )
        await pnl_service.update_position_cache(
            uid, [_pos("X", 1, "50")], redis_conn=redis
        )
        total = await pnl_service.calculate_daily_pnl(uid, redis_conn=redis)
        assert total == Decimal("250")

    async def test_zero_when_neither_present(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert await pnl_service.calculate_daily_pnl(
            uuid4(), redis_conn=redis
        ) == Decimal("0")
