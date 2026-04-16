"""Tests for :mod:`app.services.order_service`.

Uses an in-memory aiosqlite DB for persistence and a hand-rolled fake
broker so we can assert exactly which :class:`BrokerInterface` method was
called with which normalized arguments.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.exceptions import (
    BrokerOrderRejectedError,
    BrokerSessionExpiredError,
)
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.trade import Trade, TradeStatus
from app.db.models.user import User
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    ProductType,
)
from app.schemas.webhook import WebhookAction, WebhookPayload
from app.services.order_service import OrderResult, process_webhook_signal


# ═══════════════════════════════════════════════════════════════════════
# Fake broker
# ═══════════════════════════════════════════════════════════════════════


class _FakeBroker:
    """Configurable stand-in for :class:`BrokerInterface`."""

    broker_name = BrokerName.FYERS

    def __init__(
        self,
        *,
        session_valid: bool = True,
        place_responses: list[OrderResponse | Exception] | None = None,
        positions: list[Position] | None = None,
    ) -> None:
        self._session_valid = session_valid
        self._place_queue: list[OrderResponse | Exception] = list(
            place_responses or []
        )
        self._positions: list[Position] = positions or []
        self.login_calls = 0
        self.place_calls: list[OrderRequest] = []
        self.positions_calls = 0

    async def login(self) -> bool:
        self.login_calls += 1
        self._session_valid = True
        return True

    async def is_session_valid(self) -> bool:
        return self._session_valid

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        self.place_calls.append(order)
        if not self._place_queue:
            return OrderResponse(
                broker_order_id=f"OID-{len(self.place_calls)}",
                status=OrderStatus.PENDING,
                message="ok",
            )
        next_resp = self._place_queue.pop(0)
        if isinstance(next_resp, Exception):
            raise next_resp
        return next_resp

    async def get_positions(self) -> list[Position]:
        self.positions_calls += 1
        return list(self._positions)

    def normalize_symbol(self, tradingview_symbol: str, exchange: Exchange) -> str:
        return f"{exchange.value}:{tradingview_symbol}-EQ"


def _factory(broker: _FakeBroker) -> Any:
    def _build(_creds: BrokerCredentials) -> _FakeBroker:
        return broker

    return _build


# ═══════════════════════════════════════════════════════════════════════
# DB fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def user_and_credential(
    session: AsyncSession,
) -> tuple[User, BrokerCredential]:
    user = User(
        email="u@example.com",
        password_hash="hash",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    creds = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.FYERS,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SECRET"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    session.add(creds)
    await session.flush()
    return user, creds


def _payload(**overrides: Any) -> WebhookPayload:
    base: dict[str, Any] = {
        "action": WebhookAction.BUY,
        "symbol": "RELIANCE",
        "exchange": Exchange.NSE,
        "order_type": OrderType.MARKET,
        "product_type": ProductType.INTRADAY,
        "quantity": 10,
    }
    base.update(overrides)
    return WebhookPayload(**base)


# ═══════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════


class TestBuyFlow:
    async def test_buy_places_order_with_normalized_symbol(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker()
        result = await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(action=WebhookAction.BUY),
            broker_factory=_factory(broker),
        )
        assert result.success is True
        assert broker.place_calls[0].symbol == "NSE:RELIANCE-EQ"
        assert broker.place_calls[0].side is OrderSide.BUY
        assert broker.place_calls[0].quantity == 10

    async def test_sell_places_order(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker()
        await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(action=WebhookAction.SELL),
            broker_factory=_factory(broker),
        )
        assert broker.place_calls[0].side is OrderSide.SELL

    async def test_trade_row_written(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker()
        result = await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(),
            broker_factory=_factory(broker),
        )
        from sqlalchemy import select

        row = (
            await session.execute(select(Trade).where(Trade.id == result.trade_id))
        ).scalar_one()
        assert row.symbol == "NSE:RELIANCE-EQ"
        assert row.broker_order_id == "OID-1"
        assert row.latency_ms is not None
        assert row.latency_ms >= 0

    async def test_latency_ms_populated(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker()
        result = await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(),
            broker_factory=_factory(broker),
        )
        assert isinstance(result, OrderResult)
        assert result.latency_ms >= 0


# ═══════════════════════════════════════════════════════════════════════
# EXIT flow
# ═══════════════════════════════════════════════════════════════════════


class TestExitFlow:
    async def test_exit_squares_off_long(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        open_pos = Position(
            symbol="NSE:RELIANCE-EQ",
            exchange=Exchange.NSE,
            quantity=10,
            avg_price=Decimal("100"),
            ltp=Decimal("105"),
            unrealized_pnl=Decimal("50"),
            product_type=ProductType.INTRADAY,
        )
        broker = _FakeBroker(positions=[open_pos])
        await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(action=WebhookAction.EXIT),
            broker_factory=_factory(broker),
        )
        assert broker.positions_calls == 1
        assert broker.place_calls[0].side is OrderSide.SELL
        assert broker.place_calls[0].quantity == 10

    async def test_exit_squares_off_short(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        short_pos = Position(
            symbol="NSE:RELIANCE-EQ",
            exchange=Exchange.NSE,
            quantity=-5,
            avg_price=Decimal("100"),
            ltp=Decimal("98"),
            unrealized_pnl=Decimal("10"),
            product_type=ProductType.INTRADAY,
        )
        broker = _FakeBroker(positions=[short_pos])
        await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(action=WebhookAction.EXIT),
            broker_factory=_factory(broker),
        )
        assert broker.place_calls[0].side is OrderSide.BUY
        assert broker.place_calls[0].quantity == 5

    async def test_exit_no_position_noop(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker(positions=[])
        result = await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(action=WebhookAction.EXIT),
            broker_factory=_factory(broker),
        )
        # No place_order call in noop path
        assert broker.place_calls == []
        assert result.order_status is OrderStatus.COMPLETE


# ═══════════════════════════════════════════════════════════════════════
# Session handling
# ═══════════════════════════════════════════════════════════════════════


class TestSession:
    async def test_invalid_session_triggers_login(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker(session_valid=False)
        await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(),
            broker_factory=_factory(broker),
        )
        assert broker.login_calls == 1

    async def test_session_expired_mid_flight_retries_once(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker(
            place_responses=[
                BrokerSessionExpiredError("expired", broker_name="fyers"),
                OrderResponse(
                    broker_order_id="RETRY-1",
                    status=OrderStatus.PENDING,
                    message="ok",
                ),
            ],
        )
        result = await process_webhook_signal(
            session,
            user_id=user.id,
            broker_credential_id=creds.id,
            payload=_payload(),
            broker_factory=_factory(broker),
        )
        assert broker.login_calls >= 1
        assert result.broker_order_id == "RETRY-1"


# ═══════════════════════════════════════════════════════════════════════
# Error propagation
# ═══════════════════════════════════════════════════════════════════════


class TestErrors:
    async def test_rejected_order_bubbles_up(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        user, creds = user_and_credential
        broker = _FakeBroker(
            place_responses=[
                BrokerOrderRejectedError(
                    "rejected", broker_name="fyers", reason="insufficient margin"
                )
            ],
        )
        with pytest.raises(BrokerOrderRejectedError) as excinfo:
            await process_webhook_signal(
                session,
                user_id=user.id,
                broker_credential_id=creds.id,
                payload=_payload(),
                broker_factory=_factory(broker),
            )
        assert excinfo.value.reason == "insufficient margin"

    async def test_missing_credential_raises_auth_error(
        self, session: AsyncSession
    ) -> None:
        from app.core.exceptions import BrokerAuthError

        with pytest.raises(BrokerAuthError, match="Broker credential not found"):
            await process_webhook_signal(
                session,
                user_id=uuid.uuid4(),
                broker_credential_id=uuid.uuid4(),
                payload=_payload(),
            )

    async def test_scoped_to_user_id(
        self,
        session: AsyncSession,
        user_and_credential: tuple[User, BrokerCredential],
    ) -> None:
        """A user cannot use another user's credential even if the UUID is known."""
        _, creds = user_and_credential
        from app.core.exceptions import BrokerAuthError

        with pytest.raises(BrokerAuthError):
            await process_webhook_signal(
                session,
                user_id=uuid.uuid4(),  # Different user
                broker_credential_id=creds.id,
                payload=_payload(),
            )
