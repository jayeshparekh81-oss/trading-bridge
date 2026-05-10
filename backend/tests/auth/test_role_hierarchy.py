"""Phase 2 RBAC — role-hierarchy predicates + dependency factories.

Pins the locked five-tier vocabulary, the inheritance rules
(``user ⊂ pro_user ⊂ creator``; admin track parallel; ``super_admin``
covers everything), and the matching FastAPI dependency factories.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

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
from app.api.role_demo import router as role_demo_router
from app.auth.roles import (
    PHASE2_ROLES,
    ROLE_ADMIN,
    ROLE_CREATOR,
    ROLE_PRO_USER,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    USER_ROLES,
    is_admin,
    is_admin_or_above,
    is_creator_or_above,
    is_pro_or_above,
    is_super_admin,
)
from app.db.base import Base
from app.db.models.user import User

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-rbac2-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    yield maker
    await engine.dispose()


def _user_with_role(role: str) -> User:
    return User(
        email=f"{role}@x",
        password_hash="p",
        is_active=True,
        role=role,
    )


def _client_for(
    user: User,
    db_maker: async_sessionmaker[AsyncSession],
) -> TestClient:
    """Tiny app with role_demo router + auth override — used as the
    smoke-test surface for each tier dependency."""
    app = FastAPI()
    app.include_router(role_demo_router)

    async def _override_user() -> User:
        return user

    from app.db.session import get_session

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    app.dependency_overrides[get_current_active_user] = _override_user
    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


# ── Vocabulary lock ───────────────────────────────────────────────────


def test_phase2_locked_vocabulary() -> None:
    """The locked five-tier set + ordering. A stray addition or
    rename trips here so role values stay in sync with Migration 014."""
    assert USER_ROLES == (
        ROLE_USER,
        ROLE_PRO_USER,
        ROLE_CREATOR,
        ROLE_ADMIN,
        ROLE_SUPER_ADMIN,
    )
    assert frozenset(USER_ROLES) == PHASE2_ROLES
    assert ROLE_USER == "user"
    assert ROLE_PRO_USER == "pro_user"
    assert ROLE_CREATOR == "creator"
    assert ROLE_ADMIN == "admin"
    assert ROLE_SUPER_ADMIN == "super_admin"


# ── Hierarchy predicates ─────────────────────────────────────────────


def test_is_pro_or_above_covers_paid_track_plus_admin_track() -> None:
    assert is_pro_or_above(_user_with_role(ROLE_USER)) is False
    assert is_pro_or_above(_user_with_role(ROLE_PRO_USER)) is True
    assert is_pro_or_above(_user_with_role(ROLE_CREATOR)) is True
    assert is_pro_or_above(_user_with_role(ROLE_ADMIN)) is True
    assert is_pro_or_above(_user_with_role(ROLE_SUPER_ADMIN)) is True


def test_is_creator_or_above_covers_creator_plus_admin_track() -> None:
    assert is_creator_or_above(_user_with_role(ROLE_USER)) is False
    assert is_creator_or_above(_user_with_role(ROLE_PRO_USER)) is False
    assert is_creator_or_above(_user_with_role(ROLE_CREATOR)) is True
    assert is_creator_or_above(_user_with_role(ROLE_ADMIN)) is True
    assert is_creator_or_above(_user_with_role(ROLE_SUPER_ADMIN)) is True


def test_is_admin_or_above_covers_admin_track_only() -> None:
    assert is_admin_or_above(_user_with_role(ROLE_USER)) is False
    assert is_admin_or_above(_user_with_role(ROLE_PRO_USER)) is False
    assert is_admin_or_above(_user_with_role(ROLE_CREATOR)) is False
    assert is_admin_or_above(_user_with_role(ROLE_ADMIN)) is True
    assert is_admin_or_above(_user_with_role(ROLE_SUPER_ADMIN)) is True


def test_is_super_admin_only_super_admin() -> None:
    for role in USER_ROLES:
        expected = role == ROLE_SUPER_ADMIN
        assert is_super_admin(_user_with_role(role)) is expected


# ── Backwards compat: Phase 1 is_admin still works ───────────────────


def test_phase1_is_admin_helper_still_reads_role() -> None:
    """The Phase 1 ``is_admin(user)`` predicate continues to read
    ``role == 'admin'`` — Phase 2's expanded vocabulary doesn't
    accidentally make ``super_admin`` count as ``admin`` or vice
    versa under the legacy helper. Only ``role='admin'`` returns
    True; super_admin is its own thing."""
    assert is_admin(_user_with_role(ROLE_ADMIN)) is True
    assert is_admin(_user_with_role(ROLE_SUPER_ADMIN)) is False
    assert is_admin(_user_with_role(ROLE_USER)) is False


# ── User-model @property accessors mirror the helpers ────────────────


def test_user_model_properties_match_helpers() -> None:
    """The User model's three new ``@property`` accessors return the
    same value as the function helpers — pin so the two surfaces
    stay in sync if either is refactored."""
    for role in USER_ROLES:
        u = _user_with_role(role)
        assert u.is_pro_or_above == is_pro_or_above(u)
        assert u.is_creator_or_above == is_creator_or_above(u)
        assert u.is_super_admin == is_super_admin(u)


# ── Dependency factories — through the role_demo endpoints ───────────


@pytest.mark.asyncio
async def test_pro_endpoint_blocks_regular_user(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = _user_with_role(ROLE_USER)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/pro/feature")
    assert resp.status_code == 403
    assert "pro_user_or_above" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_pro_endpoint_allows_pro_user(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = _user_with_role(ROLE_PRO_USER)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/pro/feature")
    assert resp.status_code == 200
    assert resp.json()["your_role"] == ROLE_PRO_USER


@pytest.mark.asyncio
async def test_creator_endpoint_blocks_pro_user(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """``pro_user`` is below ``creator`` on the write track — the
    creator endpoint must reject."""
    user = _user_with_role(ROLE_PRO_USER)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/creator/publish")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_creator_endpoint_allows_creator(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = _user_with_role(ROLE_CREATOR)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/creator/publish")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_endpoint_blocks_admin(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Plain ``admin`` is NOT enough — super_admin is strict."""
    user = _user_with_role(ROLE_ADMIN)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/super-admin/system")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_endpoint_allows_super_admin(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = _user_with_role(ROLE_SUPER_ADMIN)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/super-admin/system")
    assert resp.status_code == 200
    assert resp.json()["tier_required"] == "super_admin"


