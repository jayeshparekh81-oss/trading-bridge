"""Phase 5B Part 3 — ``POST /api/strategies/{id}/backtest``.

Self-contained: each test builds its own FastAPI app holding the CRUD
+ backtest routers and overrides the auth + DB session dependencies.
A fresh sqlite-in-memory engine per test keeps state isolated.

Coverage:

    * happy path  — POST returns the three top-level keys, the backtest
                    section carries camelCase wire fields, the
                    health_card section carries snake_case (matches the
                    Phase X coach's wire shape).
    * 422 on legacy strategies whose ``strategy_json`` is NULL.
    * 404 when the strategy id doesn't exist OR isn't owned by the
      caller (cross-user enumeration guard).
    * auth required (401 without override).
"""

from __future__ import annotations

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
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api import router as strategy_crud_router
from app.strategy_engine.api.backtest import router as strategy_backtest_router

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Per-test in-memory aiosqlite engine; same StaticPool trick as
    the strategies CRUD test conftest so multiple event loops share
    one named in-memory database."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-bt-{uuid.uuid4().hex}"
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


async def _seed_user(maker: async_sessionmaker[AsyncSession], email: str) -> User:
    async with maker() as s:
        user = User(email=email, password_hash="x", is_active=True)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


async def _seed_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    name: str = "Backtest Test Strategy",
) -> Strategy:
    """Insert one strategy with the canonical sample DSL."""
    return await _insert_strategy(
        maker,
        user_id=user_id,
        name=name,
        strategy_json=_SAMPLE_STRATEGY_JSON.copy(),
    )


async def _seed_legacy_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    name: str = "Legacy strategy without DSL",
) -> Strategy:
    """Insert a strategy whose ``strategy_json`` column is NULL."""
    return await _insert_strategy(
        maker,
        user_id=user_id,
        name=name,
        strategy_json=None,
    )


async def _insert_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    name: str,
    strategy_json: dict[str, Any] | None,
) -> Strategy:
    async with maker() as s:
        strategy = Strategy(
            user_id=user_id,
            name=name,
            strategy_json=strategy_json,
            is_active=True,
        )
        s.add(strategy)
        await s.commit()
        await s.refresh(strategy)
        return strategy


_SAMPLE_STRATEGY_JSON: dict[str, object] = {
    "id": "backtest_endpoint_test",
    "name": "Backtest endpoint test",
    "mode": "expert",
    "indicators": [
        {"id": "ema_5", "type": "ema", "params": {"period": 5}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [{"type": "indicator", "left": "ema_5", "op": ">", "value": 95.0}],
    },
    "exit": {"targetPercent": 1.5, "stopLossPercent": 1.0},
    "risk": {},
    "execution": {
        "mode": "backtest",
        "orderType": "MARKET",
        "productType": "INTRADAY",
    },
}


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User], TestClient]:
    """Builder that returns a TestClient impersonating ``user``."""

    def _build(user: User) -> TestClient:
        app = FastAPI()
        app.include_router(strategy_backtest_router)
        app.include_router(strategy_crud_router)

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


