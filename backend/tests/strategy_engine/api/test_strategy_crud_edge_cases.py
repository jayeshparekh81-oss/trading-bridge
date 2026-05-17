"""High-risk edge cases for /api/strategies CRUD.

NOT modifications to existing tests — purely additive coverage for
edge cases that could cause customer pain:
  - Null / missing required fields
  - Max-length name handling (256 chars per schema)
  - Duplicate-name across same user (allowed? blocked?)
  - Cross-user ownership transfer attempts (must 404)
  - Update payloads that try to change the owner field
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api import router as strategy_crud_router
from tests.strategy_engine.api.conftest import make_strategy_payload


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:crud-edge-{uuid.uuid4().hex}"
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


@pytest_asyncio.fixture
async def seed_user(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> User:
    async with db_session_maker() as session:
        u = User(email="crud-edge@tradetri.test", password_hash="x", is_active=True)
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u


@pytest.fixture
def client(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(strategy_crud_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: seed_user
    with TestClient(app) as c:
        yield c


# ─── Missing required fields ──────────────────────────────────────────


def test_create_strategy_missing_strategy_json_returns_422(client: TestClient) -> None:
    resp = client.post("/api/strategies", json={})
    assert resp.status_code == 422


def test_create_strategy_null_strategy_json_returns_422(client: TestClient) -> None:
    resp = client.post("/api/strategies", json={"strategy_json": None})
    assert resp.status_code == 422


def test_create_strategy_missing_entry_block_returns_422(client: TestClient) -> None:
    payload = make_strategy_payload()
    del payload["strategy_json"]["entry"]
    resp = client.post("/api/strategies", json=payload)
    assert resp.status_code == 422


def test_create_strategy_missing_exit_block_returns_422(client: TestClient) -> None:
    payload = make_strategy_payload()
    del payload["strategy_json"]["exit"]
    resp = client.post("/api/strategies", json=payload)
    assert resp.status_code == 422


# ─── Max-length names ──────────────────────────────────────────────────


def test_create_strategy_at_max_length_name_succeeds(client: TestClient) -> None:
    """StrategyJSON.name has max_length=256."""
    payload = make_strategy_payload(name="x" * 256)
    resp = client.post("/api/strategies", json=payload)
    assert resp.status_code == 201
    assert len(resp.json()["name"]) == 256


def test_create_strategy_exceeding_max_length_name_returns_422(
    client: TestClient,
) -> None:
    payload = make_strategy_payload(name="x" * 257)
    resp = client.post("/api/strategies", json=payload)
    assert resp.status_code == 422


def test_create_strategy_empty_name_returns_422(client: TestClient) -> None:
    payload = make_strategy_payload(name="")
    resp = client.post("/api/strategies", json=payload)
    assert resp.status_code == 422


# ─── Duplicate names ──────────────────────────────────────────────────


def test_duplicate_names_allowed_per_user(client: TestClient) -> None:
    """The schema does NOT block duplicate names for the same user —
    two strategies with the same name produce two distinct ids."""
    r1 = client.post("/api/strategies", json=make_strategy_payload(name="Twin"))
    r2 = client.post("/api/strategies", json=make_strategy_payload(name="Twin"))
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


# ─── Cross-user ownership ─────────────────────────────────────────────


def test_get_strategy_owned_by_different_user_returns_404(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Anti-enumeration: foreign-user rows return 404, NOT 403."""
    import asyncio

    other_user_id = uuid.uuid4()

    async def _seed_other_strategy() -> str:
        from app.db.models.strategy import Strategy

        async with db_session_maker() as session:
            other = User(
                id=other_user_id,
                email="other-user@tradetri.test",
                password_hash="x",
                is_active=True,
            )
            session.add(other)
            await session.flush()
            s = Strategy(
                user_id=other_user_id,
                name="not yours",
                is_active=True,
                strategy_json={"some": "blob"},
            )
            session.add(s)
            await session.commit()
            await session.refresh(s)
            return str(s.id)

    foreign_id = asyncio.get_event_loop().run_until_complete(_seed_other_strategy())
    resp = client.get(f"/api/strategies/{foreign_id}")
    assert resp.status_code == 404
    # Detail message should NOT leak that the row exists
    assert "foreign" not in resp.json().get("detail", "").lower()
    assert "another user" not in resp.json().get("detail", "").lower()


def test_update_strategy_owned_by_different_user_returns_404(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    import asyncio

    other_user_id = uuid.uuid4()

    async def _seed_other() -> str:
        from app.db.models.strategy import Strategy

        async with db_session_maker() as session:
            session.add(
                User(
                    id=other_user_id,
                    email="other2@tradetri.test",
                    password_hash="x",
                    is_active=True,
                )
            )
            await session.flush()
            s = Strategy(
                user_id=other_user_id,
                name="locked",
                is_active=True,
                strategy_json={"x": 1},
            )
            session.add(s)
            await session.commit()
            await session.refresh(s)
            return str(s.id)

    foreign_id = asyncio.get_event_loop().run_until_complete(_seed_other())
    resp = client.put(f"/api/strategies/{foreign_id}", json=make_strategy_payload())
    assert resp.status_code == 404


def test_delete_strategy_owned_by_different_user_returns_404(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    import asyncio

    other_user_id = uuid.uuid4()

    async def _seed_other() -> str:
        from app.db.models.strategy import Strategy

        async with db_session_maker() as session:
            session.add(
                User(
                    id=other_user_id,
                    email="other3@tradetri.test",
                    password_hash="x",
                    is_active=True,
                )
            )
            await session.flush()
            s = Strategy(
                user_id=other_user_id,
                name="cannot-delete",
                is_active=True,
                strategy_json={"x": 1},
            )
            session.add(s)
            await session.commit()
            await session.refresh(s)
            return str(s.id)

    foreign_id = asyncio.get_event_loop().run_until_complete(_seed_other())
    resp = client.delete(f"/api/strategies/{foreign_id}")
    assert resp.status_code == 404


# ─── Malformed UUIDs ──────────────────────────────────────────────────


def test_get_strategy_with_malformed_uuid_returns_422(client: TestClient) -> None:
    resp = client.get("/api/strategies/not-a-uuid")
    assert resp.status_code == 422


def test_delete_strategy_with_malformed_uuid_returns_422(client: TestClient) -> None:
    resp = client.delete("/api/strategies/clearly-not-uuid")
    assert resp.status_code == 422