@pytest.mark.asyncio
async def test_super_admin_can_access_creator_endpoint(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Hierarchy: ``super_admin`` covers the creator gate too. Pin
    the cross-track inclusion so a future refactor that splits the
    tracks doesn't silently break the "super_admin sees everything"
    contract."""
    user = _user_with_role(ROLE_SUPER_ADMIN)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/creator/publish")
    assert resp.status_code == 200


# ── Hinglish error message contract ──────────────────────────────────


@pytest.mark.asyncio
async def test_403_responses_carry_hinglish_detail(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Every tier's failure surfaces the same Hinglish shape so the
    frontend can render the toast verbatim without translation."""
    user = _user_with_role(ROLE_USER)
    with _client_for(user, db_maker) as client:
        for path in (
            "/api/roles/pro/feature",
            "/api/roles/creator/publish",
            "/api/roles/super-admin/system",
        ):
            resp = client.get(path)
            assert resp.status_code == 403
            assert "Yeh feature sirf" in resp.json()["detail"]
            assert "ke liye hai" in resp.json()["detail"]


# ── /api/roles/me echo contract ──────────────────────────────────────


@pytest.mark.asyncio
async def test_roles_me_returns_role_and_tier_summary(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = _user_with_role(ROLE_CREATOR)
    with _client_for(user, db_maker) as client:
        resp = client.get("/api/roles/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == ROLE_CREATOR
    assert body["email"] == user.email
    # Tier summary mirrors the model's @property values.
    assert body["tiers"]["is_pro_or_above"] is True
    assert body["tiers"]["is_creator_or_above"] is True
    assert body["tiers"]["is_super_admin"] is False
