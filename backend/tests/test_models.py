"""ORM model tests — run against an in-memory aiosqlite DB.

Goals:
    * Every model can be instantiated and persisted.
    * FK relationships cascade / set-null as declared.
    * Unique constraints raise :class:`IntegrityError` on violation.
    * Enum columns only accept values from the declared enum.

Postgres-specific features (``JSONB``, native enums, server defaults) are
exercised against Postgres in the integration suite; here we confirm the
portable ORM contract holds.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models import (
    ActorType,
    AuditLog,
    BrokerCredential,
    CopyTradingFollower,
    CopyTradingGroup,
    IdempotencyKey,
    KillSwitchConfig,
    KillSwitchEvent,
    ProcessingStatus,
    Strategy,
    Trade,
    TradeStatus,
    User,
    WebhookEvent,
    WebhookToken,
)
from app.schemas.broker import BrokerName, OrderSide, OrderType, ProductType


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory DB per test — no cross-test contamination."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _make_user(session: AsyncSession, *, email: str = "a@example.com") -> User:
    user = User(email=email, password_hash="hash", full_name="Test")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ═══════════════════════════════════════════════════════════════════════
# User
# ═══════════════════════════════════════════════════════════════════════


class TestUser:
    async def test_create_user(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        assert isinstance(user.id, uuid.UUID)
        assert user.is_active is True
        assert user.is_admin is False
        assert isinstance(user.created_at, datetime)
        assert "User(" in repr(user)

    async def test_email_unique(self, session: AsyncSession) -> None:
        await _make_user(session, email="dup@example.com")
        dup = User(email="dup@example.com", password_hash="h")
        session.add(dup)
        with pytest.raises(IntegrityError):
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════
# BrokerCredential
# ═══════════════════════════════════════════════════════════════════════


class TestBrokerCredential:
    async def test_create_and_enum(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        cred = BrokerCredential(
            user_id=user.id,
            broker_name=BrokerName.FYERS,
            client_id_enc="enc",
            api_key_enc="enc",
            api_secret_enc="enc",
        )
        session.add(cred)
        await session.commit()
        await session.refresh(cred)
        assert cred.broker_name is BrokerName.FYERS
        assert cred.is_active is True
        assert "BrokerCredential(" in repr(cred)

    async def test_cascade_on_user_delete(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        cred = BrokerCredential(
            user_id=user.id,
            broker_name=BrokerName.DHAN,
            client_id_enc="x", api_key_enc="x", api_secret_enc="x",
        )
        session.add(cred)
        await session.commit()

        await session.delete(user)
        await session.commit()
        remaining = (await session.execute(select(BrokerCredential))).scalars().all()
        assert remaining == []


# ═══════════════════════════════════════════════════════════════════════
# WebhookToken
# ═══════════════════════════════════════════════════════════════════════


class TestWebhookToken:
    async def test_token_hash_unique(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        session.add(
            WebhookToken(user_id=user.id, token_hash="abc", hmac_secret_enc="s")
        )
        await session.commit()
        session.add(
            WebhookToken(user_id=user.id, token_hash="abc", hmac_secret_enc="s")
        )
        with pytest.raises(IntegrityError):
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════
# Strategy
# ═══════════════════════════════════════════════════════════════════════


class TestStrategy:
    async def test_allowed_symbols_json(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        strat = Strategy(
            user_id=user.id,
            name="Momentum",
            allowed_symbols=["NIFTY", "BANKNIFTY"],
            max_position_size=10,
        )
        session.add(strat)
        await session.commit()
        await session.refresh(strat)
        assert strat.allowed_symbols == ["NIFTY", "BANKNIFTY"]
        assert "Strategy(" in repr(strat)


# ═══════════════════════════════════════════════════════════════════════
# Trade
# ═══════════════════════════════════════════════════════════════════════


class TestTrade:
    async def test_create_and_enums(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        cred = BrokerCredential(
            user_id=user.id, broker_name=BrokerName.FYERS,
            client_id_enc="x", api_key_enc="x", api_secret_enc="x",
        )
        session.add(cred)
        await session.commit()
        await session.refresh(cred)

        trade = Trade(
            user_id=user.id,
            broker_credential_id=cred.id,
            symbol="NIFTY25JANFUT",
            exchange="NFO",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            product_type=ProductType.INTRADAY,
            quantity=50,
            price=Decimal("21500.25"),
            status=TradeStatus.PENDING,
            raw_payload={"source": "tradingview"},
        )
        session.add(trade)
        await session.commit()
        await session.refresh(trade)

        assert trade.status is TradeStatus.PENDING
        assert trade.side is OrderSide.BUY
        assert trade.order_type is OrderType.LIMIT
        assert trade.raw_payload["source"] == "tradingview"
        assert "Trade(" in repr(trade)

    async def test_nullable_strategy_fk(self, session: AsyncSession) -> None:
        """``strategy_id`` is nullable — a trade can exist without a strategy."""
        user = await _make_user(session)
        cred = BrokerCredential(
            user_id=user.id, broker_name=BrokerName.FYERS,
            client_id_enc="x", api_key_enc="x", api_secret_enc="x",
        )
        session.add(cred)
        await session.commit()
        await session.refresh(cred)

        trade = Trade(
            user_id=user.id,
            broker_credential_id=cred.id,
            strategy_id=None,
            symbol="X",
            exchange="NSE",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
            quantity=1,
            status=TradeStatus.COMPLETE,
        )
        session.add(trade)
        await session.commit()
        await session.refresh(trade)
        assert trade.strategy_id is None


# ═══════════════════════════════════════════════════════════════════════
# KillSwitch
# ═══════════════════════════════════════════════════════════════════════


class TestKillSwitch:
    async def test_config_pk_is_user_id(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        cfg = KillSwitchConfig(
            user_id=user.id,
            max_daily_loss_inr=Decimal("5000"),
            max_daily_trades=10,
        )
        session.add(cfg)
        await session.commit()
        await session.refresh(cfg)
        assert cfg.user_id == user.id
        assert cfg.enabled is True
        assert "KillSwitchConfig(" in repr(cfg)

    async def test_event_history(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        event = KillSwitchEvent(
            user_id=user.id,
            reason="daily loss exceeded",
            daily_pnl_at_trigger=Decimal("-12000.00"),
            positions_squared_off=[{"symbol": "NIFTY", "qty": 50}],
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        assert event.positions_squared_off[0]["symbol"] == "NIFTY"
        assert "KillSwitchEvent(" in repr(event)


# ═══════════════════════════════════════════════════════════════════════
# Idempotency + WebhookEvent
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotency:
    async def test_signal_hash_unique(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        now = datetime.now(UTC)
        session.add(
            IdempotencyKey(
                user_id=user.id,
                signal_hash="deadbeef",
                expires_at=now + timedelta(minutes=1),
            )
        )
        await session.commit()

        dup = IdempotencyKey(
            user_id=user.id,
            signal_hash="deadbeef",
            expires_at=now + timedelta(minutes=1),
        )
        session.add(dup)
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_repr(self) -> None:
        key = IdempotencyKey(
            signal_hash="abc",
            expires_at=datetime.now(UTC),
        )
        assert "IdempotencyKey(" in repr(key)


class TestWebhookEvent:
    async def test_create(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        evt = WebhookEvent(
            user_id=user.id,
            source_ip="1.2.3.4",
            signature_valid=True,
            payload={"symbol": "NIFTY", "side": "buy"},
            processing_status=ProcessingStatus.RECEIVED,
        )
        session.add(evt)
        await session.commit()
        await session.refresh(evt)
        assert evt.processing_status is ProcessingStatus.RECEIVED
        assert evt.payload["side"] == "buy"
        assert "WebhookEvent(" in repr(evt)


# ═══════════════════════════════════════════════════════════════════════
# AuditLog
# ═══════════════════════════════════════════════════════════════════════


class TestAuditLog:
    async def test_create_with_metadata(self, session: AsyncSession) -> None:
        user = await _make_user(session)
        log = AuditLog(
            user_id=user.id,
            actor=ActorType.USER,
            action="credential.create",
            resource_type="broker_credential",
            resource_id="cred-uuid",
            ip_address="10.0.0.1",
            user_agent="curl/8",
            audit_metadata={"broker": "fyers"},
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        assert log.actor is ActorType.USER
        assert log.audit_metadata["broker"] == "fyers"
        assert "AuditLog(" in repr(log)

    async def test_actor_enum(self, session: AsyncSession) -> None:
        log = AuditLog(
            actor=ActorType.SYSTEM,
            action="noop",
            resource_type="none",
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        assert log.actor is ActorType.SYSTEM


# ═══════════════════════════════════════════════════════════════════════
# CopyTrading
# ═══════════════════════════════════════════════════════════════════════


class TestCopyTrading:
    async def test_group_and_follower(self, session: AsyncSession) -> None:
        master = await _make_user(session, email="master@example.com")
        follower_user = await _make_user(session, email="fol@example.com")
        fol_cred = BrokerCredential(
            user_id=follower_user.id, broker_name=BrokerName.FYERS,
            client_id_enc="x", api_key_enc="x", api_secret_enc="x",
        )
        session.add(fol_cred)
        await session.commit()
        await session.refresh(fol_cred)

        grp = CopyTradingGroup(master_user_id=master.id, name="Alpha")
        session.add(grp)
        await session.commit()
        await session.refresh(grp)

        fol = CopyTradingFollower(
            group_id=grp.id,
            follower_credential_id=fol_cred.id,
            quantity_multiplier=Decimal("0.5"),
            max_quantity=100,
        )
        session.add(fol)
        await session.commit()
        await session.refresh(fol)

        assert fol.quantity_multiplier == Decimal("0.5")
        assert "CopyTradingGroup(" in repr(grp)
        assert "CopyTradingFollower(" in repr(fol)
