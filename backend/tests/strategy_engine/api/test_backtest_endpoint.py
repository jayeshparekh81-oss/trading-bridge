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


async def _force_market_closed() -> bool:
    return False


@pytest.fixture(autouse=True)
def _default_market_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the market gate deterministic + Redis-free in unit tests: default
    to OPEN (→ synthetic). Real-path tests override ``_market_is_open`` to
    closed via monkeypatch."""

    async def _open() -> bool:
        return True

    monkeypatch.setattr("app.strategy_engine.api.backtest._market_is_open", _open)


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
        "trade_quality",
        "version_manifest",
        "diagnosis",
        "candles_source",
        "data_quality_warnings",
    }
    # Default body has no ``candles_request`` and no raw ``candles`` —
    # the synthetic fallback fires and reports itself as such.
    assert body["candles_source"] == "synthetic"
    assert body["data_quality_warnings"] == []
    # Phase 9 deviation is opt-in via ``include_deviation_demo``; the
    # default-body request leaves the field absent → ``None``.
    assert body["deviation"] is None

    # Phase 7 trade quality — always populated alongside a successful
    # backtest. Snake_case wire shape (no aliases on the Pydantic model).
    trade_quality = body["trade_quality"]
    assert trade_quality is not None
    for key in (
        "overall_score",
        "grade",
        "components",
        "overall_summary_hinglish",
        "strengths",
        "weaknesses",
    ):
        assert key in trade_quality, f"missing trade_quality key {key!r}"
    assert 0.0 <= trade_quality["overall_score"] <= 100.0
    assert trade_quality["grade"] in {"A", "B", "C", "D", "F"}
    assert isinstance(trade_quality["components"], list)
    assert isinstance(trade_quality["overall_summary_hinglish"], str)
    assert len(trade_quality["overall_summary_hinglish"]) > 0

    # Indicator versioning manifest — always populated. The sample
    # strategy uses one indicator (``ema_5`` of registry type ``ema``),
    # so the manifest pins exactly one entry at v1.0.0.
    manifest = body["version_manifest"]
    assert manifest is not None
    for key in (
        "backtest_id",
        "strategy_id",
        "indicators_used",
        "schema_version",
        "engine_version",
        "captured_at",
    ):
        assert key in manifest, f"missing manifest key {key!r}"
    assert manifest["strategy_id"] == str(strategy.id)
    assert "ema" in manifest["indicators_used"]
    ema_record = manifest["indicators_used"]["ema"]
    assert ema_record["version"] == "1.0.0"
    assert ema_record["formula_version"] == "f1"
    assert ema_record["deprecated"] is False

    # Phase 7 AI Doctor diagnosis — always populated alongside a
    # successful backtest. Wire keys are camelCase aliases (the model
    # uses ``populate_by_name=True``), matching the Truth section's
    # convention.
    diagnosis = body["diagnosis"]
    assert diagnosis is not None
    for key in (
        "diagnosisSummary",
        "problems",
        "recommendedFixes",
        "canAutoImprove",
        "improvedStrategyDraft",
    ):
        assert key in diagnosis, f"missing diagnosis key {key!r}"
    assert isinstance(diagnosis["problems"], list)
    assert isinstance(diagnosis["canAutoImprove"], bool)

    # Backtest section uses camelCase aliases.
    backtest = body["backtest"]
    for key in ("totalPnl", "totalReturnPercent", "winRate", "totalTrades", "equityCurve"):
        assert key in backtest, f"missing camelCase key {key!r}"
    assert isinstance(backtest["equityCurve"], list)
    assert len(backtest["equityCurve"]) == 720  # synthetic candle count (Queue SS)

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


# ─── Real Dhan candle path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_backtest_falls_back_to_synthetic_when_dhan_token_missing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Market CLOSED + ``candles_request`` + no ``DHAN_ACCESS_TOKEN``: the
    real fetch can't run, so the endpoint GRACEFULLY falls back to synthetic
    (HTTP 200) instead of the old hard 503."""
    monkeypatch.delenv("DHAN_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(
        "app.strategy_engine.api.backtest._market_is_open", _force_market_closed
    )
    user = await _seed_user(db_maker, "no-token@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    candles_request = {
        "symbol": "NIFTY",
        "timeframe": "1m",
        "from_date": "2026-04-01T09:30:00Z",
        "to_date": "2026-04-02T15:30:00Z",
    }

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles_request": candles_request},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candles_source"] == "synthetic"
    assert any(
        "Real market data unavailable" in w for w in body["data_quality_warnings"]
    )


