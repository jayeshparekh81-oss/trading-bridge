"""Fixtures for the Phase 5 strategies CRUD endpoint tests.

These tests exercise the router in isolation against an aiosqlite
in-memory database. The full app's lifespan (redis client, scrip-master
prewarm, position/reconciliation loops) is irrelevant to strategy CRUD
and is not booted, keeping the test suite fast and side-effect-free.

Pattern lifted from ``tests/integration/conftest.py`` for the sqlite
StaticPool + named-shared-cache trick: the seed and the request handler
end up in different event loops and need to see the same in-memory DB.
"""

from __future__ import annotations

import uuid as _uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api import router as strategy_crud_router


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Per-test in-memory aiosqlite engine, single shared connection."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-strategy-api-{_uuid.uuid4().hex}"
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


async def _seed_user(
    maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    is_active: bool = True,
) -> User:
    """Insert one user and return the freshly-loaded ORM row."""
    async with maker() as session:
        user = User(email=email, password_hash="x", is_active=is_active)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def seed_user(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> User:
    """The default authenticated user used by every CRUD test."""
    return await _seed_user(db_session_maker, email="phase5-owner@tradetri.com")


@pytest.fixture
def client(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> Iterator[TestClient]:
    """FastAPI TestClient with the strategies router and overridden deps.

    A bare :class:`FastAPI` (no lifespan, no middleware) keeps the test
    surface tight: the only handlers under test are this router's. The
    auth dep is short-circuited to ``seed_user`` so each request is
    authenticated as that user; cross-user isolation tests override the
    dep again inside the test body.
    """
    app = FastAPI()
    app.include_router(strategy_crud_router)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    async def _override_user() -> User:
        return seed_user

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_active_user] = _override_user

    with TestClient(app) as c:
        yield c


def make_strategy_payload(
    *,
    name: str = "Phase 5 Test Strategy",
    strategy_id: str = "phase5_test_strategy",
) -> dict[str, Any]:
    """Build a minimal valid StrategyJSON payload for request bodies."""
    return {
        "strategy_json": {
            "id": strategy_id,
            "name": name,
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
                        "value": 100.0,
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
        }
    }
