"""Unit tests for :class:`app.brokers.base.BrokerInterface`.

These tests lock in the ABC contract:
    1. The abstract base class cannot be instantiated directly.
    2. A subclass that implements every method instantiates fine and its
       methods are callable.
    3. A subclass that forgets any abstract method raises ``TypeError`` at
       instantiation.
    4. Schema validators (OrderRequest) reject invalid combinations.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import ClassVar

import pytest

from app.brokers.base import BrokerInterface
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    Holding,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    ProductType,
    Quote,
)

# ═══════════════════════════════════════════════════════════════════════
# Test doubles
# ═══════════════════════════════════════════════════════════════════════


def _sample_credentials() -> BrokerCredentials:
    return BrokerCredentials(
        broker=BrokerName.FYERS,
        user_id="11111111-1111-1111-1111-111111111111",
        client_id="XA00001",
        api_key="test-key",
        api_secret="test-secret",
    )


class DummyBroker(BrokerInterface):
    """Minimal subclass implementing every abstract method.

    Used only to verify that the ABC wiring is correct — no real logic.
    """

    broker_name: ClassVar[BrokerName] = BrokerName.FYERS

    def __init__(self, credentials: BrokerCredentials) -> None:
        self._credentials = credentials
        self._session_active = False

    async def login(self) -> bool:
        self._session_active = True
        return True

    async def is_session_valid(self) -> bool:
        return self._session_active

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        return OrderResponse(
            broker_order_id="ORDER-1",
            status=OrderStatus.PENDING,
            message="accepted",
            raw_response={"echo": order.symbol},
        )

    async def modify_order(
        self, broker_order_id: str, order: OrderRequest
    ) -> OrderResponse:
        return OrderResponse(
            broker_order_id=broker_order_id,
            status=OrderStatus.OPEN,
            message="modified",
        )

    async def cancel_order(self, broker_order_id: str) -> bool:
        return True

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        return OrderStatus.COMPLETE

    async def get_positions(self) -> list[Position]:
        return [
            Position(
                symbol="NIFTY25JANFUT",
                exchange=Exchange.NFO,
                quantity=50,
                avg_price=Decimal("22000.50"),
                ltp=Decimal("22050.00"),
                unrealized_pnl=Decimal("2475.00"),
                product_type=ProductType.INTRADAY,
            )
        ]

    async def get_holdings(self) -> list[Holding]:
        return [
            Holding(
                symbol="RELIANCE",
                exchange=Exchange.NSE,
                quantity=10,
                avg_price=Decimal("2500.00"),
                ltp=Decimal("2550.00"),
                current_value=Decimal("25500.00"),
                pnl=Decimal("500.00"),
            )
        ]

    async def get_funds(self) -> Decimal:
        return Decimal("100000.00")

    async def get_quote(self, symbol: str, exchange: Exchange) -> Quote:
        return Quote(
            symbol=symbol,
            exchange=exchange,
            ltp=Decimal("100.25"),
            bid=Decimal("100.20"),
            ask=Decimal("100.30"),
            volume=123456,
            timestamp=datetime(2026, 4, 15, 9, 15, 0),
        )

    async def square_off_all(self) -> list[OrderResponse]:
        return [
            OrderResponse(
                broker_order_id="SQUARE-1",
                status=OrderStatus.COMPLETE,
                message="squared off",
            )
        ]

    async def cancel_all_pending(self) -> int:
        return 0

    def normalize_symbol(self, tradingview_symbol: str, exchange: Exchange) -> str:
        return f"{exchange.value}:{tradingview_symbol}"


# ═══════════════════════════════════════════════════════════════════════
# ABC contract tests
# ═══════════════════════════════════════════════════════════════════════


class TestBrokerInterfaceContract:
    def test_cannot_instantiate_abstract_base_class(self) -> None:
        """BrokerInterface is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError) as exc_info:
            BrokerInterface(_sample_credentials())  # type: ignore[abstract]
        assert "abstract" in str(exc_info.value).lower()

    def test_full_subclass_instantiates(self) -> None:
        broker = DummyBroker(_sample_credentials())
        assert broker.broker_name is BrokerName.FYERS
        assert isinstance(broker, BrokerInterface)

    def test_missing_abstract_method_raises_type_error(self) -> None:
        """A subclass that skips ``cancel_order`` must not be instantiable."""

        class IncompleteBroker(BrokerInterface):
            broker_name: ClassVar[BrokerName] = BrokerName.DHAN

            def __init__(self, credentials: BrokerCredentials) -> None:
                self._credentials = credentials

            async def login(self) -> bool:
                return True

            async def is_session_valid(self) -> bool:
                return True

            async def place_order(self, order: OrderRequest) -> OrderResponse:
                raise NotImplementedError

            async def modify_order(
                self, broker_order_id: str, order: OrderRequest
            ) -> OrderResponse:
                raise NotImplementedError

            # cancel_order intentionally omitted.

            async def get_order_status(self, broker_order_id: str) -> OrderStatus:
                return OrderStatus.PENDING

            async def get_positions(self) -> list[Position]:
                return []

            async def get_holdings(self) -> list[Holding]:
                return []

            async def get_funds(self) -> Decimal:
                return Decimal("0")

            async def get_quote(self, symbol: str, exchange: Exchange) -> Quote:
                raise NotImplementedError

            async def square_off_all(self) -> list[OrderResponse]:
                return []

            async def cancel_all_pending(self) -> int:
                return 0

            def normalize_symbol(
                self, tradingview_symbol: str, exchange: Exchange
            ) -> str:
                return tradingview_symbol

        with pytest.raises(TypeError) as exc_info:
            IncompleteBroker(_sample_credentials())  # type: ignore[abstract]
        assert "cancel_order" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════
