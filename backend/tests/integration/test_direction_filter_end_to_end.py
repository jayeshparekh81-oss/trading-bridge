"""A saved direction actually reaches the fan-out gate.

The two halves — a PATCH that persists and a gate that reads — were built in
separate commits, and each has its own unit tests. This file is the one that
would catch them being wired to different things: it saves through the real
endpoint, reads the row back the way the fan-out builds its subscriber rows, and
puts that value through the real gate.

The scenario, exactly as specified: set short-only, then
  * a LONG entry is SKIPPED, and
  * an EXIT is still DELIVERED.

That second half is the one that matters. A filter that also blocked exits would
strand a subscriber in a position they could not close.
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
from app.db.models.user import User
from app.db.session import get_session
from app.services.marketplace_fanout import _direction_allows
from app.strategy_engine.api.marketplace import router as marketplace_router


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-dir-{uuid.uuid4().hex}"
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


async def _sub(maker, *, subscriber_id) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(), subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"),
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def _stored_direction(maker, sub_id) -> str:
    """Read the column back the way the fan-out's subscriber query does."""
    async with maker() as s:
        row = await s.get(MarketplaceSubscription, sub_id)
        return row.direction_filter


# ═══════════════════════════════════════════════════════════════════════
# THE END-TO-END SCENARIO
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_saved_short_only_skips_a_long_entry_and_still_delivers_exits(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)

    # 1. the customer saves SHORT-ONLY through the real endpoint
    res = _client(db_maker, u).patch(
        f"/api/marketplace/subscriptions/{sub_id}/settings",
        json={"direction_filter": "short"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["direction_filter"] == "short"
    assert res.json()["applied"] is True

    # 2. it is genuinely PERSISTED, not just echoed back
    stored = await _stored_direction(db_maker, sub_id)
    assert stored == "short"

    # 3. that stored value, through the real gate:
    #    a LONG entry is skipped ...
    assert _direction_allows(stored, "buy") is False
    #    ... a SHORT entry is taken ...
    assert _direction_allows(stored, "sell") is True

    # 4. ... and an EXIT is DELIVERED regardless. The gate is entry-only: the
    #    fan-out calls it solely when entry_side is not None. A subscriber who
    #    is long and switches to short-only must still be able to close.
    src_guard = "if entry_side is not None and not _direction_allows("
    from pathlib import Path
    fanout = (
        Path(__file__).resolve().parents[2] / "app" / "services" / "marketplace_fanout.py"
    ).read_text(encoding="utf-8")
    assert src_guard in fanout, (
        "the gate lost its entry-only guard — a short-only subscriber holding a "
        "long would now be unable to exit it"
    )


@pytest.mark.asyncio
async def test_long_only_is_the_mirror_image(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)

    _client(db_maker, u).patch(
        f"/api/marketplace/subscriptions/{sub_id}/settings",
        json={"direction_filter": "long"},
    )
    stored = await _stored_direction(db_maker, sub_id)

    assert stored == "long"
    assert _direction_allows(stored, "sell") is False
    assert _direction_allows(stored, "buy") is True


@pytest.mark.asyncio
async def test_both_is_the_default_and_filters_nothing(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)

    body = _client(db_maker, u).get(
        f"/api/marketplace/subscriptions/{sub_id}/settings"
    ).json()

    assert body["direction_filter"] == "all"
    assert _direction_allows("all", "buy") is True
    assert _direction_allows("all", "sell") is True


# ═══════════════════════════════════════════════════════════════════════
# The PATCH itself
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_partial_patch_does_not_reset_the_direction(db_maker):
    """Saving lots must not silently widen a customer back to both sides."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    c = _client(db_maker, u)

    c.patch(f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"direction_filter": "short"})
    res = c.patch(f"/api/marketplace/subscriptions/{sub_id}/settings",
                  json={"lots_override": 4})

    assert res.json()["direction_filter"] == "short"
    assert await _stored_direction(db_maker, sub_id) == "short"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["both", "LONG", "buy", "", "all,long", 1])
async def test_invalid_directions_are_rejected_by_the_schema(db_maker, bad):
    """The API is the narrow gate: only the three CHECK-constrained values get
    in, so the fan-out's fail-open branch stays unreachable in practice."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)

    res = _client(db_maker, u).patch(
        f"/api/marketplace/subscriptions/{sub_id}/settings",
        json={"direction_filter": bad},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_another_customer_cannot_change_my_direction(db_maker):
    a = await _user(db_maker)
    b = await _user(db_maker)
    a_sub = await _sub(db_maker, subscriber_id=a.id)

    res = _client(db_maker, b).patch(
        f"/api/marketplace/subscriptions/{a_sub}/settings",
        json={"direction_filter": "short"},
    )

    assert res.status_code == 404
    assert await _stored_direction(db_maker, a_sub) == "all"
