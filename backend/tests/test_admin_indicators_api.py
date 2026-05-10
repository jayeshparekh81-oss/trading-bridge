"""``/api/admin/indicators/*`` + ``/api/indicators/*`` route tests.

RBAC enforcement + happy-path smoke. Service-layer logic is
covered separately under ``tests/strategy_engine/indicator_admin/``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable

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

from app.api.admin_indicators import router as admin_router
from app.api.deps import get_current_active_user
from app.api.indicators import router as user_router
from app.auth.roles import ROLE_ADMIN, ROLE_CREATOR, ROLE_USER
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-ind-api-{uuid.uuid4().hex}"
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


async def _seed(
    maker: async_sessionmaker[AsyncSession], *, email: str, role: str
) -> User:
    async with maker() as s:
        u = User(email=email, password_hash="x", is_active=True, role=role)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User | None], TestClient]:
    def _build(user: User | None) -> TestClient:
        app = FastAPI()
        app.include_router(admin_router)
        app.include_router(user_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                yield s

        app.dependency_overrides[get_session] = _override_session

        if user is not None:
            async def _override_user() -> User:
                async with db_maker() as s:
                    fresh = await s.get(User, user.id)
                    assert fresh is not None
                    return fresh

            app.dependency_overrides[get_current_active_user] = _override_user

        return TestClient(app)

    return _build


# ─── Public status endpoint ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_public_status_returns_registry_default(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    user = await _seed(db_maker, email="u1@x", role=ROLE_USER)
    with make_client(user) as client:
        resp = client.get("/api/indicators/ema/status")
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "active"
    assert body["source"] == "registry_default"


@pytest.mark.asyncio
async def test_public_status_unknown_id_404(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    user = await _seed(db_maker, email="u2@x", role=ROLE_USER)
    with make_client(user) as client:
        resp = client.get("/api/indicators/totally_made_up_xyz/status")
    assert resp.status_code == 404


# ─── Creator queue: file + view + withdraw ───────────────────────────


@pytest.mark.asyncio
async def test_creator_can_file_request(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    creator = await _seed(db_maker, email="c1@x", role=ROLE_CREATOR)
    with make_client(creator) as client:
        resp = client.post(
            "/api/indicators/queue",
            json={
                "indicator_id": "kama",
                "requested_status": "active",
                "reason": "Has 50+ subscribers using it on Nifty scalpers",
            },
        )
    body = resp.json()
    assert resp.status_code == 201
    assert body["status"] == "pending"
    assert body["indicator_id"] == "kama"


@pytest.mark.asyncio
async def test_non_creator_cannot_file_request(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    user = await _seed(db_maker, email="u3@x", role=ROLE_USER)
    with make_client(user) as client:
        resp = client.post(
            "/api/indicators/queue",
            json={
                "indicator_id": "kama",
                "requested_status": "active",
                "reason": "x",
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_file_request_unknown_indicator_404(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """Filing for an id not in the registry → 404. Prevents
    creating phantom queue rows for typo'd ids."""
    creator = await _seed(db_maker, email="c2@x", role=ROLE_CREATOR)
    with make_client(creator) as client:
        resp = client.post(
            "/api/indicators/queue",
            json={
                "indicator_id": "made_up_xyz",
                "requested_status": "active",
                "reason": "x",
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_pending_request_409(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    creator = await _seed(db_maker, email="c3@x", role=ROLE_CREATOR)
    payload = {
        "indicator_id": "kama",
        "requested_status": "active",
        "reason": "first",
    }
    with make_client(creator) as client:
        first = client.post("/api/indicators/queue", json=payload)
        second = client.post("/api/indicators/queue", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_my_requests_isolates_per_user(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    creator_a = await _seed(db_maker, email="ca@x", role=ROLE_CREATOR)
    creator_b = await _seed(db_maker, email="cb@x", role=ROLE_CREATOR)
    with make_client(creator_a) as client:
        client.post(
            "/api/indicators/queue",
            json={
                "indicator_id": "kama",
                "requested_status": "active",
                "reason": "A",
            },
        )
    with make_client(creator_b) as client:
        client.post(
            "/api/indicators/queue",
            json={
                "indicator_id": "supertrend",
                "requested_status": "active",
                "reason": "B",
            },
        )
        resp = client.get("/api/indicators/queue/me")
    body = resp.json()
    ids = {r["indicator_id"] for r in body["requests"]}
    assert ids == {"supertrend"}


# ─── Admin: queue list + decide ──────────────────────────────────────


@pytest.mark.asyncio
async def test_non_admin_cannot_list_queue(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    creator = await _seed(db_maker, email="c4@x", role=ROLE_CREATOR)
    with make_client(creator) as client:
        resp = client.get("/api/admin/indicators/queue")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_approve_queue_item(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    creator = await _seed(db_maker, email="c5@x", role=ROLE_CREATOR)
    admin = await _seed(db_maker, email="a1@x", role=ROLE_ADMIN)
    with make_client(creator) as client:
        post_resp = client.post(
            "/api/indicators/queue",
            json={
                "indicator_id": "kama",
                "requested_status": "active",
                "reason": "ready",
            },
        )
        queue_id = post_resp.json()["id"]
    with make_client(admin) as client:
        decide_resp = client.post(
            f"/api/admin/indicators/queue/{queue_id}/decide",
            json={"decision": "approve", "notes": "lgtm"},
        )
        # Public status now reflects the override.
        status_resp = client.get("/api/indicators/kama/status")
    decide_body = decide_resp.json()
    status_body = status_resp.json()
    assert decide_resp.status_code == 200
    assert decide_body["status"] == "approved"
    assert decide_body["resulting_override_id"] is not None
    assert status_body["status"] == "active"
    assert status_body["source"] == "override"


@pytest.mark.asyncio
async def test_admin_decide_already_decided_409(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    creator = await _seed(db_maker, email="c6@x", role=ROLE_CREATOR)
    admin = await _seed(db_maker, email="a2@x", role=ROLE_ADMIN)
    with make_client(creator) as client:
        post_resp = client.post(
            "/api/indicators/queue",
            json={
                "indicator_id": "kama",
                "requested_status": "active",
                "reason": "x",
            },
        )
        queue_id = post_resp.json()["id"]
    with make_client(admin) as client:
        client.post(
            f"/api/admin/indicators/queue/{queue_id}/decide",
            json={"decision": "approve", "notes": "ok"},
        )
        second = client.post(
            f"/api/admin/indicators/queue/{queue_id}/decide",
            json={"decision": "reject", "notes": "changed mind"},
        )
    assert second.status_code == 409


# ─── Admin: direct override + history ────────────────────────────────


@pytest.mark.asyncio
async def test_admin_direct_override_unknown_indicator_404(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    admin = await _seed(db_maker, email="a3@x", role=ROLE_ADMIN)
    with make_client(admin) as client:
        resp = client.post(
            "/api/admin/indicators/totally_made_up/override",
            json={"new_status": "active", "reason": "x"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_direct_override_known_indicator_succeeds(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    admin = await _seed(db_maker, email="a4@x", role=ROLE_ADMIN)
    with make_client(admin) as client:
        resp = client.post(
            "/api/admin/indicators/ema/override",
            json={"new_status": "deprecated", "reason": "security issue"},
        )
        history = client.get("/api/admin/indicators/ema/history")
    body = resp.json()
    hist = history.json()
    assert resp.status_code == 200
    assert body["override_status"] == "deprecated"
    assert hist["current_status"] == "deprecated"
    assert len(hist["history"]) == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_override(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    creator = await _seed(db_maker, email="c7@x", role=ROLE_CREATOR)
    with make_client(creator) as client:
        resp = client.post(
            "/api/admin/indicators/ema/override",
            json={"new_status": "deprecated", "reason": "x"},
        )
    assert resp.status_code == 403
