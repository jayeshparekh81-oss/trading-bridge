"""``/api/support`` CRUD + RBAC tests.

Mirrors the marketplace test pattern: fresh in-memory aiosqlite
DB per test, FastAPI ``dependency_overrides`` for auth + session
+ admin gate. The support API has two role gates:

    * Any authenticated user — POST /tickets, GET /tickets/me,
      GET /tickets/{id} (own only).
    * Admin-only — GET /tickets, PUT /tickets/{id}, DELETE /tickets/{id}.

Each gate gets at least one positive case and one rejection. The
auto-priority schedule + the ``status='resolved'`` →
``resolved_at`` side-effect get their own pinned cases.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Callable
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
from app.auth.roles import (
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    require_admin,
)
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.support import router as support_router

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-support-{uuid.uuid4().hex}"
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
    email: str,
    role: str = ROLE_USER,
) -> User:
    async with maker() as s:
        u = User(
            email=email,
            password_hash="x",
            is_active=True,
            role=role,
            is_admin=role in (ROLE_ADMIN, ROLE_SUPER_ADMIN),
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User], TestClient]:
    def _build(user: User) -> TestClient:
        app = FastAPI()
        app.include_router(support_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        async def _override_user() -> User:
            return user

        async def _override_admin() -> User:
            allowed = {ROLE_ADMIN, ROLE_SUPER_ADMIN}
            if user.role not in allowed:
                from fastapi import HTTPException
                from fastapi import status as http_status

                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="Admin only.",
                )
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_current_active_user] = _override_user
        app.dependency_overrides[require_admin] = _override_admin
        return TestClient(app)

    return _build


# ─── Sample payloads ──────────────────────────────────────────────────


def _payload(
    *, category: str = "strategy_help", description: str = "Need help"
) -> dict[str, Any]:
    return {
        "category": category,
        "subject": "Help needed",
        "description": description,
    }


# ─── 1. Create + visibility ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_can_create_ticket(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "u1@x")
    with make_client(user) as client:
        resp = client.post("/api/support/tickets", json=_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "open"
    assert body["category"] == "strategy_help"
    assert body["user_id"] == str(user.id)


@pytest.mark.asyncio
async def test_create_ticket_emits_email_stub_log(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Phase 1 stub logs ``support.ticket.email_stub`` at INFO.

    Substring match because the project uses structlog → stdlib
    bridging, which formats the event name into a longer string
    rather than placing it raw in ``record.message``."""
    user = await _seed_user(db_maker, "stub@x")
    with (
        caplog.at_level(logging.INFO, logger="app.strategy_engine.api.support"),
        make_client(user) as client,
    ):
        client.post("/api/support/tickets", json=_payload())
    stub_lines = [
        r for r in caplog.records if "support.ticket.email_stub" in r.message
    ]
    assert len(stub_lines) == 1


