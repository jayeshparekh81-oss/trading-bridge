"""Pre-trade gate tests for :func:`app.services.strategy_executor._live_place_order`.

Covers the two checks added in Tier-1 Task #4:

* **Symbol resolution probe** — :meth:`BrokerInterface.validate_symbol`.
  Default no-op; Dhan overrides to fail fast on unknown symbols.
* **Coarse margin floor** — `available < quantity × pre_trade_margin_per_lot_inr × 1.10`
  raises :class:`BrokerInsufficientFundsError` *before* the broker
  ``place_order`` call. NOT a real margin calculator — see config docstring.

The fifth test pins the SQLite in-memory test fixture fix (StaticPool +
``check_same_thread=False``). Without that fix, seed-side User INSERTs
were silently rolled back; with it, a request-side ``select(User.is_active)``
returns the seeded value. This unblocks Tier-1 Task #5 (gate B: user-active
check on the strategy webhook).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.brokers.base import BrokerInterface
from app.core.exceptions import (
    BrokerInsufficientFundsError,
    BrokerInvalidSymbolError,
)
from app.db.models.broker_credential import BrokerCredential
from app.db.models.user import User
from app.schemas.broker import BrokerName, Exchange, OrderResponse, OrderSide, OrderStatus
from app.services.strategy_executor import _live_place_order
from tests.integration.conftest import _seed_user_with_strategy


# ═══════════════════════════════════════════════════════════════════════
# Fake broker — implements only what _live_place_order touches
# ═══════════════════════════════════════════════════════════════════════


def _make_fake_broker(
    *,
    funds: Decimal,
    validate_raises: Exception | None = None,
    place_order_response: OrderResponse | None = None,
) -> MagicMock:
    """Build an ``BrokerInterface`` mock with the methods _live_place_order calls.

    ``validate_raises`` lets a test inject :class:`BrokerInvalidSymbolError`
    so the symbol-resolution probe exercises its raise path.
    """
    broker = MagicMock(spec=BrokerInterface)
    # broker_name is a ClassVar on BrokerInterface subclasses; the spec
    # mock doesn't reproduce its concrete value. Set it explicitly so the
    # margin-error path can read `broker.broker_name.value`.
    broker.broker_name = BrokerName.DHAN
    broker.is_session_valid = AsyncMock(return_value=True)
    broker.login = AsyncMock(return_value=True)

    if validate_raises is not None:
        broker.validate_symbol = AsyncMock(side_effect=validate_raises)
    else:
        broker.validate_symbol = AsyncMock(return_value=None)

    broker.get_funds = AsyncMock(return_value=funds)

    if place_order_response is None:
        place_order_response = OrderResponse(
            broker_order_id="LIVE-ORDER-123",
            status=OrderStatus.PENDING,
            message="placed",
            raw_response={"echo": "fake-broker"},
        )
    broker.place_order = AsyncMock(return_value=place_order_response)
    return broker


def _factory_returning(
    broker: MagicMock,
) -> Callable[[Any], BrokerInterface]:
    """Build a ``broker_factory`` callable matching ``_live_place_order``'s signature."""

    def _factory(_creds: Any) -> BrokerInterface:
        return broker

    return _factory


async def _fetch_cred_row(
    maker: async_sessionmaker[AsyncSession], user_id: uuid.UUID
) -> BrokerCredential:
    async with maker() as s:
        stmt = select(BrokerCredential).where(BrokerCredential.user_id == user_id)
        return (await s.execute(stmt)).scalar_one()


# ═══════════════════════════════════════════════════════════════════════
# Tests — pre-trade gates
# ═══════════════════════════════════════════════════════════════════════


class TestMarginSufficient:
    def test_funds_above_threshold_allow_place_order(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """1 lot needs ~₹110,000 (₹100k × 1.10 buffer); ₹500k is plenty."""
        import asyncio

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker, email="margin-ok@tradetri.com"
            )
        )
        cred_row = asyncio.get_event_loop().run_until_complete(
            _fetch_cred_row(db_session_maker, seeded["user_id"])
        )

        broker = _make_fake_broker(funds=Decimal("500000"))
        result = asyncio.get_event_loop().run_until_complete(
            _live_place_order(
                broker=broker,
                user_id=seeded["user_id"],
                symbol="NIFTY",
                side=OrderSide.BUY,
                quantity=1,
                lot_size=1,
            )
        )

        assert result["broker_order_id"] == "LIVE-ORDER-123"
        broker.validate_symbol.assert_awaited_once_with("NIFTY", Exchange.NFO)
        broker.get_funds.assert_awaited_once()
        broker.place_order.assert_awaited_once()


class TestMarginInsufficient:
    def test_funds_below_threshold_raises_insufficient_funds(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """1 lot needs ₹110,000 (with buffer); ₹50k is not enough.

        Asserts:
        * ``BrokerInsufficientFundsError`` is raised.
        * ``available_funds`` and ``required_estimate`` are surfaced in
          the exception metadata (debug-friendly).
        * ``place_order`` is NEVER called — we save the broker round-trip.
        """
        import asyncio

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker, email="margin-low@tradetri.com"
            )
        )
        cred_row = asyncio.get_event_loop().run_until_complete(
            _fetch_cred_row(db_session_maker, seeded["user_id"])
        )

        broker = _make_fake_broker(funds=Decimal("50000"))

        with pytest.raises(BrokerInsufficientFundsError) as exc:
            asyncio.get_event_loop().run_until_complete(
                _live_place_order(
                    broker=broker,
                    user_id=seeded["user_id"],
                    symbol="NIFTY",
                    side=OrderSide.BUY,
                    quantity=1,
                    lot_size=1,
                )
            )

        meta = exc.value.metadata
        assert meta["available_funds"] == "50000"
        assert meta["required_estimate"] == "110000.00"
        assert meta["quantity"] == 1
        assert meta["floor_per_lot"] == "100000"
        assert meta["slippage_buffer"] == "1.10"

        broker.place_order.assert_not_awaited()


