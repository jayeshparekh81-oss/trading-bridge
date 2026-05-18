"""Strategy CRUD regression suite covering both hand-built + cloned rows.

Catches regressions of the shape: a change to GET/POST/PUT/DELETE
breaks one row type while passing tests on the other. Exercises all
5 CRUD endpoints against BOTH origin types and asserts no surprises.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

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

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api import router as strategy_crud_router
from app.templates.api import router as templates_router
from app.templates.models import StrategyTemplate


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:strat-crud-{uuid.uuid4().hex}"
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
async def setup(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> tuple[User, StrategyTemplate]:
    async with db_session_maker() as session:
        user = User(email="strat-crud@tradetri.test", password_hash="x", is_active=True)
        session.add(user)
        await session.flush()
        now = datetime.now(UTC)
        template = StrategyTemplate(
            id=uuid.uuid4(),
            slug="test-template",
            name="Test Template",
            segment="equity",
            instrument_type="stock",
            category="Trend",
            complexity="beginner",
            description_en="x",
            description_hi="",
            config_json={
                "indicators": ["ema"],
                "entry_long": {"condition": "ema > price"},
                "exit_long": {"condition": "ema < price"},
                "stop_loss_pct": 1.0,
                "take_profit_pct": 2.0,
                "position_sizing": {"method": "fixed_amount", "amount_inr": 10000},
                "max_open_positions": 1,
                "trading_hours": {"start": "09:15", "end": "15:15"},
            },
            risk_level="low",
            recommended_capital_inr=10000,
            timeframe="5m",
            indicators_used=["ema"],
            index_filter=[],
            tags=[],
            is_active=True,
            requires_options_builder=False,
            legs_count=None,
            display_order=0,
            created_at=now,
            updated_at=now,
        )
        session.add(template)
        await session.commit()
        await session.refresh(user)
        await session.refresh(template)
        return user, template


@pytest.fixture
def client(
    db_session_maker: async_sessionmaker[AsyncSession],
    setup: tuple[User, StrategyTemplate],
) -> Iterator[TestClient]:
    user, _ = setup
    app = FastAPI()
    app.include_router(templates_router)
    app.include_router(strategy_crud_router)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_active_user] = lambda: user

    with TestClient(app) as c:
        yield c


def test_list_contains_both_handbuilt_and_cloned(
    client: TestClient,
    setup: tuple[User, StrategyTemplate],
) -> None:
    """LIST returns both row types; no template_origin in list response (perf)."""
    from tests.strategy_engine.api.conftest import make_strategy_payload

    _, template = setup
    # Hand-built
    handbuilt = client.post(
        "/api/strategies",
        json=make_strategy_payload(name="handbuilt-1"),
    )
    assert handbuilt.status_code == 201
    # Cloned
    cloned = client.post(f"/api/templates/{template.slug}/clone", json={})
    assert cloned.status_code == 201

    list_resp = client.get("/api/strategies")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["count"] == 2
    names = {s["name"] for s in body["strategies"]}
    assert "handbuilt-1" in names
    # Verify list doesn't carry template_origin (it's a GET-one only field)
    for s in body["strategies"]:
        assert s.get("template_origin") is None


def test_get_cloned_strategy_has_origin(
    client: TestClient,
    setup: tuple[User, StrategyTemplate],
) -> None:
    _, template = setup
    clone = client.post(f"/api/templates/{template.slug}/clone", json={})
    sid = clone.json()["strategy_id"]
    detail = client.get(f"/api/strategies/{sid}")
    assert detail.json()["template_origin"] is not None


def test_get_handbuilt_strategy_has_no_origin(
    client: TestClient,
) -> None:
    from tests.strategy_engine.api.conftest import make_strategy_payload

    create = client.post("/api/strategies", json=make_strategy_payload())
    sid = create.json()["id"]
    detail = client.get(f"/api/strategies/{sid}")
    assert detail.json()["template_origin"] is None


def test_put_handbuilt_strategy_does_not_create_origin(
    client: TestClient,
) -> None:
    """PUT update should NOT spawn a template_origin row."""
    from tests.strategy_engine.api.conftest import make_strategy_payload

    create = client.post("/api/strategies", json=make_strategy_payload(name="v1"))
    sid = create.json()["id"]

    update_payload = make_strategy_payload(name="v2 renamed")
    upd = client.put(f"/api/strategies/{sid}", json=update_payload)
    assert upd.status_code == 200

    detail = client.get(f"/api/strategies/{sid}")
    assert detail.json()["template_origin"] is None
    assert detail.json()["name"] == "v2 renamed"


def test_delete_handbuilt_strategy_404s_subsequent_get(
    client: TestClient,
) -> None:
    from tests.strategy_engine.api.conftest import make_strategy_payload

    create = client.post("/api/strategies", json=make_strategy_payload())
    sid = create.json()["id"]

    delete = client.delete(f"/api/strategies/{sid}")
    assert delete.status_code == 204

    detail = client.get(f"/api/strategies/{sid}")
    assert detail.status_code == 404


def test_delete_cloned_strategy_cascade_origin(
    client: TestClient,
    setup: tuple[User, StrategyTemplate],
) -> None:
    """Deleting a cloned strategy should NOT leave a dangling origin row."""
    _, template = setup
    clone = client.post(f"/api/templates/{template.slug}/clone", json={})
    sid = clone.json()["strategy_id"]

    detail_before = client.get(f"/api/strategies/{sid}")
    assert detail_before.json()["template_origin"] is not None

    delete = client.delete(f"/api/strategies/{sid}")
    assert delete.status_code == 204

    detail_after = client.get(f"/api/strategies/{sid}")
    assert detail_after.status_code == 404


def test_clone_unknown_template_returns_404(
    client: TestClient,
) -> None:
    resp = client.post("/api/templates/nonexistent-slug/clone", json={})
    assert resp.status_code == 404