@pytest.mark.asyncio
async def test_list_my_tickets_scoped_to_caller(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    a = await _seed_user(db_maker, "a@x")
    b = await _seed_user(db_maker, "b@x")
    with make_client(a) as client:
        client.post("/api/support/tickets", json=_payload())
    with make_client(b) as client:
        client.post("/api/support/tickets", json=_payload())
        resp = client.get("/api/support/tickets/me")
    body = resp.json()
    assert body["count"] == 1
    assert body["tickets"][0]["user_id"] == str(b.id)


@pytest.mark.asyncio
async def test_get_ticket_owner_only_404_for_others(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    owner = await _seed_user(db_maker, "owner@x")
    intruder = await _seed_user(db_maker, "intruder@x")
    with make_client(owner) as client:
        created = client.post("/api/support/tickets", json=_payload()).json()
    with make_client(intruder) as client:
        resp = client.get(f"/api/support/tickets/{created['id']}")
    # 404, not 403, so the endpoint isn't an enumeration oracle.
    assert resp.status_code == 404


# ─── 2. Auto-priority by category ─────────────────────────────────────


@pytest.mark.asyncio
async def test_billing_category_gets_high_priority(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "bill@x")
    with make_client(user) as client:
        resp = client.post(
            "/api/support/tickets",
            json=_payload(category="billing"),
        )
    assert resp.json()["priority"] == "high"


@pytest.mark.asyncio
async def test_other_category_gets_low_priority(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "low@x")
    with make_client(user) as client:
        resp = client.post(
            "/api/support/tickets",
            json=_payload(category="other"),
        )
    assert resp.json()["priority"] == "low"


@pytest.mark.asyncio
async def test_bug_with_critical_keyword_escalates_to_critical(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """A ``bug`` ticket whose description matches a known severity
    keyword (``crash``, ``data loss``, etc.) bumps from ``high``
    to ``critical``."""
    user = await _seed_user(db_maker, "crit@x")
    with make_client(user) as client:
        resp = client.post(
            "/api/support/tickets",
            json=_payload(
                category="bug",
                description="App keeps crashing every time I open the strategy page",
            ),
        )
    assert resp.json()["priority"] == "critical"


@pytest.mark.asyncio
async def test_bug_without_critical_keyword_stays_high(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "bug-high@x")
    with make_client(user) as client:
        resp = client.post(
            "/api/support/tickets",
            json=_payload(
                category="bug",
                description="The chart axis labels look misaligned on Safari.",
            ),
        )
    assert resp.json()["priority"] == "high"


# ─── 3. Validation ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subject_length_validation(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "len@x")
    with make_client(user) as client:
        resp = client.post(
            "/api/support/tickets",
            json={
                "category": "other",
                "subject": "x" * 250,  # > 200
                "description": "ok",
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unknown_category_rejected(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "cat@x")
    with make_client(user) as client:
        resp = client.post(
            "/api/support/tickets",
            json={
                "category": "feature_request",  # not in enum
                "subject": "x",
                "description": "y",
            },
        )
    assert resp.status_code == 422


# ─── 4. Admin endpoints ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_can_list_all_tickets(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user_a = await _seed_user(db_maker, "ua@x")
    user_b = await _seed_user(db_maker, "ub@x")
    admin = await _seed_user(db_maker, "admin@x", role=ROLE_ADMIN)

    with make_client(user_a) as client:
        client.post("/api/support/tickets", json=_payload())
    with make_client(user_b) as client:
        client.post("/api/support/tickets", json=_payload())

    with make_client(admin) as client:
        resp = client.get("/api/support/tickets")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_non_admin_blocked_from_list_all(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "regular@x")
    with make_client(user) as client:
        resp = client.get("/api/support/tickets")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_filter_by_status_and_priority(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "filt@x")
    admin = await _seed_user(db_maker, "filt-admin@x", role=ROLE_ADMIN)
    with make_client(user) as client:
        client.post("/api/support/tickets", json=_payload(category="billing"))
        client.post("/api/support/tickets", json=_payload(category="other"))
    with make_client(admin) as client:
        only_high = client.get(
            "/api/support/tickets", params={"priority": "high"}
        )
    assert only_high.json()["count"] == 1
    assert only_high.json()["tickets"][0]["category"] == "billing"


@pytest.mark.asyncio
async def test_admin_can_resolve_ticket_and_resolved_at_populated(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "res-u@x")
    admin = await _seed_user(db_maker, "res-admin@x", role=ROLE_ADMIN)
    with make_client(user) as client:
        ticket = client.post(
            "/api/support/tickets", json=_payload()
        ).json()

    with make_client(admin) as client:
        resp = client.put(
            f"/api/support/tickets/{ticket['id']}",
            json={"status": "resolved"},
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None


@pytest.mark.asyncio
async def test_flipping_back_out_of_resolved_clears_resolved_at(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "flip-u@x")
    admin = await _seed_user(db_maker, "flip-admin@x", role=ROLE_ADMIN)
    with make_client(user) as client:
        ticket = client.post(
            "/api/support/tickets", json=_payload()
        ).json()
    with make_client(admin) as client:
        client.put(
            f"/api/support/tickets/{ticket['id']}",
            json={"status": "resolved"},
        )
        resp = client.put(
            f"/api/support/tickets/{ticket['id']}",
            json={"status": "in_progress"},
        )
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["resolved_at"] is None


@pytest.mark.asyncio
async def test_non_admin_cannot_update_ticket(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "noadmin-u@x")
    intruder = await _seed_user(db_maker, "noadmin-i@x")
    with make_client(user) as client:
        ticket = client.post(
            "/api/support/tickets", json=_payload()
        ).json()
    with make_client(intruder) as client:
        resp = client.put(
            f"/api/support/tickets/{ticket['id']}",
            json={"status": "resolved"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_soft_delete_flips_to_closed(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "del-u@x")
    admin = await _seed_user(db_maker, "del-admin@x", role=ROLE_ADMIN)
    with make_client(user) as client:
        ticket = client.post(
            "/api/support/tickets", json=_payload()
        ).json()
    with make_client(admin) as client:
        resp = client.delete(f"/api/support/tickets/{ticket['id']}")
        # Owner can still see it after soft delete (status=closed).
    with make_client(user) as client:
        get_resp = client.get(f"/api/support/tickets/{ticket['id']}")
    assert resp.status_code == 204
    assert get_resp.json()["status"] == "closed"


# ─── 5. Auth required ────────────────────────────────────────────────


def test_unauthenticated_create_returns_401() -> None:
    app = FastAPI()
    app.include_router(support_router)
    with TestClient(app) as client:
        resp = client.post(
            "/api/support/tickets", json=_payload()
        )
    assert resp.status_code == 401
