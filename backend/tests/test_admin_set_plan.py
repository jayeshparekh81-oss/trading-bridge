"""Phase 2 Billing B3.1 — admin set-plan endpoint.

Pins the contract for ``PUT /api/admin/users/{user_id}/plan``:

    * Sets ONLY the billing triple (plan_status / active_plan_id /
      plan_expires_at) — NEVER role / is_admin / live_trading_enabled
      (billing ⟂ RBAC).
    * Validates the plan_status vocabulary (422) and the active_plan_id FK
      (404); 404 on unknown user; 403 for non-admins.
    * Writes an append-only AuditLog row (actor=admin, action=
      'admin.set_user_plan') with before/after metadata.
    * PUT/replace semantics: omitted optional fields are cleared.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.admin import router as admin_router
from app.api.deps import get_current_active_user, get_current_admin
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.subscription_plan import SubscriptionPlan
from app.db.models.user import User
from app.db.session import get_session

_FUTURE_ISO = "2099-01-01T00:00:00+00:00"
_PAST_ISO = "2000-01-01T00:00:00+00:00"


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-setplan-{uuid.uuid4().hex}"
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


async def _seed(
    maker: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed one free 'user'-role target + one 'pro' plan. Returns their ids."""
    async with maker() as s:
        user = User(
            email="target@x",
            password_hash="p",
            is_active=True,
            is_admin=False,
            role="user",
            live_trading_enabled=False,
        )
        plan = SubscriptionPlan(name="Pro", tier="pro")
        s.add_all([user, plan])
        await s.commit()
        return user.id, plan.id


def _make_client(
    maker: async_sessionmaker[AsyncSession],
    *,
    admin: bool = True,
) -> TestClient:
    app = FastAPI()
    app.include_router(admin_router)

    actor = User(
        email="admin@x",
        password_hash="p",
        is_active=True,
        is_admin=admin,
        role="admin" if admin else "user",
    )
    actor.id = uuid.uuid4()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    if admin:
        # Happy/validation path: impersonate an admin directly.
        async def _override_admin() -> User:
            return actor

        app.dependency_overrides[get_current_admin] = _override_admin
    else:
        # 403 path: feed a non-admin to the REAL get_current_admin chain.
        async def _override_active() -> User:
            return actor

        app.dependency_overrides[get_current_active_user] = _override_active
    return TestClient(app)


# ── 1. Happy path: sets billing triple, leaves RBAC/live untouched ────


@pytest.mark.asyncio
async def test_set_plan_active_updates_only_billing_fields(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plan_id = await _seed(db_maker)
    with _make_client(db_maker) as client:
        resp = client.put(
            f"/api/admin/users/{user_id}/plan",
            json={
                "plan_status": "active",
                "active_plan_id": str(plan_id),
                "plan_expires_at": _FUTURE_ISO,
            },
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan_status"] == "active"

    async with db_maker() as s:
        u = await s.get(User, user_id)
        assert u is not None
        # billing triple set
        assert u.plan_status == "active"
        assert u.active_plan_id == plan_id
        assert u.plan_expires_at is not None
        # RBAC / live-trading UNTOUCHED
        assert u.role == "user"
        assert u.is_admin is False
        assert u.live_trading_enabled is False
        # audit row written
        log = (
            await s.execute(select(AuditLog).where(AuditLog.action == "admin.set_user_plan"))
        ).scalar_one_or_none()
        assert log is not None
        assert str(log.resource_id) == str(user_id)
        assert log.audit_metadata["after"]["plan_status"] == "active"


# ── 2. PUT/replace: 'none' clears plan_id + expiry ────────────────────


@pytest.mark.asyncio
async def test_set_plan_none_clears_plan_id_and_expiry(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plan_id = await _seed(db_maker)
    with _make_client(db_maker) as client:
        # first make it active...
        client.put(
            f"/api/admin/users/{user_id}/plan",
            json={
                "plan_status": "active",
                "active_plan_id": str(plan_id),
                "plan_expires_at": _FUTURE_ISO,
            },
        )
        # ...then downgrade to free with only plan_status
        resp = client.put(
            f"/api/admin/users/{user_id}/plan",
            json={"plan_status": "none"},
        )
    assert resp.status_code == 200, resp.text
    async with db_maker() as s:
        u = await s.get(User, user_id)
        assert u is not None
        assert u.plan_status == "none"
        assert u.active_plan_id is None
        assert u.plan_expires_at is None


# ── 3. Validation + guards ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bad_plan_status_is_422(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_id, _ = await _seed(db_maker)
    with _make_client(db_maker) as client:
        resp = client.put(
            f"/api/admin/users/{user_id}/plan",
            json={"plan_status": "premium"},  # not in the locked vocabulary
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_active_requires_plan_id_and_future_expiry_else_422(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """plan_status='active' must carry a plan id AND a future expiry."""
    user_id, plan_id = await _seed(db_maker)
    bad_bodies = [
        {"plan_status": "active", "plan_expires_at": _FUTURE_ISO},  # no plan_id
        {"plan_status": "active", "active_plan_id": str(plan_id)},  # no expiry
        {  # past expiry
            "plan_status": "active",
            "active_plan_id": str(plan_id),
            "plan_expires_at": _PAST_ISO,
        },
    ]
    with _make_client(db_maker) as client:
        for body in bad_bodies:
            resp = client.put(f"/api/admin/users/{user_id}/plan", json=body)
            assert resp.status_code == 422, (body, resp.text)


@pytest.mark.asyncio
async def test_unknown_plan_id_is_404(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_id, _ = await _seed(db_maker)
    with _make_client(db_maker) as client:
        resp = client.put(
            f"/api/admin/users/{user_id}/plan",
            # valid shape (plan_id + future expiry) so it clears the schema
            # validator and reaches the endpoint FK existence check → 404.
            json={
                "plan_status": "active",
                "active_plan_id": str(uuid.uuid4()),
                "plan_expires_at": _FUTURE_ISO,
            },
        )
    assert resp.status_code == 404
    assert "plan" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unknown_user_is_404(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(db_maker)
    with _make_client(db_maker) as client:
        # valid body (free tier needs no plan_id/expiry) so the request
        # reaches the user lookup → 404.
        resp = client.put(
            f"/api/admin/users/{uuid.uuid4()}/plan",
            json={"plan_status": "none"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_is_403(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user_id, _ = await _seed(db_maker)
    with _make_client(db_maker, admin=False) as client:
        # valid body so the only failure is the role gate (avoids 422/403
        # ordering ambiguity).
        resp = client.put(
            f"/api/admin/users/{user_id}/plan",
            json={"plan_status": "none"},
        )
    assert resp.status_code == 403