@pytest.mark.asyncio
async def test_post_backtest_uses_dhan_candles_when_request_supplied(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the adapter is mocked to return clean candles, the
    backtest pipeline runs on them and reports
    ``candles_source="dhan_historical"``."""
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(
        "app.strategy_engine.api.backtest._market_is_open", _force_market_closed
    )

    user = await _seed_user(db_maker, "dhan-happy@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    candles_request = {
        "symbol": "NIFTY",
        "timeframe": "1m",
        "from_date": "2026-04-01T09:30:00Z",
        "to_date": "2026-04-01T11:30:00Z",
    }

    # Build a clean 120-bar 1-minute fake response in-process.
    from datetime import UTC, datetime, timedelta

    from app.strategy_engine.data_provider.models import (
        HistoricalDataRequest,
        HistoricalDataResponse,
    )
    from app.strategy_engine.schema.ohlcv import Candle

    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    fake_candles = [
        Candle(
            timestamp=base + timedelta(minutes=i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1_000.0,
        )
        for i in range(120)
    ]

    def _fake_fetch(
        request: HistoricalDataRequest, *args: Any, **kwargs: Any
    ) -> HistoricalDataResponse:
        return HistoricalDataResponse(
            candles=fake_candles,
            request=request,
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            quality_warnings=[],
        )

    monkeypatch.setattr(
        "app.strategy_engine.api.backtest.fetch_historical_candles",
        _fake_fetch,
    )

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles_request": candles_request},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candles_source"] == "dhan_historical"
    assert body["data_quality_warnings"] == []
    # Backtest ran end-to-end on the supplied 120 bars.
    assert len(body["backtest"]["equityCurve"]) == 120


@pytest.mark.asyncio
async def test_post_backtest_falls_back_to_synthetic_when_dhan_quality_low(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Market CLOSED + a pathologically gapped candle stream (quality_score
    < 40): the quality gate trips, and instead of the old hard 422 the
    endpoint GRACEFULLY falls back to synthetic (HTTP 200)."""
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(
        "app.strategy_engine.api.backtest._market_is_open", _force_market_closed
    )

    user = await _seed_user(db_maker, "dhan-bad@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    candles_request = {
        "symbol": "NIFTY",
        "timeframe": "1m",
        "from_date": "2026-04-01T09:30:00Z",
        "to_date": "2026-04-01T15:30:00Z",
    }

    from datetime import UTC, datetime, timedelta

    from app.strategy_engine.data_provider.models import (
        HistoricalDataRequest,
        HistoricalDataResponse,
    )
    from app.strategy_engine.schema.ohlcv import Candle

    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    # Ten candles spaced two hours apart on a 1-minute timeframe →
    # nine `missing_candle` critical issues → quality_score ~10
    # (well below the 40-point safety floor).
    bad_candles = [
        Candle(
            timestamp=base + timedelta(hours=2 * i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1_000.0,
        )
        for i in range(10)
    ]

    def _fake_fetch(
        request: HistoricalDataRequest, *args: Any, **kwargs: Any
    ) -> HistoricalDataResponse:
        return HistoricalDataResponse(
            candles=bad_candles,
            request=request,
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            quality_warnings=["large gap detected"],
        )

    monkeypatch.setattr(
        "app.strategy_engine.api.backtest.fetch_historical_candles",
        _fake_fetch,
    )

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles_request": candles_request},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candles_source"] == "synthetic"
    assert any(
        "Real market data unavailable" in w for w in body["data_quality_warnings"]
    )


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


# ─── Migration 012: cached scores writeback ───────────────────────────


@pytest.mark.asyncio
async def test_backtest_caches_trust_and_truth_scores_on_strategy_row(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful backtest **over real Dhan candles** with reliability
    enabled must populate ``last_trust_score``, ``last_truth_score``,
    and ``last_scores_at`` on the strategy row. The live-orders
    SafetyChain reads those columns with a 24h TTL — see
    ``live_orders.strategy_scores``.

    NOTE: pre-guard this test asserted the same write on a synthetic
    run (``json={}``). The new score-write guard at backtest.py:403
    requires ``candles_source == "dhan_historical"``, so this test now
    drives the real-data path via the same mocked Dhan adapter that
    ``test_post_backtest_uses_dhan_candles_when_request_supplied``
    uses. The synthetic no-write path is asserted by its own dedicated
    test below.
    """
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(
        "app.strategy_engine.api.backtest._market_is_open", _force_market_closed
    )

    user = await _seed_user(db_maker, "scores-cache@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    # Sanity: fresh strategy starts with NULL scores.
    async with db_maker() as s:
        row = await s.get(Strategy, strategy.id)
        assert row is not None
        assert row.last_trust_score is None
        assert row.last_truth_score is None
        assert row.last_scores_at is None

    # Build a clean 120-bar 1-minute fake Dhan response.
    from datetime import UTC, datetime, timedelta

    from app.strategy_engine.data_provider.models import (
        HistoricalDataRequest,
        HistoricalDataResponse,
    )
    from app.strategy_engine.schema.ohlcv import Candle

    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    fake_candles = [
        Candle(
            timestamp=base + timedelta(minutes=i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1_000.0,
        )
        for i in range(120)
    ]

    def _fake_fetch(
        request: HistoricalDataRequest, *args: Any, **kwargs: Any
    ) -> HistoricalDataResponse:
        return HistoricalDataResponse(
            candles=fake_candles,
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
        "to_date": "2026-04-01T11:30:00Z",
    }

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles_request": candles_request},
        )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["candles_source"] == "dhan_historical"
    assert body["reliability"] is not None
    assert body["truth"] is not None

    # The endpoint should have written the scores back to the row.
    async with db_maker() as s:
        row = await s.get(Strategy, strategy.id)
        assert row is not None
        assert row.last_trust_score is not None
        assert row.last_truth_score is not None
        assert row.last_scores_at is not None

        # Persisted values match the response payload.
        expected_trust = body["reliability"]["trust_score"]["score"]
        expected_truth = body["truth"]["truthScore"]
        assert float(row.last_trust_score) == float(expected_trust)
        assert float(row.last_truth_score) == float(expected_truth)


# ─── Score-write guard: synthetic runs MUST NOT touch the cached scores ─


_SENTINEL_TRUST = "77.00"
_SENTINEL_TRUTH = "66.00"


async def _seed_sentinel_scores(
    db_maker: async_sessionmaker[AsyncSession], strategy_id: uuid.UUID
) -> "tuple[Any, Any, Any]":
    """Pre-populate the three score columns with known sentinel values so
    a missed write is detected as "row unchanged" rather than "row
    populated from NULL". Returns the (trust, truth, computed_at)
    tuple the test compares against after the request."""
    from datetime import UTC, datetime
    from decimal import Decimal

    pre_seeded_at = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    async with db_maker() as s:
        row = await s.get(Strategy, strategy_id)
        assert row is not None
        row.last_trust_score = Decimal(_SENTINEL_TRUST)
        row.last_truth_score = Decimal(_SENTINEL_TRUTH)
        row.last_scores_at = pre_seeded_at
        await s.commit()
    return Decimal(_SENTINEL_TRUST), Decimal(_SENTINEL_TRUTH), pre_seeded_at


async def _assert_sentinel_unchanged(
    db_maker: async_sessionmaker[AsyncSession],
    strategy_id: uuid.UUID,
    expected_trust: Any,
    expected_truth: Any,
    expected_at: Any,
) -> None:
    """Re-read the strategy row and assert the three score columns are
    exactly the sentinel values. A drift means the synthetic-write
    guard at backtest.py:403 has regressed.

    SQLite stores ``DateTime(timezone=True)`` as naive even when the
    inserted value was tz-aware, so we coerce the persisted timestamp
    to UTC before comparing — mirrors ``strategy_scores.py:91-96``."""
    from datetime import UTC

    async with db_maker() as s:
        row = await s.get(Strategy, strategy_id)
        assert row is not None
        assert row.last_trust_score == expected_trust
        assert row.last_truth_score == expected_truth
        persisted_at = row.last_scores_at
        assert persisted_at is not None
        if persisted_at.tzinfo is None:
            persisted_at = persisted_at.replace(tzinfo=UTC)
        assert persisted_at == expected_at


@pytest.mark.asyncio
async def test_synthetic_default_path_does_not_write_scores(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """The default body (no ``candles_request``, no raw ``candles``)
    runs on the synthetic fallback. Pre-guard, this still wrote scores
    derived from synthetic data onto the strategy row; post-guard, the
    write is gated on ``candles_source == "dhan_historical"`` and the
    cached SafetyChain scores stay at their prior values."""
    user = await _seed_user(db_maker, "no-write-default@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)
    trust, truth, at = await _seed_sentinel_scores(db_maker, strategy.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["candles_source"] == "synthetic"

    await _assert_sentinel_unchanged(db_maker, strategy.id, trust, truth, at)


@pytest.mark.asyncio
async def test_raw_candles_injection_does_not_write_scores(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Raw ``candles`` injection (the existing test-suite path) is
    classified ``synthetic`` by ``_resolve_candles`` because the data
    didn't come from Dhan. The guard must therefore skip the score
    write here too."""
    from datetime import UTC, datetime, timedelta

    user = await _seed_user(db_maker, "no-write-raw@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)
    trust, truth, at = await _seed_sentinel_scores(db_maker, strategy.id)

    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    raw_candles = [
        {
            "timestamp": (base + timedelta(minutes=i)).isoformat(),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1_000.0,
        }
        for i in range(120)
    ]

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles": raw_candles},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["candles_source"] == "synthetic"

    await _assert_sentinel_unchanged(db_maker, strategy.id, trust, truth, at)


@pytest.mark.asyncio
async def test_market_hours_forced_synthetic_does_not_write_scores(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Market OPEN forces ``_resolve_candles`` into the synthetic branch
    regardless of any ``candles_request`` — the safety gate prevents
    Dhan fetches contending with live order placement. The score-write
    guard must skip the cache update on this path so an intraday page
    open does not corrupt the live BSE-LTD SafetyChain gate."""
    # NOTE: the autouse ``_default_market_open`` fixture already sets the
    # market to OPEN, but this test pins the intent explicitly for the
    # reader.
    async def _open() -> bool:
        return True

    monkeypatch.setattr("app.strategy_engine.api.backtest._market_is_open", _open)
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")

    user = await _seed_user(db_maker, "no-write-market-open@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)
    trust, truth, at = await _seed_sentinel_scores(db_maker, strategy.id)

    candles_request = {
        "symbol": "NIFTY",
        "timeframe": "1m",
        "from_date": "2026-04-01T09:30:00Z",
        "to_date": "2026-04-01T11:30:00Z",
    }

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles_request": candles_request},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["candles_source"] == "synthetic"

    await _assert_sentinel_unchanged(db_maker, strategy.id, trust, truth, at)


@pytest.mark.asyncio
async def test_dhan_outage_graceful_fallback_does_not_write_scores(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Market CLOSED + explicit ``candles_request`` + Dhan adapter
    raises: ``_resolve_candles`` GRACEFULLY falls back to synthetic
    with a ``"Real market data unavailable"`` warning. The score-write
    guard must skip the cache update on this path — the gracefully-
    handled 200 response is the very case that, pre-guard, would have
    silently rewritten the live row's scores from placeholder data."""
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(
        "app.strategy_engine.api.backtest._market_is_open", _force_market_closed
    )

    from app.strategy_engine.data_provider.models import HistoricalDataRequest

    def _raise(request: HistoricalDataRequest, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated Dhan outage")

    monkeypatch.setattr(
        "app.strategy_engine.api.backtest.fetch_historical_candles",
        _raise,
    )

    user = await _seed_user(db_maker, "no-write-outage@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)
    trust, truth, at = await _seed_sentinel_scores(db_maker, strategy.id)

    candles_request = {
        "symbol": "NIFTY",
        "timeframe": "1m",
        "from_date": "2026-04-01T09:30:00Z",
        "to_date": "2026-04-01T11:30:00Z",
    }

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles_request": candles_request},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candles_source"] == "synthetic"
    assert any(
        "Real market data unavailable" in w for w in body["data_quality_warnings"]
    )

    await _assert_sentinel_unchanged(db_maker, strategy.id, trust, truth, at)


@pytest.mark.asyncio
async def test_dhan_historical_success_writes_scores_over_sentinel(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard MUST allow the score write when the run was over real
    Dhan candles. Pre-seed the row with sentinel values; assert all
    three columns moved off the sentinel after a ``dhan_historical``
    run, and that the persisted scores match the response payload."""
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(
        "app.strategy_engine.api.backtest._market_is_open", _force_market_closed
    )

    user = await _seed_user(db_maker, "write-dhan@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)
    sentinel_trust, sentinel_truth, sentinel_at = await _seed_sentinel_scores(
        db_maker, strategy.id
    )

    from datetime import UTC, datetime, timedelta

    from app.strategy_engine.data_provider.models import (
        HistoricalDataRequest,
        HistoricalDataResponse,
    )
    from app.strategy_engine.schema.ohlcv import Candle

    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    fake_candles = [
        Candle(
            timestamp=base + timedelta(minutes=i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1_000.0,
        )
        for i in range(120)
    ]

    def _fake_fetch(
        request: HistoricalDataRequest, *args: Any, **kwargs: Any
    ) -> HistoricalDataResponse:
        return HistoricalDataResponse(
            candles=fake_candles,
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
        "to_date": "2026-04-01T11:30:00Z",
    }

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"candles_request": candles_request},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candles_source"] == "dhan_historical"

    # All three columns moved off the sentinel; persisted values align
    # with the response payload.
    async with db_maker() as s:
        row = await s.get(Strategy, strategy.id)
        assert row is not None
        assert row.last_trust_score != sentinel_trust
        assert row.last_truth_score != sentinel_truth
        assert row.last_scores_at != sentinel_at
        assert float(row.last_trust_score) == float(
            body["reliability"]["trust_score"]["score"]
        )
        assert float(row.last_truth_score) == float(body["truth"]["truthScore"])


@pytest.mark.asyncio
async def test_backtest_without_reliability_does_not_clobber_cached_scores(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """When the caller opts out of reliability, the SafetyChain's
    cached scores must NOT be overwritten with NULL. A previously-
    fresh score should survive a partial backtest run."""
    from datetime import UTC, datetime
    from decimal import Decimal

    user = await _seed_user(db_maker, "scores-preserve@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    # Pre-seed a known-fresh score pair.
    pre_seeded_at = datetime.now(UTC)
    async with db_maker() as s:
        row = await s.get(Strategy, strategy.id)
        assert row is not None
        row.last_trust_score = Decimal("88.00")
        row.last_truth_score = Decimal("72.00")
        row.last_scores_at = pre_seeded_at
        await s.commit()

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"include_reliability": False},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reliability"] is None

    # Cached scores should be untouched.
    async with db_maker() as s:
        row = await s.get(Strategy, strategy.id)
        assert row is not None
        assert row.last_trust_score == Decimal("88.00")
        assert row.last_truth_score == Decimal("72.00")
        assert row.last_scores_at is not None


# ─── Robustness Test Controls (Expert Builder) ────────────────────────


@pytest.mark.asyncio
async def test_backtest_walk_forward_disabled_returns_null_walk_forward(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """``walk_forward_enabled=false`` causes the reliability report's
    ``walk_forward`` field to be ``None`` in the response — the rest
    of the report (backtest, oos, trust score) is unaffected."""
    user = await _seed_user(db_maker, "wf-disabled@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"walk_forward_enabled": False},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reliability"] is not None
    assert body["reliability"]["walk_forward"] is None
    # OOS still ran (only walk-forward was gated).
    assert body["reliability"]["out_of_sample"] is not None


@pytest.mark.asyncio
async def test_backtest_walk_forward_windows_three_produces_two_test_segments(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """``walk_forward_windows=3`` overrides the default 5; the
    response's walk-forward report carries exactly N-1 = 2 test
    segments (first segment is in-sample only)."""
    user = await _seed_user(db_maker, "wf-three@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"walk_forward_windows": 3},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reliability"] is not None
    wf = body["reliability"]["walk_forward"]
    assert wf is not None
    # Phase 4B convention: ``num_windows`` partitions produce
    # ``num_windows - 1`` test results (the first segment is the
    # initial training fold).
    assert len(wf["windows"]) == 2


@pytest.mark.asyncio
async def test_backtest_sensitivity_enabled_via_new_field_populates_report(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """The new ``sensitivity_enabled`` field flips the run on, same
    as the legacy ``include_sensitivity`` boolean — pinned so the
    spec's wire vocabulary works without callers also setting the
    legacy flag."""
    user = await _seed_user(db_maker, "sens-enabled@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={"sensitivity_enabled": True},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reliability"] is not None
    assert body["reliability"]["sensitivity"] is not None


# ─── Audit emission — pin the Phase 11 wiring ────────────────────────


@pytest.mark.asyncio
async def test_backtest_emits_backtest_run_audit_event_on_success(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """A successful backtest emits exactly one ``backtest_run``
    audit event with success=True and the headline metadata
    (total_trades, candles_source, trust_score, truth_score)."""
    from app.strategy_engine.audit import clear_audit_log, query_events

    clear_audit_log()

    user = await _seed_user(db_maker, "audit-backtest@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={},
        )
    assert resp.status_code == 200, resp.text

    events = query_events(
        user_id=user.id,
        strategy_id=strategy.id,
        event_type="backtest_run",
    )
    assert events.filtered_count >= 1
    meta = events.events[-1].metadata
    assert meta.get("success") is True
    assert "total_trades" in meta
    assert "candles_source" in meta
    assert "trust_score" in meta
    assert "truth_score" in meta
