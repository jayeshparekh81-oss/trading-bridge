"""End-to-end backtest flow against a mocked Dhan adapter.

Pins the contract that, once Phase C wires the data-provider in, a
``candles_request`` body produces a *fully populated* backtest
response — every panel the frontend depends on (Phase 3 result,
Phase 4 reliability + trust, Phase 6 truth, Phase 7 trade-quality +
diagnosis, Phase 8 regime, Phase 9 deviation demo, Phase 11 quality
warnings, Phase 12 version manifest) lights up against the real
backtest pipeline.

The Dhan adapter is mocked at the import boundary inside
``app.strategy_engine.api.backtest`` so no network is touched and
the test runs in milliseconds.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
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
from app.strategy_engine.data_provider.models import (
    HistoricalDataRequest,
    HistoricalDataResponse,
)
from app.strategy_engine.schema.ohlcv import Candle

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-realdata-{uuid.uuid4().hex}"
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


_SAMPLE_STRATEGY_JSON: dict[str, Any] = {
    "id": "real_data_test",
    "name": "Real-data backtest test",
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


async def _seed_user(maker: async_sessionmaker[AsyncSession]) -> User:
    async with maker() as s:
        user = User(email="real-data@tradetri.com", password_hash="x", is_active=True)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


async def _seed_strategy(
    maker: async_sessionmaker[AsyncSession], *, user_id: uuid.UUID
) -> Strategy:
    async with maker() as s:
        strategy = Strategy(
            user_id=user_id,
            name="Real-data backtest",
            strategy_json=dict(_SAMPLE_STRATEGY_JSON),
            is_active=True,
        )
        s.add(strategy)
        await s.commit()
        await s.refresh(strategy)
        return strategy


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User], TestClient]:
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


def _clean_candles(n: int = 240) -> list[Candle]:
    """Lightly-trending 1-minute candles. Enough bars for every Phase
    4 sub-analysis (OOS, walk-forward, sensitivity) to clear its
    minimum-bar gate."""
    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    candles: list[Candle] = []
    for i in range(n):
        mid = 100.0 + (i % 24) * 0.05
        candles.append(
            Candle(
                timestamp=base + timedelta(minutes=i),
                open=mid,
                high=mid + 0.6,
                low=mid - 0.4,
                close=mid + 0.2,
                volume=1_000.0,
            )
        )
    return candles


# ─── End-to-end: every panel populated when Dhan supplies the data ────


@pytest.mark.asyncio
async def test_real_data_backtest_populates_every_panel(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive the endpoint with ``candles_request`` + ``include_deviation_demo``,
    mocked Dhan adapter, and assert every Phase 1-12 panel is present."""
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "integration-test-token")

    user = await _seed_user(db_maker)
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    candles = _clean_candles(240)

    def _fake_fetch(
        request: HistoricalDataRequest, *args: Any, **kwargs: Any
    ) -> HistoricalDataResponse:
        return HistoricalDataResponse(
            candles=candles,
            request=request,
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            quality_warnings=[],
        )

    monkeypatch.setattr(
        "app.strategy_engine.api.backtest.fetch_historical_candles",
        _fake_fetch,
    )

    candles_request = {
        "symbol": "NIFTY",
        "timeframe": "1m",
        "from_date": "2026-04-01T09:30:00Z",
        "to_date": "2026-04-01T13:30:00Z",
    }

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={
                "candles_request": candles_request,
                "include_deviation_demo": True,
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Source + warnings — Phase C contract.
    assert body["candles_source"] == "dhan_historical"
    assert isinstance(body["data_quality_warnings"], list)

    # Phase 3 backtest ran on the mocked candles.
    backtest = body["backtest"]
    assert len(backtest["equityCurve"]) == 240
    assert backtest["totalTrades"] >= 0

    # Phase 4 reliability + trust score.
    reliability = body["reliability"]
    assert reliability is not None
    assert 0 <= reliability["trust_score"]["score"] <= 100
    assert reliability["walk_forward"] is not None
    assert reliability["out_of_sample"] is not None

    # Phase X coach.
    health = body["health_card"]
    assert health["overall_grade"] in {"A", "B", "C", "D", "F"}
    assert isinstance(health["metric_grades"], list)
    assert len(health["metric_grades"]) == 7

    # Phase 6 truth.
    truth = body["truth"]
    assert truth is not None
    assert 0 <= truth["truthScore"] <= 100

    # Phase 8 regime.
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

    # Phase 9 deviation (opted in).
    deviation = body["deviation"]
    assert deviation is not None
    assert deviation["status"] in {"normal", "watch", "warning", "critical"}

    # Phase 7 trade quality.
    trade_quality = body["trade_quality"]
    assert trade_quality is not None
    assert trade_quality["grade"] in {"A", "B", "C", "D", "F"}
    assert isinstance(trade_quality["components"], list)

    # Phase 12 version manifest — pinned at v1.0.0 for the seeded
    # ``ema`` indicator.
    manifest = body["version_manifest"]
    assert manifest is not None
    assert "ema" in manifest["indicators_used"]
    assert manifest["indicators_used"]["ema"]["version"] == "1.0.0"

    # Phase 7 diagnosis.
    diagnosis = body["diagnosis"]
    assert diagnosis is not None
    assert isinstance(diagnosis["problems"], list)


# ─── 503 when token missing ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_real_data_backtest_503_without_dhan_token(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token missing + ``candles_request`` set ⇒ locked Hinglish 503."""
    monkeypatch.delenv("DHAN_ACCESS_TOKEN", raising=False)

    user = await _seed_user(db_maker)
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={
                "candles_request": {
                    "symbol": "NIFTY",
                    "timeframe": "1m",
                    "from_date": "2026-04-01T09:30:00Z",
                    "to_date": "2026-04-01T11:30:00Z",
                }
            },
        )

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "Dhan token configure nahi hai" in detail
    # Token never appears in error messages.
    assert "integration-test-token" not in detail


# ─── Synthetic fallback regression ────────────────────────────────────


@pytest.mark.asyncio
async def test_real_data_backtest_falls_back_to_synthetic(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """No ``candles_request`` ⇒ synthetic fallback still works and the
    response declares it explicitly."""
    user = await _seed_user(db_maker)
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(f"/api/strategies/{strategy.id}/backtest", json={})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candles_source"] == "synthetic"
    assert len(body["backtest"]["equityCurve"]) == 120
