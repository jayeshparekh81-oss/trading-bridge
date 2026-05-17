"""End-to-end template-clone flow integration test.

Catches bugs of the shape: clone POST creates a Strategy with
strategy_json=None + a strategy_template_origin row, but the detail
page's GET endpoint doesn't surface the origin → user sees the
"legacy" warning incorrectly.

Flow tested:
    1. POST /api/templates/{slug}/clone with an active template slug
    2. Assert 201 + response carries a Strategy + StrategyTemplateOrigin
    3. GET /api/strategies/{new_id}
    4. Assert response.template_origin is populated (slug, name, etc.)
    5. Assert strategy_json is None (the inert-clone Phase 1 contract)

Uses the lighter conftest at tests/strategy_engine/api/ via direct
import — adds the templates router so the clone POST works.
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


# JSONB → JSON compiler shim for sqlite test paths
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


_ACTIVE_TEMPLATE_CONFIG = {
    "indicators": ["parabolic_sar"],
    "entry_long": {"condition": "parabolic_sar flips below close"},
    "exit_long": {"condition": "parabolic_sar flips above close"},
    "stop_loss_pct": 1.5,
    "take_profit_pct": 3.5,
    "position_sizing": {"method": "fixed_amount", "amount_inr": 30000},
    "max_open_positions": 1,
    "trading_hours": {"start": "09:15", "end": "15:15"},
}


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tmpl-clone-flow-{uuid.uuid4().hex}"
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
async def seed_user_and_template(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> tuple[User, StrategyTemplate]:
    async with db_session_maker() as session:
        user = User(
            email="clone-flow@tradetri.test",
            password_hash="x",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        now = datetime.now(UTC)
        template = StrategyTemplate(
            id=uuid.uuid4(),
            slug="parabolic-sar-reversal",
            name="Parabolic SAR Reversal",
            segment="equity",
            instrument_type="stock",
            category="Trend Following",
            complexity="beginner",
            description_en="PSAR flip entries",
            description_hi="",
            config_json=_ACTIVE_TEMPLATE_CONFIG,
            risk_level="medium",
            recommended_capital_inr=30000,
            timeframe="5m",
            indicators_used=["parabolic_sar"],
            index_filter=[],
            tags=["psar"],
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
    seed_user_and_template: tuple[User, StrategyTemplate],
) -> Iterator[TestClient]:
    user, _ = seed_user_and_template
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

    async def _override_user() -> User:
        return user

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_active_user] = _override_user

    with TestClient(app) as c:
        yield c


def test_clone_then_detail_surfaces_template_origin(
    client: TestClient,
    seed_user_and_template: tuple[User, StrategyTemplate],
) -> None:
    """End-to-end clone + detail flow with template_origin assertion."""
    _, template = seed_user_and_template

    # Step 1: Clone the template
    resp = client.post(
        f"/api/templates/{template.slug}/clone",
        json={},
    )
    assert resp.status_code == 201, resp.text
    clone_body = resp.json()
    new_strategy_id = clone_body["strategy_id"]
    assert uuid.UUID(new_strategy_id)
    assert clone_body["template_slug"] == template.slug

    # Step 2: GET the detail
    detail = client.get(f"/api/strategies/{new_strategy_id}")
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()

    # Step 3: The detail response has template_origin populated
    assert detail_body["template_origin"] is not None, (
        "Cloned strategy detail must surface template_origin so the "
        "frontend doesn't render the legacy warning."
    )
    origin = detail_body["template_origin"]
    assert origin["template_slug"] == template.slug
    assert origin["template_name"] == template.name
    assert origin["template_category"] == "Trend Following"
    assert origin["template_complexity"] == "beginner"
    assert origin["config_json"]["stop_loss_pct"] == 1.5

    # Step 4: strategy_json IS None (cloned-row contract)
    assert detail_body["strategy_json"] is None


def test_handbuilt_strategy_detail_has_no_template_origin(
    client: TestClient,
) -> None:
    """Belt-and-braces — a hand-built strategy must NOT have a template_origin."""
    from tests.strategy_engine.api.conftest import make_strategy_payload

    payload = make_strategy_payload(name="handbuilt v1")
    create = client.post("/api/strategies", json=payload)
    assert create.status_code == 201
    strategy_id = create.json()["id"]

    detail = client.get(f"/api/strategies/{strategy_id}")
    assert detail.status_code == 200
    assert detail.json()["template_origin"] is None