# DummyBroker behaviour tests (smoke tests for async method signatures)
# ═══════════════════════════════════════════════════════════════════════


class TestDummyBrokerBehaviour:
    """Smoke tests verifying the async method signatures round-trip cleanly."""

    @pytest.fixture
    def broker(self) -> DummyBroker:
        return DummyBroker(_sample_credentials())

    async def test_login_flips_session(self, broker: DummyBroker) -> None:
        assert await broker.is_session_valid() is False
        assert await broker.login() is True
        assert await broker.is_session_valid() is True

    async def test_place_order_returns_pending(self, broker: DummyBroker) -> None:
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        response = await broker.place_order(order)
        assert response.broker_order_id == "ORDER-1"
        assert response.status is OrderStatus.PENDING
        assert response.raw_response == {"echo": "RELIANCE"}

    async def test_get_positions_returns_typed_list(self, broker: DummyBroker) -> None:
        positions = await broker.get_positions()
        assert len(positions) == 1
        assert positions[0].unrealized_pnl == Decimal("2475.00")

    async def test_get_funds_is_decimal(self, broker: DummyBroker) -> None:
        funds = await broker.get_funds()
        assert isinstance(funds, Decimal)
        assert funds == Decimal("100000.00")

    def test_normalize_symbol_is_pure(self, broker: DummyBroker) -> None:
        assert broker.normalize_symbol("NIFTY25JANFUT", Exchange.NFO) == "NFO:NIFTY25JANFUT"


# ═══════════════════════════════════════════════════════════════════════
# OrderRequest validation tests
# ═══════════════════════════════════════════════════════════════════════


class TestOrderRequestValidation:
    """Cross-field validators must reject ambiguous order combinations."""

    def test_market_order_accepts_no_price(self) -> None:
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        assert order.price is None

    def test_market_order_rejects_price(self) -> None:
        with pytest.raises(ValueError, match="MARKET order must not carry a price"):
            OrderRequest(
                symbol="RELIANCE",
                exchange=Exchange.NSE,
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.MARKET,
                product_type=ProductType.INTRADAY,
                price=Decimal("2500"),
            )

    def test_limit_order_requires_price(self) -> None:
        with pytest.raises(ValueError, match="LIMIT order requires a positive price"):
            OrderRequest(
                symbol="RELIANCE",
                exchange=Exchange.NSE,
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.LIMIT,
                product_type=ProductType.INTRADAY,
            )

    def test_sl_order_requires_both_prices(self) -> None:
        with pytest.raises(ValueError, match="SL order requires a positive trigger_price"):
            OrderRequest(
                symbol="RELIANCE",
                exchange=Exchange.NSE,
                side=OrderSide.SELL,
                quantity=1,
                order_type=OrderType.SL,
                product_type=ProductType.INTRADAY,
                price=Decimal("2500"),
            )

    def test_sl_m_order_requires_trigger_only(self) -> None:
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.SELL,
            quantity=1,
            order_type=OrderType.SL_M,
            product_type=ProductType.INTRADAY,
            trigger_price=Decimal("2490"),
        )
        assert order.trigger_price == Decimal("2490")
        assert order.price is None

    def test_sl_m_order_rejects_price(self) -> None:
        with pytest.raises(ValueError, match="SL_M order must not carry a price"):
            OrderRequest(
                symbol="RELIANCE",
                exchange=Exchange.NSE,
                side=OrderSide.SELL,
                quantity=1,
                order_type=OrderType.SL_M,
                product_type=ProductType.INTRADAY,
                price=Decimal("2500"),
                trigger_price=Decimal("2490"),
            )

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            OrderRequest(
                symbol="RELIANCE",
                exchange=Exchange.NSE,
                side=OrderSide.BUY,
                quantity=0,
                order_type=OrderType.MARKET,
                product_type=ProductType.INTRADAY,
            )

    def test_model_is_frozen(self) -> None:
        order = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        )
        with pytest.raises(ValueError):
            order.symbol = "TCS"  # type: ignore[misc]
