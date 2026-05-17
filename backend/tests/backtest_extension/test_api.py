"""API endpoint tests for the backtest extension.

Covers all three endpoints:

    POST /api/backtest                  — enqueue + cache hit / miss
    GET  /api/backtest/{run_id}         — owner-scoped fetch, 404, with metrics
    GET  /api/backtest/{run_id}/trades  — paginated trades, 409 on non-SUCCEEDED

Uses FastAPI TestClient against a minimal mounted app. Celery dispatch
is mocked so no real Redis or worker is needed.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_current_active_user
from app.backtest_extension import persistence
from app.backtest_extension.api import router as backtest_router
from app.backtest_extension.schemas import BacktestRunStatus
from app.db.models.user import User
from app.db.session import get_session
from tests.backtest_extension.conftest import make_request_payload


@pytest.fixture
def client(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> Iterator[TestClient]:
    """FastAPI TestClient with the backtest router mounted and deps overridden."""
    app = FastAPI()
    app.include_router(backtest_router)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    async def _override_user() -> User:
        return seed_user

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_active_user] = _override_user

    # Mock Celery dispatch — TestClient never spawns a worker
    with patch(
        "app.backtest_extension.celery_tasks.run_backtest_task.apply_async"
    ) as mock_dispatch:
        with TestClient(app) as test_client:
            test_client._mock_dispatch = mock_dispatch  # type: ignore[attr-defined]
            yield test_client


def _body(strategy_id: uuid.UUID, **overrides) -> dict:
    body = {
        "strategy_id": str(strategy_id),
        "symbol": "NIFTY",
        "timeframe": "5m",
        "start": datetime(2026, 3, 17, 3, 45, tzinfo=UTC).isoformat(),
        "end": datetime(2026, 5, 17, 10, 0, tzinfo=UTC).isoformat(),
        "initial_capital": 100000.0,
        "quantity": 1.0,
        "cost_settings": {
            "fixed_cost": 0.0,
            "percent_cost": 0.0,
            "slippage_percent": 0.0,
            "spread_percent": 0.0,
        },
        "ambiguity_mode": "conservative",
    }
    body.update(overrides)
    return body


# ─── POST /api/backtest ────────────────────────────────────────────────


def test_enqueue_cache_miss_returns_202_with_run_id(
    client: TestClient,
    seed_strategy,
) -> None:
    resp = client.post("/api/backtest", json=_body(seed_strategy.id))
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert uuid.UUID(body["run_id"])
    assert body["status"] == "PENDING"
    assert body["cached"] is False
    assert len(body["request_hash"]) == 64
    assert body["engine_version"] == "v1"
    # Celery dispatch was invoked
    assert client._mock_dispatch.call_count == 1  # type: ignore[attr-defined]


def test_enqueue_rejects_strategy_config(
    client: TestClient,
    seed_strategy,
) -> None:
    """Anonymous-config preview rejected per decision D8."""
    body = _body(seed_strategy.id)
    body["strategy_config"] = {"id": "anon"}
    body["strategy_id"] = None
    resp = client.post("/api/backtest", json=body)
    assert resp.status_code == 422
    assert "Anonymous-config" in resp.json()["detail"]


def test_enqueue_rejects_neither_strategy_id_nor_config(
    client: TestClient,
) -> None:
    body = _body(uuid.UUID(int=1))
    body["strategy_id"] = None
    resp = client.post("/api/backtest", json=body)
    assert resp.status_code == 422


def test_enqueue_rejects_unknown_strategy_id(client: TestClient) -> None:
    """Unknown strategy → 422 (not 404 — body validation tier)."""
    body = _body(uuid.uuid4())
    resp = client.post("/api/backtest", json=body)
    assert resp.status_code == 422
    assert "not found" in resp.json()["detail"].lower() or "not owned" in resp.json()["detail"].lower()


def test_enqueue_cache_hit_returns_200(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
    seed_strategy,
) -> None:
    """Two identical requests → first 202, second 200 with same run_id."""
    body = _body(seed_strategy.id)

    # First request — cache miss → 202 + PENDING
    resp1 = client.post("/api/backtest", json=body)
    assert resp1.status_code == 202
    run_id_first = resp1.json()["run_id"]
    request_hash = resp1.json()["request_hash"]

    # Promote first run to SUCCEEDED manually (the Celery worker is mocked)
    import asyncio

    async def _promote() -> None:
        async with db_session_maker() as session:
            await persistence.update_status(
                session,
                run_id=uuid.UUID(run_id_first),
                status=BacktestRunStatus.RUNNING,
            )
            await persistence.update_status(
                session,
                run_id=uuid.UUID(run_id_first),
                status=BacktestRunStatus.SUCCEEDED,
                completed_at=datetime.now(UTC),
            )
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_promote())

    # Second request — cache HIT → 200 + same run_id + cached=True
    resp2 = client.post("/api/backtest", json=body)
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["run_id"] == run_id_first
    assert body2["cached"] is True
    assert body2["status"] == "SUCCEEDED"
    assert body2["request_hash"] == request_hash


# ─── GET /api/backtest/{run_id} ────────────────────────────────────────


def test_get_run_happy_path(
    client: TestClient,
    seed_strategy,
) -> None:
    resp = client.post("/api/backtest", json=_body(seed_strategy.id))
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    detail = client.get(f"/api/backtest/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["id"] == run_id
    assert payload["status"] == "PENDING"
    assert payload["metrics"] is None


def test_get_run_unknown_id_returns_404(client: TestClient) -> None:
    resp = client.get(f"/api/backtest/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_run_other_user_returns_404(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """A run that exists but belongs to a different user returns 404,
    not 403 (anti-enumeration per decision D15)."""
    import asyncio

    other_user_id = uuid.uuid4()

    async def _create_other_user_run() -> uuid.UUID:
        # The other user needs to exist for the FK to satisfy, but we
        # only insert the run + a stub user.
        from app.db.models.user import User as UserModel

        async with db_session_maker() as session:
            other_user = UserModel(
                id=other_user_id,
                email="other@tradetri.test",
                password_hash="x",
                is_active=True,
            )
            session.add(other_user)
            await session.commit()

            run = await persistence.save_run(
                session,
                user_id=other_user_id,
                strategy_id=None,
                request_payload=make_request_payload(),
                request_hash="z" * 64,
                engine_version="v1",
            )
            await session.commit()
            return run.id

    run_id = asyncio.get_event_loop().run_until_complete(
        _create_other_user_run()
    )
    resp = client.get(f"/api/backtest/{run_id}")
    assert resp.status_code == 404


def test_get_run_with_metrics_after_promotion(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
    seed_strategy,
) -> None:
    """After a run is promoted to SUCCEEDED with metrics, GET returns them."""
    import asyncio
    import math

    from app.strategy_engine.backtest import BacktestResult, EquityPoint, Trade
    from app.strategy_engine.schema.strategy import Side

    resp = client.post("/api/backtest", json=_body(seed_strategy.id))
    assert resp.status_code == 202
    run_id = uuid.UUID(resp.json()["run_id"])

    fake_result = BacktestResult(
        total_pnl=250.0,
        total_return_percent=0.25,
        win_rate=0.66666,
        loss_rate=0.33333,
        total_trades=3,
        average_win=150.0,
        average_loss=50.0,
        largest_win=200.0,
        largest_loss=-50.0,
        max_drawdown=0.05,
        profit_factor=6.0,
        expectancy=83.3,
        equity_curve=[
            EquityPoint(
                timestamp=datetime(2026, 5, 1, 9, 30, tzinfo=UTC),
                equity=100000.0,
            )
        ],
        trades=[],
        warnings=[],
    )

    async def _promote() -> None:
        async with db_session_maker() as session:
            await persistence.update_status(
                session,
                run_id=run_id,
                status=BacktestRunStatus.RUNNING,
            )
            await persistence.save_metrics(
                session, run_id=run_id, result=fake_result
            )
            await persistence.update_status(
                session,
                run_id=run_id,
                status=BacktestRunStatus.SUCCEEDED,
                completed_at=datetime.now(UTC),
            )
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_promote())

    detail = client.get(f"/api/backtest/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "SUCCEEDED"
    assert payload["metrics"] is not None
    assert payload["metrics"]["total_trades"] == 3
    assert payload["metrics"]["total_pnl"] == 250.0


# ─── GET /api/backtest/{run_id}/trades ─────────────────────────────────


def test_get_trades_unknown_run_returns_404(client: TestClient) -> None:
    resp = client.get(f"/api/backtest/{uuid.uuid4()}/trades")
    assert resp.status_code == 404


def test_get_trades_pending_run_returns_409(
    client: TestClient,
    seed_strategy,
) -> None:
    """A PENDING run has no trades (decision D16: 409 not 200-with-empty)."""
    resp = client.post("/api/backtest", json=_body(seed_strategy.id))
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    trades = client.get(f"/api/backtest/{run_id}/trades")
    assert trades.status_code == 409


def test_get_trades_succeeded_run_returns_page(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
    seed_strategy,
) -> None:
    import asyncio

    from app.strategy_engine.backtest import Trade
    from app.strategy_engine.schema.strategy import Side

    resp = client.post("/api/backtest", json=_body(seed_strategy.id))
    run_id = uuid.UUID(resp.json()["run_id"])

    fake_trades = [
        Trade(
            entry_time=datetime(2026, 5, 1, 9, 30, tzinfo=UTC),
            exit_time=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
            side=Side.BUY,
            entry_price=22000.0 + i,
            exit_price=22100.0 + i,
            quantity=1.0,
            pnl=100.0,
            exit_reason="target_hit",
            entry_reasons=("ema",),
        )
        for i in range(5)
    ]

    async def _promote() -> None:
        async with db_session_maker() as session:
            await persistence.update_status(
                session, run_id=run_id, status=BacktestRunStatus.RUNNING
            )
            await persistence.save_trades(
                session, run_id=run_id, trades=fake_trades
            )
            await persistence.update_status(
                session,
                run_id=run_id,
                status=BacktestRunStatus.SUCCEEDED,
                completed_at=datetime.now(UTC),
            )
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_promote())

    page = client.get(f"/api/backtest/{run_id}/trades?page_size=3")
    assert page.status_code == 200
    payload = page.json()
    assert payload["run_id"] == str(run_id)
    assert len(payload["trades"]) == 3
    assert [t["trade_index"] for t in payload["trades"]] == [0, 1, 2]
    assert payload["has_more"] is True
    assert payload["next_cursor"] == 2

    # Next page
    page2 = client.get(
        f"/api/backtest/{run_id}/trades?page_size=3&cursor=2"
    )
    assert page2.status_code == 200
    payload2 = page2.json()
    assert [t["trade_index"] for t in payload2["trades"]] == [3, 4]
    assert payload2["has_more"] is False


def test_get_trades_page_size_validation(client: TestClient) -> None:
    """page_size > 1000 → 422 from Query validation."""
    resp = client.get(
        f"/api/backtest/{uuid.uuid4()}/trades?page_size=2000"
    )
    assert resp.status_code == 422
