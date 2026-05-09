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


# ─── Real Dhan candle path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_backtest_503_when_dhan_token_missing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``candles_request`` set without ``DHAN_ACCESS_TOKEN`` produces a
    503 with the locked Hinglish error string."""
    monkeypatch.delenv("DHAN_ACCESS_TOKEN", raising=False)
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

    assert resp.status_code == 503
    assert "Dhan token configure nahi hai" in resp.json()["detail"]


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
async def test_post_backtest_422_when_dhan_quality_below_threshold(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pathologically gapped candle stream (quality_score < 40)
    short-circuits the pipeline with a 422 carrying the issue list."""
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")

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

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert "quality_score" in detail
    assert detail["quality_score"] < 40
    assert isinstance(detail["issues"], list)
    assert len(detail["issues"]) > 0


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
) -> None:
    """A successful backtest with reliability enabled must populate
    ``last_trust_score``, ``last_truth_score``, and ``last_scores_at``
    on the strategy row. The live-orders SafetyChain reads those
    columns with a 24h TTL — see ``live_orders.strategy_scores``.
    """
    user = await _seed_user(db_maker, "scores-cache@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    # Sanity: fresh strategy starts with NULL scores.
    async with db_maker() as s:
        row = await s.get(Strategy, strategy.id)
        assert row is not None
        assert row.last_trust_score is None
        assert row.last_truth_score is None
        assert row.last_scores_at is None

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/backtest",
            json={},  # synthetic candles; reliability defaults on.
        )
    assert resp.status_code == 200, resp.text

    body = resp.json()
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
