"""Shared fixtures for live-orders tests.

Mirrors the kill_switch_service test pattern: SQLite in-memory engine
with ``Base.metadata.create_all`` plus a ``fakeredis`` client that
monkey-patches ``redis_client.get_redis``. Helpers seed the rows the
SafetyChain reads (paper sessions, cached scores, broker credentials,
per-user live-trading flag) so each test stays focused on one
condition.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core import redis_client
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.schemas.broker import BrokerName
from app.strategy_engine.feature_flags import reset_all_flags, set_flag
from app.strategy_engine.feature_flags.constants import ENV_PREFIX
from app.strategy_engine.paper_trading import store as paper_store


@pytest.fixture(autouse=True)
def _isolated_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drop every env override + runtime override before each test.

    Also forces ``STRATEGY_PAPER_MODE=false`` so the live-orders flow
    is exercised under its live-mode contract. Safety fix #3 added a
    paper-mode short-circuit at the top of ``place_live_order`` that
    raises before the SafetyChain runs — the paper-mode behaviour is
    covered explicitly in the dedicated ``TestPaperModeGate`` class
    inside ``test_order_router.py``.
    """
    import os

    for name, _ in list(os.environ.items()):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name, raising=False)
    reset_all_flags()
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest_asyncio.fixture
async def redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    """In-memory Redis substitute for the SafetyChain's kill-switch read."""
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def user(db: AsyncSession) -> User:
    """User with live trading enabled (per-user flag on by default).

    Tests that want the per-user flag off override
    ``live_trading_enabled`` directly.
    """
    u = User(
        email="safety@x",
        password_hash="p",
        is_active=True,
        live_trading_enabled=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def strategy(db: AsyncSession, user: User) -> Strategy:
    s = Strategy(user_id=user.id, name="safety-test", is_active=True)
    db.add(s)
    await db.flush()
    return s


@pytest_asyncio.fixture
async def all_passing(
    db: AsyncSession,
    user: User,
    strategy: Strategy,
    redis: fake_aioredis.FakeRedis,
) -> tuple[User, Strategy]:
    """Seed every dependency so all 7 checks pass.

        * Kill switch ACTIVE (= "not tripped").
        * 7 completed paper sessions.
        * Fresh cached scores: trust=80, truth=70.
        * Per-user + global live trading flags ON.
        * One active Dhan broker credential.
        * Risk engine pre-check is fail-open by design.
    """
    # 1. Kill switch — leave the redis key unset; default reader returns ACTIVE.
    # 2. Seven completed paper sessions, distinct days.
    base = date(2026, 5, 1)
    for i in range(7):
        row = await paper_store.create_session(
            db,
            user_id=user.id,
            strategy_id=strategy.id,
            engine_strategy_id="eng",
            session_date=base + timedelta(days=i),
        )
        await paper_store.complete_session(
            db,
            session_id=row.id,
            total_trades=1,
            total_pnl=Decimal("10"),
        )
    # 3. Cached scores — fresh.
    strategy.last_trust_score = Decimal("80.00")
    strategy.last_truth_score = Decimal("70.00")
    strategy.last_scores_at = datetime.now(UTC) - timedelta(hours=1)
    # 4. Live trading global flag.
    set_flag("LIVE_TRADING_ENABLED", True)
    # 5. Active Dhan credential.
    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SEC"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred)
    await db.flush()
    return user, strategy


def fresh_uuid() -> uuid.UUID:
    return uuid.uuid4()
