"""Tests for :mod:`app.services.circuit_breaker_service`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import redis_client
from app.schemas.broker import (
    Exchange,
    OrderRequest,
    OrderSide,
    OrderType,
    ProductType,
)
from app.services.circuit_breaker_service import (
    CircuitBreakerLevel,
    CircuitBreakerService,
    circuit_breaker_service,
)


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def svc() -> CircuitBreakerService:
    return circuit_breaker_service


def _order(
    qty: int = 10,
    order_type: OrderType = OrderType.MARKET,
    price: Decimal | None = None,
    side: OrderSide = OrderSide.BUY,
) -> OrderRequest:
    return OrderRequest(
        symbol="NSE:RELIANCE-EQ",
        exchange=Exchange.NSE,
        side=side,
        quantity=qty,
        order_type=order_type,
        product_type=ProductType.INTRADAY,
        price=price,
    )


# ═══════════════════════════════════════════════════════════════════════
# Volatility
# ═══════════════════════════════════════════════════════════════════════


class TestVolatility:
    async def test_first_sample_is_allow(self, svc: CircuitBreakerService) -> None:
        decision = await svc.check_volatility(
            "RELIANCE", Exchange.NSE, Decimal("2500"), now=datetime(2026, 1, 1, tzinfo=UTC)
        )
        assert decision.level is CircuitBreakerLevel.ALLOW

    async def test_small_move_allow(self, svc: CircuitBreakerService) -> None:
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.check_volatility("X", Exchange.NSE, Decimal("100"), now=t0)
        d = await svc.check_volatility(
            "X", Exchange.NSE, Decimal("101"), now=t0 + timedelta(seconds=3)
        )
        # 1% move — below 2% threshold → ALLOW
        assert d.level is CircuitBreakerLevel.ALLOW

    async def test_pause_short_on_2pct_in_5s(self, svc: CircuitBreakerService) -> None:
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.check_volatility("X", Exchange.NSE, Decimal("100"), now=t0)
        d = await svc.check_volatility(
            "X", Exchange.NSE, Decimal("103"), now=t0 + timedelta(seconds=3)
        )
        assert d.level is CircuitBreakerLevel.PAUSE_SHORT
        assert d.until is not None

    async def test_pause_long_on_5pct_in_60s(self, svc: CircuitBreakerService) -> None:
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.check_volatility("Y", Exchange.NSE, Decimal("100"), now=t0)
        # 10s window so 2%-in-5s won't match; 5% move does match 60s window.
        d = await svc.check_volatility(
            "Y", Exchange.NSE, Decimal("106"), now=t0 + timedelta(seconds=10)
        )
        assert d.level is CircuitBreakerLevel.PAUSE_LONG

    async def test_halt_on_10pct(self, svc: CircuitBreakerService) -> None:
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.check_volatility("Z", Exchange.NSE, Decimal("100"), now=t0)
        d = await svc.check_volatility(
            "Z", Exchange.NSE, Decimal("112"), now=t0 + timedelta(seconds=60)
        )
        assert d.level is CircuitBreakerLevel.HALT
        assert d.until is None

    async def test_halt_persists_until_override(
        self, svc: CircuitBreakerService
    ) -> None:
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.check_volatility("H", Exchange.NSE, Decimal("100"), now=t0)
        await svc.check_volatility(
            "H", Exchange.NSE, Decimal("115"), now=t0 + timedelta(seconds=5)
        )
        level = await svc.get_state("H", Exchange.NSE)
        assert level is CircuitBreakerLevel.HALT

    async def test_pause_auto_expires(self, svc: CircuitBreakerService) -> None:
        """After ``until`` passes, ``get_state`` transparently clears the key."""
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.check_volatility("P", Exchange.NSE, Decimal("100"), now=t0)
        # Trigger a PAUSE with an ``until`` anchored to ``t0`` — long in the
        # past relative to real-wall-clock — so the TTL has already expired
        # when we read it back.
        await svc.check_volatility(
            "P", Exchange.NSE, Decimal("103"), now=t0 + timedelta(seconds=3)
        )
        level = await svc.get_state("P", Exchange.NSE)
        assert level is CircuitBreakerLevel.ALLOW

    async def test_invalid_price_is_allow(
        self, svc: CircuitBreakerService
    ) -> None:
        d = await svc.check_volatility("I", Exchange.NSE, Decimal("0"))
        assert d.level is CircuitBreakerLevel.ALLOW

    async def test_halt_short_circuits_new_checks(
        self, svc: CircuitBreakerService
    ) -> None:
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.admin_override("S", Exchange.NSE, action=CircuitBreakerLevel.HALT)
        d = await svc.check_volatility(
            "S", Exchange.NSE, Decimal("100"), now=t0
        )
        assert d.level is CircuitBreakerLevel.HALT


# ═══════════════════════════════════════════════════════════════════════
# Admin override
# ═══════════════════════════════════════════════════════════════════════


class TestAdminOverride:
    async def test_force_halt(self, svc: CircuitBreakerService) -> None:
        await svc.admin_override("A", Exchange.NSE, action=CircuitBreakerLevel.HALT)
        assert await svc.get_state("A", Exchange.NSE) is CircuitBreakerLevel.HALT

    async def test_force_allow_resumes(
        self, svc: CircuitBreakerService
    ) -> None:
        await svc.admin_override("B", Exchange.NSE, action=CircuitBreakerLevel.HALT)
        await svc.admin_override("B", Exchange.NSE, action=CircuitBreakerLevel.ALLOW)
        assert await svc.get_state("B", Exchange.NSE) is CircuitBreakerLevel.ALLOW

    async def test_invalid_action(self, svc: CircuitBreakerService) -> None:
        with pytest.raises(ValueError):
            await svc.admin_override(
                "C", Exchange.NSE, action=CircuitBreakerLevel.PAUSE_SHORT
            )


# ═══════════════════════════════════════════════════════════════════════
# Order sanity
# ═══════════════════════════════════════════════════════════════════════


class TestOrderSanity:
    def test_allows_normal_order(self, svc: CircuitBreakerService) -> None:
        decision = svc.check_order_sanity(
            _order(qty=5), user_avg_order_size=Decimal("10")
        )
        assert decision.allow is True
        assert decision.reasons == []

    def test_blocks_10x_quantity(self, svc: CircuitBreakerService) -> None:
        decision = svc.check_order_sanity(
            _order(qty=500), user_avg_order_size=Decimal("10")
        )
        assert decision.allow is False
        assert any("quantity" in r for r in decision.reasons)

    def test_blocks_over_daily_budget(self, svc: CircuitBreakerService) -> None:
        decision = svc.check_order_sanity(
            _order(qty=10, order_type=OrderType.LIMIT, price=Decimal("1000")),
            user_daily_budget=Decimal("5000"),
        )
        assert decision.allow is False

    def test_price_band_warning(self, svc: CircuitBreakerService) -> None:
        decision = svc.check_order_sanity(
            _order(qty=1, order_type=OrderType.LIMIT, price=Decimal("110")),
            ltp=Decimal("100"),
        )
        # 10% from LTP → warning not block.
        assert decision.allow is True
        assert decision.warnings


# ═══════════════════════════════════════════════════════════════════════
# Order conversion
# ═══════════════════════════════════════════════════════════════════════


class TestOrderConversion:
    def test_allow_passes_order_through(
        self, svc: CircuitBreakerService
    ) -> None:
        order = _order()
        converted = svc.convert_order_in_volatile_market(
            order, level=CircuitBreakerLevel.ALLOW, ltp=Decimal("100")
        )
        assert converted is order

    def test_halt_blocks(self, svc: CircuitBreakerService) -> None:
        order = _order()
        converted = svc.convert_order_in_volatile_market(
            order, level=CircuitBreakerLevel.HALT, ltp=Decimal("100")
        )
        assert converted is None

    def test_pause_converts_market_to_limit(
        self, svc: CircuitBreakerService
    ) -> None:
        order = _order(side=OrderSide.BUY)
        converted = svc.convert_order_in_volatile_market(
            order,
            level=CircuitBreakerLevel.PAUSE_SHORT,
            ltp=Decimal("100"),
        )
        assert converted is not None
        assert converted.order_type is OrderType.LIMIT
        assert converted.price == Decimal("100.50")

    def test_pause_sell_limit_below_ltp(
        self, svc: CircuitBreakerService
    ) -> None:
        order = _order(side=OrderSide.SELL)
        converted = svc.convert_order_in_volatile_market(
            order,
            level=CircuitBreakerLevel.PAUSE_SHORT,
            ltp=Decimal("100"),
        )
        assert converted is not None
        assert converted.price == Decimal("99.50")

    def test_pause_without_ltp_blocks(
        self, svc: CircuitBreakerService
    ) -> None:
        order = _order()
        converted = svc.convert_order_in_volatile_market(
            order, level=CircuitBreakerLevel.PAUSE_SHORT, ltp=None
        )
        assert converted is None

    def test_pause_limit_order_unchanged(
        self, svc: CircuitBreakerService
    ) -> None:
        order = _order(order_type=OrderType.LIMIT, price=Decimal("99"))
        converted = svc.convert_order_in_volatile_market(
            order,
            level=CircuitBreakerLevel.PAUSE_SHORT,
            ltp=Decimal("100"),
        )
        assert converted is order


# ═══════════════════════════════════════════════════════════════════════
# Multiple symbols tracked independently
# ═══════════════════════════════════════════════════════════════════════


class TestIndependentSymbols:
    async def test_symbols_do_not_cross_contaminate(
        self, svc: CircuitBreakerService
    ) -> None:
        t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        await svc.check_volatility("ONE", Exchange.NSE, Decimal("100"), now=t0)
        await svc.check_volatility(
            "ONE", Exchange.NSE, Decimal("120"), now=t0 + timedelta(seconds=3)
        )
        assert await svc.get_state("ONE", Exchange.NSE) is CircuitBreakerLevel.HALT

        # Distinct symbol starts clean.
        assert await svc.get_state("TWO", Exchange.NSE) is CircuitBreakerLevel.ALLOW