# ─── Happy path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_backtest_returns_combined_response_with_three_sections(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """200 + ``{ backtest, reliability, health_card }`` shape."""
    user = await _seed_user(db_maker, "owner@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={},  # all defaults — synthetic candles, sensitivity off
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "backtest",
        "reliability",
        "health_card",
        "truth",
        "regime",
        "deviation",
    }
    # Phase 9 deviation is opt-in via ``include_deviation_demo``; the
    # default-body request leaves the field absent → ``None``.
    assert body["deviation"] is None

    # Backtest section uses camelCase aliases.
    backtest = body["backtest"]
    for key in ("totalPnl", "totalReturnPercent", "winRate", "totalTrades", "equityCurve"):
        assert key in backtest, f"missing camelCase key {key!r}"
    assert isinstance(backtest["equityCurve"], list)
    assert len(backtest["equityCurve"]) == 120  # synthetic candle count

    # Health card uses snake_case (Phase X coach has no aliases).
    health = body["health_card"]
    assert "overall_grade" in health
    assert health["overall_grade"] in {"A", "B", "C", "D", "F"}
    assert isinstance(health["metric_grades"], list)
    assert len(health["metric_grades"]) == 7

    # Reliability is opt-in but defaulted on; sensitivity is off (None).
    reliability = body["reliability"]
    assert reliability is not None
    assert reliability["sensitivity"] is None

    # Phase 6 Truth report rides on top of reliability — same camelCase
    # alias convention as the rest of the strategy-engine surface.
    truth = body["truth"]
    assert truth is not None
    for key in (
        "truthScore",
        "grade",
        "verdict",
        "riskLevel",
        "fakeBacktestWarnings",
        "overfittingWarnings",
        "executionWarnings",
        "costWarnings",
        "strengths",
        "weaknesses",
        "recommendedNextActions",
    ):
        assert key in truth, f"missing truth key {key!r}"
    assert 0 <= truth["truthScore"] <= 100
    assert truth["grade"] in {"A", "B", "C", "D", "F"}
    assert truth["riskLevel"] in {"low", "medium", "high", "extreme"}

    # Phase 8 regime report — always populated alongside a successful
    # backtest. Wire keys are camelCase (response_model_by_alias=True),
    # matching the BacktestResult / TruthReport convention.
    regime = body["regime"]
    assert regime is not None
    assert regime["regime"] in {
        "trending",
        "sideways",
        "high_volatility",
        "low_volatility",
        "gap_day",
        "choppy",
        "breakout",
        "abnormal",
    }
    assert 0.0 <= regime["confidence"] <= 1.0
    assert isinstance(regime["hinglishSummary"], str)
    assert len(regime["hinglishSummary"]) > 0
    assert isinstance(regime["warnings"], list)
    metrics = regime["metrics"]
    for key in (
        "adxValue",
        "atrNormalized",
        "maSlopePercent",
        "rangeCompressionRatio",
        "gapPercent",
        "directionChangesCount",
        "volatilityPercentile",
    ):
        assert key in metrics, f"missing regime metric key {key!r}"
    # Strategy was passed to detect_regime → suitability verdict present.
    suitability = regime["strategySuitability"]
    assert suitability is not None
    assert isinstance(suitability["suitable"], bool)
    assert suitability["riskLevel"] in {"low", "medium", "high"}
    assert suitability["strategyType"] in {
        "trend_following",
        "mean_reversion",
        "breakout",
        "volatility",
        "unknown",
    }


# ─── Deviation demo opt-in ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_backtest_returns_deviation_when_demo_requested(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """``include_deviation_demo=True`` synthesises a Phase 9 deviation
    report from the backtest's own trade list (70/30 split)."""
    user = await _seed_user(db_maker, "deviation@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"include_deviation_demo": True},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    deviation = body["deviation"]
    assert deviation is not None
    # Per the Phase 9 model — frozen, no aliases, snake_case.
    for key in (
        "deviation_score",
        "status",
        "deviations",
        "recommended_actions",
        "should_pause",
        "should_reduce_size",
        "should_switch_to_paper",
        "hinglish_summary",
        "auto_kill_switch_signal",
    ):
        assert key in deviation, f"missing deviation key {key!r}"
    assert deviation["status"] in {"normal", "watch", "warning", "critical"}
    assert 0.0 <= deviation["deviation_score"] <= 100.0
    assert isinstance(deviation["recommended_actions"], list)
    assert isinstance(deviation["hinglish_summary"], str)
    assert len(deviation["hinglish_summary"]) > 0


# ─── 422 on legacy strategies (strategy_json is NULL) ─────────────────


@pytest.mark.asyncio
async def test_post_backtest_422_when_strategy_has_no_dsl(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "legacy@tradetri.com")
    legacy = await _seed_legacy_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(f"/api/strategies/{legacy.id}/backtest", json={})

    assert resp.status_code == 422
    assert "DSL" in resp.json()["detail"]


# ─── 404 cross-user / unknown id ──────────────────────────────────────


@pytest.mark.asyncio
async def test_post_backtest_404_on_unknown_or_unowned_strategy(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """404 covers both 'not found' and 'not yours' — same body keeps
    the endpoint from being an id-enumeration oracle."""
    owner = await _seed_user(db_maker, "owner-a@tradetri.com")
    intruder = await _seed_user(db_maker, "intruder-b@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=owner.id)

    # Unknown id.
    with make_client(owner) as client:
        unknown_resp = client.post(f"/api/strategies/{uuid.uuid4()}/backtest", json={})
    assert unknown_resp.status_code == 404

    # Owner's id viewed by intruder → also 404 (NOT 403, by design).
    with make_client(intruder) as client:
        cross_resp = client.post(f"/api/strategies/{strategy.id}/backtest", json={})
    assert cross_resp.status_code == 404


# ─── 401 without auth override ────────────────────────────────────────


def test_post_backtest_requires_authentication() -> None:
    """Without the auth dep override, the dep raises 401 before any
    DB lookup happens — so this test needs no DB plumbing."""
    app = FastAPI()
    app.include_router(strategy_backtest_router)
    with TestClient(app) as client:
        resp = client.post(f"/api/strategies/{uuid.uuid4()}/backtest", json={})
    assert resp.status_code == 401
