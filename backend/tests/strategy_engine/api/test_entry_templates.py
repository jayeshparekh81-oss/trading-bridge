"""``/api/templates/entry`` CRUD — standalone Entry Builder backend.

Mirrors the pattern in :mod:`test_strategies_crud` — fresh
in-memory aiosqlite DB per test, auth + DB session deps overridden
on a tiny FastAPI app holding only the entry-templates router.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Iterator
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
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.entry_templates import router as entry_templates_router

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-entry-tpl-{uuid.uuid4().hex}"
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
    maker: async_sessionmaker[AsyncSession], email: str
) -> User:
    async with maker() as s:
        u = User(email=email, password_hash="x", is_active=True)
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
        app.include_router(entry_templates_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_current_active_user] = _override_user
        return TestClient(app)

    return _build


# ─── Sample payloads ──────────────────────────────────────────────────


def _valid_payload(name: str = "RSI overbought") -> dict[str, Any]:
    """Single price-condition entry template — passes
    ``EntryRules.model_validate``."""
    return {
        "name": name,
        "description": "Sirf entry — reusable template",
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "price", "op": ">", "value": 100.0},
        ],
        "indicators_used": [],
    }


# ─── 1. Happy path — POST + GET round-trip ───────────────────────────


@pytest.mark.asyncio
async def test_create_returns_201_and_persists_row(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "owner@x")
    with make_client(user) as client:
        resp = client.post(
            "/api/templates/entry", json=_valid_payload("first")
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "first"
    assert body["side"] == "BUY"
    assert body["operator"] == "AND"
    assert body["conditions"][0]["type"] == "price"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_list_returns_users_templates(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Two POSTs land both rows in the list response. Strict
    newest-first ordering relies on Postgres timestamptz microsecond
    precision; the SQLite test engine resolves ``func.now()`` to
    the second, so consecutive inserts can tie. Pin the contract
    that matters end-to-end (both rows visible) and let the
    Postgres-side production env enforce the ordering."""
    user = await _seed_user(db_maker, "owner-list@x")
    with make_client(user) as client:
        client.post("/api/templates/entry", json=_valid_payload("alpha"))
        client.post("/api/templates/entry", json=_valid_payload("beta"))

        resp = client.get("/api/templates/entry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    names = {t["name"] for t in body["templates"]}
    assert names == {"alpha", "beta"}


# ─── 2. Update + Delete ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_replaces_template_fields(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "owner-put@x")
    with make_client(user) as client:
        created = client.post(
            "/api/templates/entry", json=_valid_payload("old name")
        ).json()
        new_payload = _valid_payload("new name")
        new_payload["operator"] = "OR"
        resp = client.put(
            f"/api/templates/entry/{created['id']}", json=new_payload
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "new name"
    assert body["operator"] == "OR"


@pytest.mark.asyncio
async def test_delete_removes_template(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "owner-del@x")
    with make_client(user) as client:
        created = client.post(
            "/api/templates/entry", json=_valid_payload("doomed")
        ).json()
        del_resp = client.delete(
            f"/api/templates/entry/{created['id']}"
        )
        get_resp = client.get(
            f"/api/templates/entry/{created['id']}"
        )
    assert del_resp.status_code == 204
    assert get_resp.status_code == 404


# ─── 3. Validation — invalid condition shape → 422 ───────────────────


@pytest.mark.asyncio
async def test_create_rejects_invalid_condition_with_422(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Condition with an unknown ``type`` discriminator fails the
    canonical ``EntryRules.model_validate`` and surfaces as 422."""
    user = await _seed_user(db_maker, "owner-bad@x")
    bad = _valid_payload("bad")
    bad["conditions"] = [
        {"type": "this_does_not_exist", "value": 0.0},
    ]
    with make_client(user) as client:
        resp = client.post("/api/templates/entry", json=bad)
    assert resp.status_code == 422
    assert "Invalid entry block" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_rejects_empty_conditions_list(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """``conditions`` must have at least one entry — locked at the
    Pydantic boundary on both ``EntryTemplateCreate`` and
    ``EntryRules``."""
    user = await _seed_user(db_maker, "owner-empty@x")
    bad = _valid_payload("bad")
    bad["conditions"] = []
    with make_client(user) as client:
        resp = client.post("/api/templates/entry", json=bad)
    assert resp.status_code == 422


# ─── 4. Cross-user isolation ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_user_get_returns_404(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """User B can't read User A's template — 404 (not 403) so the
    endpoint isn't an enumeration oracle."""
    owner = await _seed_user(db_maker, "owner-iso@x")
    intruder = await _seed_user(db_maker, "intruder-iso@x")

    with make_client(owner) as client:
        created = client.post(
            "/api/templates/entry", json=_valid_payload("private")
        ).json()

    with make_client(intruder) as client:
        get_resp = client.get(
            f"/api/templates/entry/{created['id']}"
        )
        put_resp = client.put(
            f"/api/templates/entry/{created['id']}",
            json=_valid_payload("hijack"),
        )
        del_resp = client.delete(
            f"/api/templates/entry/{created['id']}"
        )
    assert get_resp.status_code == 404
    assert put_resp.status_code == 404
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_list_is_scoped_to_caller(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """User A's list call returns only A's templates, never B's."""
    user_a = await _seed_user(db_maker, "owner-list-a@x")
    user_b = await _seed_user(db_maker, "owner-list-b@x")

    with make_client(user_a) as client:
        client.post("/api/templates/entry", json=_valid_payload("a-only"))
    with make_client(user_b) as client:
        client.post("/api/templates/entry", json=_valid_payload("b-only"))

        list_b = client.get("/api/templates/entry").json()
    assert list_b["count"] == 1
    assert list_b["templates"][0]["name"] == "b-only"


# ─── 5. Auth required ────────────────────────────────────────────────


def _bare_iter() -> Iterator[None]:
    yield None


def test_create_requires_authentication() -> None:
    """No auth dep override → 401 before any DB access."""
    app = FastAPI()
    app.include_router(entry_templates_router)
    with TestClient(app) as client:
        resp = client.post(
            "/api/templates/entry", json=_valid_payload()
        )
    assert resp.status_code == 401
