"""open_position on GET /api/marketplace/subscriptions/me.

Exists so a subscriber can PAUSE then CLOSE from My Strategies. The hard rule,
held exactly like the drift-notice scoping test: customer A must NEVER see
customer B's position.

Also pinned: the owner-scoped /strategies/positions filter
(subscription_id IS NULL) is NOT relaxed — that guard protects the live-money
path and this feature works around it, not through it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_position import StrategyPosition
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router

URL = "/api/marketplace/subscriptions/me"


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-openpos-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


def _client(maker, user: User) -> TestClient:
    app = FastAPI()
    app.include_router(marketplace_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: user
    return TestClient(app)


async def _user(maker) -> User:
    async with maker() as s:
        u = User(email=f"u-{uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _sub(maker, *, user) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(), subscriber_id=user.id,
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"), execution_mode="auto",
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def _pos(maker, *, user, sub_id, symbol="BSE-AUG2026-FUT",
               qty=2, status="open"):
    async with maker() as s:
        p = StrategyPosition(
            strategy_id=uuid.uuid4(), subscription_id=sub_id, user_id=user.id,
            symbol=symbol, side="buy", total_quantity=qty, remaining_quantity=qty,
            status=status, opened_at=datetime.now(UTC),
            broker_credential_id=uuid.uuid4(),
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return p.id


def _op(body, sub_id):
    for s in body["subscriptions"]:
        if s["id"] == str(sub_id):
            return s.get("open_position")
    return None


# ═══════════════════════════════════════════════════════════════════
# Present when there is one
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_open_position_is_returned(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, user=u)
    pos_id = await _pos(db_maker, user=u, sub_id=sub_id)

    op = _op(_client(db_maker, u).get(URL).json(), sub_id)
    assert op is not None
    assert op["id"] == str(pos_id)
    assert op["symbol"] == "BSE-AUG2026-FUT"
    assert op["quantity"] == 2


@pytest.mark.asyncio
async def test_partial_position_counts_as_open(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, user=u)
    await _pos(db_maker, user=u, sub_id=sub_id, status="partial")
    assert _op(_client(db_maker, u).get(URL).json(), sub_id) is not None


# ═══════════════════════════════════════════════════════════════════
# Absent — the UI then shows NO Close button (never a disabled one)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_null_when_no_position(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, user=u)
    assert _op(_client(db_maker, u).get(URL).json(), sub_id) is None


@pytest.mark.asyncio
async def test_null_when_position_is_closed(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, user=u)
    await _pos(db_maker, user=u, sub_id=sub_id, status="closed")
    assert _op(_client(db_maker, u).get(URL).json(), sub_id) is None


# ═══════════════════════════════════════════════════════════════════
# ⚠️ SCOPING — A must NEVER see B's position
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_customer_never_sees_another_customers_position(db_maker):
    alice = await _user(db_maker)
    bob = await _user(db_maker)
    alice_sub = await _sub(db_maker, user=alice)
    bob_sub = await _sub(db_maker, user=bob)
    await _pos(db_maker, user=bob, sub_id=bob_sub, symbol="BOB-SECRET-FUT")

    body = _client(db_maker, alice).get(URL).json()

    ids = {s["id"] for s in body["subscriptions"]}
    assert ids == {str(alice_sub)}                 # only her own row
    assert _op(body, alice_sub) is None            # and no position
    assert "BOB-SECRET-FUT" not in str(body)       # nowhere in the payload

    # …and Bob still sees his own.
    bob_body = _client(db_maker, bob).get(URL).json()
    assert _op(bob_body, bob_sub)["symbol"] == "BOB-SECRET-FUT"


@pytest.mark.asyncio
async def test_position_is_matched_to_the_right_subscription(db_maker):
    """Two subscriptions of the SAME user must not swap positions."""
    u = await _user(db_maker)
    s1 = await _sub(db_maker, user=u)
    s2 = await _sub(db_maker, user=u)
    p1 = await _pos(db_maker, user=u, sub_id=s1, symbol="ONE-FUT")
    p2 = await _pos(db_maker, user=u, sub_id=s2, symbol="TWO-FUT")

    body = _client(db_maker, u).get(URL).json()
    assert _op(body, s1)["id"] == str(p1)
    assert _op(body, s1)["symbol"] == "ONE-FUT"
    assert _op(body, s2)["id"] == str(p2)
    assert _op(body, s2)["symbol"] == "TWO-FUT"


# ═══════════════════════════════════════════════════════════════════
# The owner-scope guard must stay untouched
# ═══════════════════════════════════════════════════════════════════


def test_owner_positions_filter_is_not_relaxed():
    """/strategies/positions must still exclude subscriber rows."""
    import inspect

    from app.api import strategy_positions as mod

    src = inspect.getsource(mod)
    assert "subscription_id.is_(None)" in src, (
        "the owner-scope filter guards the live-money path and must not be "
        "relaxed for UI convenience"
    )


@pytest.mark.asyncio
async def test_field_is_additive_and_optional(db_maker):
    u = await _user(db_maker)
    await _sub(db_maker, user=u)
    row = _client(db_maker, u).get(URL).json()["subscriptions"][0]
    for f in ("id", "listing_id", "status", "amount_paid_inr"):
        assert f in row
    assert row["open_position"] is None
