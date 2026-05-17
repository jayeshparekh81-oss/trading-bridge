"""Fixtures for backtest extension tests.

Provides an in-memory aiosqlite session maker that creates ONLY the
backtest_extension tables + their dependencies (users, strategies) so
the test suite stays fast and side-effect-free.

JSONB → JSON compiler shim: ORM uses Postgres JSONB; sqlite can't
compile it natively. The @compiles(JSONB, "sqlite") shim routes
JSONB → vanilla JSON on the sqlite path. No effect on the Postgres
runtime path.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.backtest_extension.models import (
    BacktestMetrics,  # noqa: F401  — register table
    BacktestRun,
    BacktestTrade,  # noqa: F401  — register table
)
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Per-test in-memory aiosqlite engine with single shared connection.

    StaticPool + shared-cache URI pin the engine to one connection so
    seed INSERTs and SELECTs in the same test see the same DB.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:bt-ext-test-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def seed_user(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> User:
    """The default authenticated user for every test."""
    async with db_session_maker() as session:
        user = User(
            email=f"bt-ext-{uuid.uuid4().hex[:8]}@tradetri.test",
            password_hash="x",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def seed_strategy(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> Strategy:
    """Owner-scoped Strategy row with a valid StrategyJSON payload.

    Mirrors the minimal valid shape from
    ``tests/strategy_engine/api/conftest.make_strategy_payload``.
    """
    async with db_session_maker() as session:
        strategy = Strategy(
            user_id=seed_user.id,
            name="Backtest test strategy",
            is_active=True,
            strategy_json={
                "id": "bt_ext_test",
                "name": "Backtest test strategy",
                "mode": "expert",
                "indicators": [
                    {"id": "ema_20", "type": "ema", "params": {"period": 20}},
                ],
                "entry": {
                    "side": "BUY",
                    "operator": "AND",
                    "conditions": [
                        {
                            "type": "indicator",
                            "left": "ema_20",
                            "op": ">",
                            "value": 21000.0,
                        }
                    ],
                },
                "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
                "risk": {},
                "execution": {
                    "mode": "backtest",
                    "orderType": "MARKET",
                    "productType": "INTRADAY",
                },
            },
        )
        session.add(strategy)
        await session.commit()
        await session.refresh(strategy)
        return strategy


def make_request_payload(*, symbol: str = "NIFTY") -> dict[str, object]:
    """Canonical sample BacktestEnqueueRequest payload as a dict."""
    return {
        "symbol": symbol,
        "timeframe": "5m",
        "start": datetime(2026, 3, 17, 3, 45, tzinfo=UTC).isoformat(),
        "end": datetime(2026, 5, 17, 10, 0, tzinfo=UTC).isoformat(),
        "initial_capital": 100000.0,
        "quantity": 1.0,
        "cost_settings": {
            "fixed_cost": 0.0,
            "percent_cost": 0.0,
            "slippage_percent": 0.0,
            "spread_percent": 0.0,
        },
        "ambiguity_mode": "conservative",
    }