class TestSymbolResolves:
    def test_validate_symbol_noop_lets_order_through(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """The default :meth:`BrokerInterface.validate_symbol` is a no-op
        (returns ``None``). The order proceeds to ``place_order``."""
        import asyncio

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker, email="sym-ok@tradetri.com"
            )
        )
        cred_row = asyncio.get_event_loop().run_until_complete(
            _fetch_cred_row(db_session_maker, seeded["user_id"])
        )

        broker = _make_fake_broker(funds=Decimal("500000"))
        result = asyncio.get_event_loop().run_until_complete(
            _live_place_order(
                broker=broker,
                user_id=seeded["user_id"],
                symbol="NIFTY",
                side=OrderSide.BUY,
                quantity=1,
                lot_size=1,
            )
        )

        assert result["broker_order_id"] == "LIVE-ORDER-123"
        broker.place_order.assert_awaited_once()


class TestSymbolInvalid:
    def test_invalid_symbol_aborts_before_funds_or_order(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Bad symbol → :class:`BrokerInvalidSymbolError` from ``validate_symbol``,
        and the funds + place-order calls never fire (we save HTTP round-trips)."""
        import asyncio

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker, email="sym-bad@tradetri.com"
            )
        )
        cred_row = asyncio.get_event_loop().run_until_complete(
            _fetch_cred_row(db_session_maker, seeded["user_id"])
        )

        bad_symbol_error = BrokerInvalidSymbolError(
            "Symbol 'NOTREAL' not found in scrip master",
            broker_name=BrokerName.DHAN.value,
            metadata={"symbol": "NOTREAL"},
        )
        broker = _make_fake_broker(
            funds=Decimal("500000"),
            validate_raises=bad_symbol_error,
        )

        with pytest.raises(BrokerInvalidSymbolError):
            asyncio.get_event_loop().run_until_complete(
                _live_place_order(
                    broker=broker,
                    user_id=seeded["user_id"],
                    symbol="NOTREAL",
                    side=OrderSide.BUY,
                    quantity=1,
                    lot_size=1,
                )
            )

        broker.validate_symbol.assert_awaited_once_with("NOTREAL", Exchange.NFO)
        broker.get_funds.assert_not_awaited()
        broker.place_order.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════
# Test fixture verification — pins the StaticPool fix
# ═══════════════════════════════════════════════════════════════════════


class TestDhanValidateSymbolOverride:
    async def test_dhan_override_delegates_to_get_security_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The Dhan override is a 1-line proxy to :meth:`get_security_id`.

        Direct unit assertion (rather than via the strategy executor)
        because the executor's tests use a ``MagicMock(spec=BrokerInterface)``
        that replaces ``validate_symbol`` wholesale — those tests don't
        exercise the actual Dhan implementation. This pins the override
        so a contributor who deletes it can't ship green.
        """
        from datetime import UTC, datetime

        from app.brokers.dhan import DhanBroker
        from app.schemas.broker import BrokerCredentials

        creds = BrokerCredentials(
            broker=BrokerName.DHAN,
            user_id="00000000-0000-0000-0000-000000000000",
            client_id="cid",
            api_key="ak",
            api_secret="as",
            access_token="tok",
            refresh_token=None,
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        broker = DhanBroker(creds)

        called: list[tuple[str, Exchange]] = []

        async def _fake_gsi(self: DhanBroker, symbol: str, exchange: Exchange) -> str:
            called.append((symbol, exchange))
            return "12345"

        monkeypatch.setattr(DhanBroker, "get_security_id", _fake_gsi)

        result = await broker.validate_symbol("NIFTY", Exchange.NFO)

        assert result is None  # validate_symbol returns nothing on success
        assert called == [("NIFTY", Exchange.NFO)]


class TestSeededUserVisibleAcrossSessions:
    def test_user_is_active_query_returns_seeded_value(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Pins the StaticPool + ``check_same_thread=False`` fix.

        Pre-fix behaviour: the seed's User INSERT was silently rolled
        back (aiosqlite handed out per-connection in-memory DBs), so
        request-side queries against ``users`` returned nothing — even
        though webhook_tokens / strategies / broker_credentials were
        visible. Documented in the Task #3 post-mortem.

        Post-fix: a single shared connection means the seed and the
        query operate on the same DB. This test would have failed under
        the old fixture and passes under the new one.
        """
        import asyncio

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker, email="visibility@tradetri.com"
            )
        )

        async def _read_active() -> Any:
            async with db_session_maker() as s:
                stmt = select(User.is_active).where(User.id == seeded["user_id"])
                return await s.scalar(stmt)

        is_active = asyncio.get_event_loop().run_until_complete(_read_active())
        assert is_active is True, (
            "Seeded User row not visible to a fresh session. "
            "Check that conftest's db_session_maker uses StaticPool + "
            "connect_args={'check_same_thread': False}."
        )

