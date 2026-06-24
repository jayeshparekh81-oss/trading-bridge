"""M3 backend reads/writes — ``GET /api/billing/me`` + per-subscriber settings.

Self-contained (in-memory aiosqlite + dependency_overrides), mirroring the
marketplace CRUD test harness. Covers:
    * billing/me reflects the entitlement (plan_status / is_active)
    * settings PATCH validates the even / 2-20 sizing rule (422 on odd / OOB)
    * settings PATCH is guarded on THIS branch — applied=False,
      pending_fanout_merge=True (columns land with the fan-out merge)
    * settings GET defaults to paper-only
    * a non-owned subscription 404s
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.billing import router as billing_router
from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-m3-{uuid.uuid4().hex}"
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


def _client(maker: async_sessionmaker[AsyncSession], user: User) -> TestClient:
    app = FastAPI()
    app.include_router(billing_router)
    app.include_router(marketplace_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: user
    return TestClient(app)


async def _seed_user(maker: async_sessionmaker[AsyncSession], **kw: object) -> User:
    async with maker() as s:
        u = User(
            email=f"m3-{uuid.uuid4().hex}@t.com",
            password_hash="x",
            is_active=True,
            **kw,
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _seed_sub(
    maker: async_sessionmaker[AsyncSession], subscriber_id: uuid.UUID
) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(),
            subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC),
            status="active",
            amount_paid_inr=Decimal("499"),
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


# ── billing/me ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_billing_me_reflects_active_entitlement(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(
        db_maker,
        plan_status="active",
        plan_expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    with _client(db_maker, user) as client:
        r = client.get("/api/billing/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan_status"] == "active"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_billing_me_free_user_is_inactive(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker, plan_status="none")
    with _client(db_maker, user) as client:
        r = client.get("/api/billing/me")
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


# ── subscription settings ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_settings_patch_rejects_odd_lots(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 3},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_settings_patch_rejects_below_minimum(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 1},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_settings_patch_rejects_bad_execution_mode(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"execution_mode": "banana"},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_settings_patch_even_lots_validated_but_not_persisted(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Even lots accepted; on THIS branch the columns are absent so the write is
    validated-but-not-persisted (applied=False, pending_fanout_merge=True)."""
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 4, "execution_mode": "auto", "is_paper": False},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lots_override"] == 4
    assert body["execution_mode"] == "auto"
    assert body["is_paper"] is False
    assert body["applied"] is False
    assert body["pending_fanout_merge"] is True


@pytest.mark.asyncio
async def test_settings_get_defaults_to_paper(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.get(f"/api/marketplace/subscriptions/{sub_id}/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["execution_mode"] == "paper"
    assert body["is_paper"] is True
    assert body["lots_override"] is None
    assert body["applied"] is False


@pytest.mark.asyncio
async def test_settings_patch_on_unowned_subscription_404s(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    owner = await _seed_user(db_maker)
    other = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, owner.id)
    with _client(db_maker, other) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 4},
        )
    assert r.status_code == 404, r.text
