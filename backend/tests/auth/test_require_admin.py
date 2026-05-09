"""Phase 1 RBAC — ``require_admin`` + role helpers.

Pins the contract:

    * Default role on a fresh User row is ``"user"``.
    * ``is_admin`` predicate flips on ``role`` (not on ``user.is_admin``
      column — the helper is the canonical Phase 2 reader).
    * ``require_admin`` dependency lets admins through and raises 403
      with a Hinglish detail for non-admins.
    * ``require_role(...)`` factory matches the same shape for an
      arbitrary role string (Phase 2 forward-compat).
    * The new ``GET /api/admin/audit-events`` endpoint demonstrates
      the wiring end-to-end.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

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

from app.api.admin import router as admin_router
from app.api.deps import get_current_active_user
from app.auth.roles import (
    PHASE1_ROLES,
    ROLE_ADMIN,
    ROLE_USER,
    is_admin,
    require_admin,
    require_role,
)
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.audit import clear_audit_log
from app.strategy_engine.audit.loggers import log_strategy_change

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-rbac-{uuid.uuid4().hex}"
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


def _make_app_with_user(
    user: User,
    db_maker: async_sessionmaker[AsyncSession],
) -> TestClient:
    """Build a TestClient that mounts the admin router with the
    given user impersonated and the supplied DB session bound."""
    app = FastAPI()
    app.include_router(admin_router)

    async def _override_user() -> User:
        return user

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    app.dependency_overrides[get_current_active_user] = _override_user
    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_audit_buffer() -> Iterator[None]:
    clear_audit_log()
    yield
    clear_audit_log()


# ── 1. Phase 1 vocabulary is locked ──────────────────────────────────


def test_phase1_roles_set_is_user_and_admin_only() -> None:
    """Pin the locked role vocabulary so a stray addition (e.g. an
    accidental ``ROLE_PRO_USER`` slip from Phase 2) trips a regression
    here rather than landing silently."""
    assert frozenset({ROLE_USER, ROLE_ADMIN}) == PHASE1_ROLES
    assert ROLE_USER == "user"
    assert ROLE_ADMIN == "admin"


# ── 2. Default role on a fresh User row ──────────────────────────────


@pytest.mark.asyncio
async def test_new_user_defaults_to_role_user(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """A User created without an explicit role uses the column's
    Python-level default (``"user"``). This mirrors what the
    server-side ``server_default`` would do for an insert that
    bypasses the ORM."""
    async with db_maker() as s:
        u = User(email="default-role@x", password_hash="p", is_active=True)
        s.add(u)
        await s.flush()
        assert u.role == ROLE_USER


# ── 3. is_admin predicate reads role, not the legacy is_admin column ─


def test_is_admin_predicate_reads_role_not_legacy_flag() -> None:
    admin = User(
        email="a@x",
        password_hash="p",
        is_active=True,
        is_admin=False,  # legacy flag explicitly off
        role=ROLE_ADMIN,
    )
    assert is_admin(admin) is True

    regular = User(
        email="r@x",
        password_hash="p",
        is_active=True,
        is_admin=True,  # legacy flag explicitly ON
        role=ROLE_USER,
    )
    # The new predicate ignores ``user.is_admin`` — only ``role`` matters.
    assert is_admin(regular) is False


# ── 4. require_admin behaviour through the audit-events endpoint ─────


@pytest.mark.asyncio
async def test_audit_events_endpoint_allows_admin(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    admin = User(
        email="admin@x",
        password_hash="p",
        is_active=True,
        role=ROLE_ADMIN,
    )
    # Seed one audit event so the response has a non-empty ``events`` list.
    log_strategy_change(
        strategy_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        change_type="created",
        summary="created in test",
    )

    with _make_app_with_user(admin, db_maker) as client:
        resp = client.get("/api/admin/audit-events")

    assert resp.status_code == 200
    body = resp.json()
    assert body["filtered_count"] >= 1
    assert body["events"][0]["event_type"] == "strategy_created"


@pytest.mark.asyncio
async def test_audit_events_endpoint_blocks_regular_user_with_hinglish(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    regular = User(
        email="user@x",
        password_hash="p",
        is_active=True,
        role=ROLE_USER,
    )
    with _make_app_with_user(regular, db_maker) as client:
        resp = client.get("/api/admin/audit-events")

    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "admin" in detail.lower()
    assert "Yeh feature sirf admin ke liye hai" in detail


def test_audit_events_endpoint_requires_authentication() -> None:
    """No auth dep override — the underlying ``get_current_active_user``
    raises 401 before ``require_admin`` runs the role check."""
    app = FastAPI()
    app.include_router(admin_router)
    with TestClient(app) as client:
        resp = client.get("/api/admin/audit-events")
    assert resp.status_code == 401


# ── 5. require_role(...) factory shape (Phase 2 forward-compat) ──────


def test_require_role_factory_blocks_mismatched_role() -> None:
    """``require_role("pro_user")`` (a Phase-2 role string) blocks a
    regular user — proves the factory shape works for any role
    without further changes when Phase 2 lands."""
    from fastapi import APIRouter, Depends, status

    pro_only_router = APIRouter()
    _pro_dep = require_role("pro_user")

    # Default-argument form here rather than ``Annotated[..., Depends]``
    # because ``from __future__ import annotations`` (top of this file)
    # turns annotations into strings that FastAPI's resolver doesn't
    # always read correctly for Annotated metadata on nested function
    # defs. The inline B008 noqa is intentional.
    @pro_only_router.get("/pro-only", status_code=status.HTTP_200_OK)
    async def pro_only(
        _user: User = Depends(_pro_dep),  # noqa: B008
    ) -> dict[str, str]:
        return {"status": "ok"}

    regular = User(
        email="regular@x",
        password_hash="p",
        is_active=True,
        role=ROLE_USER,
    )

    async def _override_regular() -> User:
        return regular

    app = FastAPI()
    app.include_router(pro_only_router)
    app.dependency_overrides[get_current_active_user] = _override_regular

    with TestClient(app) as client:
        resp = client.get("/pro-only")
    assert resp.status_code == 403, resp.json()
    detail = resp.json().get("detail", "")
    assert "pro_user" in detail


def test_require_role_factory_allows_matching_role() -> None:
    from fastapi import APIRouter, Depends, status

    router = APIRouter()
    _admin_dep = require_role(ROLE_ADMIN)

    @router.get("/admin-via-factory", status_code=status.HTTP_200_OK)
    async def via_factory(
        _user: User = Depends(_admin_dep),  # noqa: B008 — see neighbouring test
    ) -> dict[str, str]:
        return {"status": "ok"}

    admin = User(
        email="admin-factory@x",
        password_hash="p",
        is_active=True,
        role=ROLE_ADMIN,
    )

    async def _override_admin() -> User:
        return admin

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_active_user] = _override_admin

    with TestClient(app) as client:
        resp = client.get("/admin-via-factory")
    assert resp.status_code == 200


# ── 6. require_admin direct unit-style — pure import contract ────────


def test_require_admin_is_an_async_callable() -> None:
    import inspect

    assert inspect.iscoroutinefunction(require_admin)


def test_require_role_factory_returns_named_dependency() -> None:
    """The factory tags the returned function with a stable name so
    FastAPI's dependency cache key + traceback frames are
    debuggable. Pinned so a refactor that drops the rename breaks
    here, not in production logs."""
    dep = require_role("creator")
    assert dep.__name__ == "require_role_creator"


# ── 7. Filters on the audit-events endpoint ──────────────────────────


@pytest.mark.asyncio
async def test_audit_events_filter_by_event_type(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    admin = User(
        email="filter@x",
        password_hash="p",
        is_active=True,
        role=ROLE_ADMIN,
    )
    sid_a = uuid.uuid4()
    sid_b = uuid.uuid4()
    log_strategy_change(
        strategy_id=sid_a,
        user_id=uuid.uuid4(),
        change_type="created",
        summary="created A",
    )
    log_strategy_change(
        strategy_id=sid_b,
        user_id=uuid.uuid4(),
        change_type="updated",
        summary="updated B",
    )

    with _make_app_with_user(admin, db_maker) as client:
        resp = client.get(
            "/api/admin/audit-events",
            params={"event_type": "strategy_updated"},
        )

    assert resp.status_code == 200
    body = resp.json()
    # Only the updated event matches the filter; total_count is the
    # buffer-wide count (>= 2) and filtered_count is the matches.
    assert body["filtered_count"] == 1
    assert body["events"][0]["summary"] == "updated B"
    assert body["total_count"] >= 2
