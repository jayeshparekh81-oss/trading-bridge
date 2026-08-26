"""Drift notice on GET /api/marketplace/subscriptions/me.

Derived from audit_logs — no column, no migration.

The hard one: the query is USER-SCOPED, and a customer must NEVER see another
customer's drift notice. That is asserted explicitly below.
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

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router

DRIFT_ACTION = "marketplace.subscription.auto_to_manual.broker_drift"
USER_CHANGE_ACTION = "marketplace.subscription.execution_mode.user_change"
RESOURCE_TYPE = "marketplace_subscription"


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-notice-{uuid.uuid4().hex}"
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


async def _sub(maker, *, subscriber_id, execution_mode="offline") -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(), subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"), execution_mode=execution_mode,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def _audit(maker, *, user_id, sub_id, action, when=None, meta=None):
    async with maker() as s:
        row = AuditLog(
            user_id=user_id,
            actor=ActorType.SYSTEM if action == DRIFT_ACTION else ActorType.USER,
            action=action, resource_type=RESOURCE_TYPE, resource_id=str(sub_id),
            audit_metadata=meta or {},
        )
        if when is not None:
            row.created_at = when
        s.add(row)
        await s.commit()


def _notice_for(body, sub_id):
    for s in body["subscriptions"]:
        if s["id"] == str(sub_id):
            return s.get("drift_notice")
    return None


# ═══════════════════════════════════════════════════════════════════════
# Present after a flip
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_notice_present_after_a_flip(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _audit(
        db_maker, user_id=u.id, sub_id=sub_id, action=DRIFT_ACTION,
        meta={"symbol": "BSE-AUG2026-FUT", "reason": "broker_flat"},
    )

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    notice = _notice_for(body, sub_id)

    assert notice is not None
    assert notice["symbol"] == "BSE-AUG2026-FUT"
    assert notice["reason"] == "broker_flat"
    assert notice["flipped_at"]


@pytest.mark.asyncio
async def test_partial_reason_is_carried(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _audit(
        db_maker, user_id=u.id, sub_id=sub_id, action=DRIFT_ACTION,
        meta={"symbol": "CDSL-JUL2026-FUT", "reason": "broker_partial"},
    )
    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    assert _notice_for(body, sub_id)["reason"] == "broker_partial"


# ═══════════════════════════════════════════════════════════════════════
# Absent when there was no flip
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_absent_when_no_flip(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    assert _notice_for(body, sub_id) is None


@pytest.mark.asyncio
async def test_unrelated_audit_actions_do_not_produce_a_notice(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _audit(db_maker, user_id=u.id, sub_id=sub_id, action="some.other.action")
    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    assert _notice_for(body, sub_id) is None


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ SCOPING — a customer must NEVER see another customer's drift
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_customer_never_sees_another_customers_drift_notice(db_maker):
    alice = await _user(db_maker)
    bob = await _user(db_maker)
    alice_sub = await _sub(db_maker, subscriber_id=alice.id)
    bob_sub = await _sub(db_maker, subscriber_id=bob.id)

    # ONLY Bob drifted.
    await _audit(
        db_maker, user_id=bob.id, sub_id=bob_sub, action=DRIFT_ACTION,
        meta={"symbol": "BOB-SECRET-FUT", "reason": "broker_flat"},
    )

    alice_body = _client(db_maker, alice).get(
        "/api/marketplace/subscriptions/me").json()

    # Alice sees only her own subscription, and NO notice.
    ids = {s["id"] for s in alice_body["subscriptions"]}
    assert ids == {str(alice_sub)}
    assert _notice_for(alice_body, alice_sub) is None
    # Bob's symbol must not appear anywhere in Alice's payload.
    assert "BOB-SECRET-FUT" not in str(alice_body)

    # …and Bob still sees his own.
    bob_body = _client(db_maker, bob).get(
        "/api/marketplace/subscriptions/me").json()
    assert _notice_for(bob_body, bob_sub)["symbol"] == "BOB-SECRET-FUT"


@pytest.mark.asyncio
async def test_audit_row_for_another_users_subscription_is_not_leaked(db_maker):
    """Even a mislabelled audit row must not cross the user boundary."""
    alice = await _user(db_maker)
    bob = await _user(db_maker)
    alice_sub = await _sub(db_maker, subscriber_id=alice.id)

    # An audit row referencing ALICE's subscription but owned by BOB.
    await _audit(
        db_maker, user_id=bob.id, sub_id=alice_sub, action=DRIFT_ACTION,
        meta={"symbol": "LEAK-FUT", "reason": "broker_flat"},
    )

    body = _client(db_maker, alice).get("/api/marketplace/subscriptions/me").json()
    # Alice's own query is user-scoped, so this row is invisible to her.
    assert _notice_for(body, alice_sub) is None
    assert "LEAK-FUT" not in str(body)


# ═══════════════════════════════════════════════════════════════════════
# Self-clearing on re-enable
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_notice_clears_after_the_customer_changes_mode(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    now = datetime.now(UTC)

    await _audit(
        db_maker, user_id=u.id, sub_id=sub_id, action=DRIFT_ACTION,
        when=now - timedelta(hours=2),
        meta={"symbol": "BSE-AUG2026-FUT", "reason": "broker_flat"},
    )
    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    assert _notice_for(body, sub_id) is not None      # showing

    # Customer re-enables AUTO (recorded by the settings endpoint).
    await _audit(
        db_maker, user_id=u.id, sub_id=sub_id, action=USER_CHANGE_ACTION,
        when=now - timedelta(minutes=5), meta={"from": "offline", "to": "auto"},
    )
    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    assert _notice_for(body, sub_id) is None          # cleared


@pytest.mark.asyncio
async def test_a_newer_flip_after_a_user_change_shows_again(db_maker):
    """Re-enabled, then drifted again → the customer must be told again."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    now = datetime.now(UTC)

    await _audit(db_maker, user_id=u.id, sub_id=sub_id, action=DRIFT_ACTION,
                 when=now - timedelta(days=2), meta={"reason": "broker_flat"})
    await _audit(db_maker, user_id=u.id, sub_id=sub_id, action=USER_CHANGE_ACTION,
                 when=now - timedelta(days=1), meta={"from": "offline", "to": "auto"})
    await _audit(db_maker, user_id=u.id, sub_id=sub_id, action=DRIFT_ACTION,
                 when=now - timedelta(minutes=1),
                 meta={"symbol": "NEW-FUT", "reason": "broker_partial"})

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    notice = _notice_for(body, sub_id)
    assert notice is not None
    assert notice["symbol"] == "NEW-FUT"


@pytest.mark.asyncio
async def test_older_user_change_does_not_clear_a_newer_flip(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    now = datetime.now(UTC)

    await _audit(db_maker, user_id=u.id, sub_id=sub_id, action=USER_CHANGE_ACTION,
                 when=now - timedelta(days=3), meta={"from": "offline", "to": "auto"})
    await _audit(db_maker, user_id=u.id, sub_id=sub_id, action=DRIFT_ACTION,
                 when=now - timedelta(hours=1), meta={"reason": "broker_flat"})

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    assert _notice_for(body, sub_id) is not None


# ═══════════════════════════════════════════════════════════════════════
# Backwards compatibility
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_field_is_additive_and_optional(db_maker):
    """Existing consumers must be unaffected — every other field intact."""
    u = await _user(db_maker)
    await _sub(db_maker, subscriber_id=u.id)
    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    row = body["subscriptions"][0]
    for field in ("id", "listing_id", "subscriber_id", "subscribed_at",
                  "status", "amount_paid_inr"):
        assert field in row
    assert row["drift_notice"] is None
