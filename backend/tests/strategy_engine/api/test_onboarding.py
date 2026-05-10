"""``/api/onboarding`` state-machine tests.

Mirrors the marketplace / support fixtures: in-memory aiosqlite
DB per test, FastAPI ``dependency_overrides`` for auth + session.

The state machine has four user-visible operations (state, step,
preferences, complete) plus the implicit "no admin gate, every
user manages their own state" contract.
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

from app.api.deps import get_current_active_user
from app.auth.roles import ROLE_USER
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.onboarding import router as onboarding_router

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-onboarding-{uuid.uuid4().hex}"
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
    *,
    onboarding_step: int = 0,
) -> User:
    async with maker() as s:
        u = User(
            email=email,
            password_hash="x",
            is_active=True,
            role=ROLE_USER,
            onboarding_step=onboarding_step,
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
        app.include_router(onboarding_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        async def _override_user() -> User:
            # ``db.get`` reads from disk so subsequent test calls
            # see the latest persisted ``onboarding_step`` /
            # ``notification_prefs``. ``merge`` would return a
            # stale in-memory snapshot.
            async with db_maker() as s:
                fresh = await s.get(User, user.id)
                assert fresh is not None
                return fresh

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_current_active_user] = _override_user
        return TestClient(app)

    return _build


# ─── 1. State endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_state_for_new_user(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "new@x", onboarding_step=0)
    with make_client(user) as client:
        resp = client.get("/api/onboarding/state")
    body = resp.json()
    assert resp.status_code == 200
    assert body["onboarding_step"] == 0
    assert body["is_new_user"] is True
    assert body["onboarding_completed_at"] is None


@pytest.mark.asyncio
async def test_state_for_completed_user(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Existing users (onboarding_step == 6 from migration backfill)
    surface as ``is_new_user=False`` — the dashboard's auto-redirect
    reads exactly this flag."""
    user = await _seed_user(db_maker, "old@x", onboarding_step=6)
    with make_client(user) as client:
        resp = client.get("/api/onboarding/state")
    assert resp.json()["is_new_user"] is False


# ─── 2. Step advance ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_advance_step_succeeds_forward(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "fwd@x", onboarding_step=0)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/step", json={"next_step": 1}
        )
    assert resp.status_code == 200
    assert resp.json()["onboarding_step"] == 1


@pytest.mark.asyncio
async def test_advance_step_rejects_backwards(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Forward-only contract — once at step 3, cannot move to 2."""
    user = await _seed_user(db_maker, "back@x", onboarding_step=3)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/step", json={"next_step": 2}
        )
    assert resp.status_code == 409
    assert "backwards" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_advance_step_rejects_same_step(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Re-firing step 3 from step 3 is a 409 (forward-only is
    strict — no idempotent same-step advance)."""
    user = await _seed_user(db_maker, "same@x", onboarding_step=3)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/step", json={"next_step": 3}
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_advance_step_rejects_already_complete(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "done@x", onboarding_step=6)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/step", json={"next_step": 5}
        )
    assert resp.status_code == 409
    assert "already complete" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_advance_step_validates_range(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Pydantic enforces 1 <= next_step <= 5. Higher values get 422."""
    user = await _seed_user(db_maker, "rng@x", onboarding_step=0)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/step", json={"next_step": 6}
        )
    assert resp.status_code == 422


# ─── 3. Preferences ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_preferences_save_goal_and_experience(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "prefs@x", onboarding_step=2)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/preferences",
            json={"goal": "build_and_backtest", "experience": "new"},
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["goal"] == "build_and_backtest"
    assert body["experience"] == "new"


@pytest.mark.asyncio
async def test_preferences_partial_update(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Saving only ``goal`` doesn't clear a previously-saved
    ``experience`` (and vice-versa)."""
    user = await _seed_user(db_maker, "partial@x", onboarding_step=2)
    with make_client(user) as client:
        client.post(
            "/api/onboarding/preferences",
            json={"goal": "explore", "experience": "expert"},
        )
        resp = client.post(
            "/api/onboarding/preferences",
            json={"goal": "marketplace_buy"},
        )
    body = resp.json()
    assert body["goal"] == "marketplace_buy"
    assert body["experience"] == "expert"  # preserved


@pytest.mark.asyncio
async def test_preferences_rejects_unknown_goal(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "bad-goal@x", onboarding_step=2)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/preferences",
            json={"goal": "yolo_mode"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_preferences_locked_after_complete(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Post-completion the prefs endpoint refuses mutations —
    user-settings page is the right surface for goal changes
    after onboarding is over."""
    user = await _seed_user(db_maker, "lock@x", onboarding_step=6)
    with make_client(user) as client:
        resp = client.post(
            "/api/onboarding/preferences",
            json={"goal": "explore"},
        )
    assert resp.status_code == 409


# ─── 4. Complete endpoint ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_terminates_flow(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "fin@x", onboarding_step=3)
    with make_client(user) as client:
        resp = client.post("/api/onboarding/complete")
    body = resp.json()
    assert resp.status_code == 200
    assert body["onboarding_step"] == 6
    assert body["is_new_user"] is False
    assert body["onboarding_completed_at"] is not None


@pytest.mark.asyncio
async def test_complete_is_idempotent(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Re-calling complete on an already-complete user is a 200
    that returns the same state (timestamp NOT re-stamped)."""
    user = await _seed_user(db_maker, "idem@x", onboarding_step=3)
    with make_client(user) as client:
        first = client.post("/api/onboarding/complete").json()
        second = client.post("/api/onboarding/complete").json()
    assert first["onboarding_completed_at"] == second["onboarding_completed_at"]


# ─── 5. Auth ─────────────────────────────────────────────────────────


def test_unauthenticated_state_returns_401() -> None:
    app = FastAPI()
    app.include_router(onboarding_router)
    with TestClient(app) as client:
        resp = client.get("/api/onboarding/state")
    assert resp.status_code == 401
