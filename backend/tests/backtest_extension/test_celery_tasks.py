"""Celery task tests for the backtest extension.

Mocks ``app.strategy_engine.backtest.run_backtest`` so the engine
itself never runs. Drives the state machine end-to-end through the
async worker body (``_run_backtest_async``), verifying:

    PENDING → RUNNING → SUCCEEDED  on happy path
    PENDING → RUNNING → FAILED     on engine raise
    PENDING → RUNNING → FAILED     on strategy-missing
    duplicate dispatch is a no-op  (status==RUNNING/SUCCEEDED already)
    unknown run_id is a no-op      (logged, returns "UNKNOWN")
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backtest_extension import celery_tasks, persistence
from app.backtest_extension.schemas import BacktestRunStatus
from app.db.models.user import User
from app.strategy_engine.backtest import BacktestResult, EquityPoint, Trade
from app.strategy_engine.schema.strategy import Side
from tests.backtest_extension.conftest import make_request_payload


# ─── Fixture: a fake engine result (mirrors test_persistence helpers) ──


def _fake_result(*, total_trades: int = 2) -> BacktestResult:
    trades = [
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
        for i in range(total_trades)
    ]
    equity = [
        EquityPoint(
            timestamp=datetime(2026, 5, 1, 9, 30, tzinfo=UTC) + timedelta(minutes=5 * i),
            equity=100_000.0 + i * 100.0,
        )
        for i in range(3)
    ]
    return BacktestResult(
        total_pnl=100.0 * total_trades,
        total_return_percent=0.1 * total_trades,
        win_rate=1.0,
        loss_rate=0.0,
        total_trades=total_trades,
        average_win=100.0,
        average_loss=0.0,
        largest_win=100.0,
        largest_loss=0.0,
        max_drawdown=0.0,
        profit_factor=math.inf,
        expectancy=100.0,
        equity_curve=equity,
        trades=trades,
        warnings=[],
    )


@pytest.fixture
def patched_sessionmaker(
    db_session_maker: async_sessionmaker[AsyncSession],
):
    """Patch ``get_sessionmaker`` so the Celery worker uses the in-memory test DB."""
    with patch(
        "app.backtest_extension.celery_tasks.get_sessionmaker",
        return_value=db_session_maker,
    ):
        yield db_session_maker


# ─── Happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_backtest_async_succeeds(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
    seed_strategy,
) -> None:
    """PENDING → RUNNING → SUCCEEDED; trades + metrics persisted."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=make_request_payload(),
            request_hash="a" * 64,
            engine_version="v1",
        )
        await session.commit()

    with patch(
        "app.backtest_extension.celery_tasks.run_backtest",
        return_value=_fake_result(total_trades=2),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "SUCCEEDED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert final is not None
        assert final.status == "SUCCEEDED"
        assert final.completed_at is not None
        assert final.error_json is None
        assert final.metrics is not None
        assert final.metrics.total_trades == 2

        # Trades persisted with monotonic trade_index
        page, _, _ = await persistence.get_trades_page(
            session, run_id=run.id, cursor=None, page_size=10
        )
        assert len(page) == 2
        assert [r.trade_index for r in page] == [0, 1]


# ─── Engine raises (RuntimeError) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_run_backtest_async_failed_on_engine_raise(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
    seed_strategy,
) -> None:
    """Engine RuntimeError → FAILED with populated error_json."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=make_request_payload(),
            request_hash="b" * 64,
            engine_version="v1",
        )
        await session.commit()

    with patch(
        "app.backtest_extension.celery_tasks.run_backtest",
        side_effect=RuntimeError("engine kaboom"),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "FAILED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert final is not None
        assert final.status == "FAILED"
        assert final.completed_at is not None
        assert final.error_json is not None
        assert final.error_json["type"] == "RuntimeError"
        assert "engine kaboom" in final.error_json["message"]
        # No trades / no metrics persisted on the failed path
        assert final.metrics is None


# ─── Engine raises (ValueError) — Pydantic-style bad-input case ───────


@pytest.mark.asyncio
async def test_run_backtest_async_failed_on_value_error(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
    seed_strategy,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=make_request_payload(),
            request_hash="c" * 64,
            engine_version="v1",
        )
        await session.commit()

    with patch(
        "app.backtest_extension.celery_tasks.run_backtest",
        side_effect=ValueError("candle list too short"),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "FAILED"
    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.error_json["type"] == "ValueError"


# ─── Strategy-missing failure path ─────────────────────────────────────


@pytest.mark.asyncio
async def test_run_backtest_async_failed_when_strategy_id_unknown(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
) -> None:
    """A run pointing at a non-existent strategy_id lands in FAILED."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=uuid.uuid4(),  # never-existed strategy
            request_payload=make_request_payload(),
            request_hash="d" * 64,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "FAILED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "FAILED"
        assert final.error_json["type"] == "StrategyPayloadResolutionError"


@pytest.mark.asyncio
async def test_run_backtest_async_failed_when_strategy_id_null(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
) -> None:
    """A run with strategy_id=None (anonymous-config attempt) lands in FAILED
    per decision D8."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="e" * 64,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "FAILED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "FAILED"
        assert "Anonymous-config" in final.error_json["message"]


@pytest.mark.asyncio
async def test_run_backtest_async_failed_when_strategy_has_no_dsl(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
) -> None:
    """A Strategy with strategy_json=None (cloned-from-template) lands in FAILED."""
    from app.db.models.strategy import Strategy

    async with db_session_maker() as session:
        strategy = Strategy(
            user_id=seed_user.id,
            name="No-DSL clone",
            is_active=True,
            strategy_json=None,
        )
        session.add(strategy)
        await session.commit()
        await session.refresh(strategy)

        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=strategy.id,
            request_payload=make_request_payload(),
            request_hash="f" * 64,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "FAILED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert "no DSL configured" in final.error_json["message"]


# ─── Duplicate-dispatch idempotency ─────────────────────────────────────


@pytest.mark.asyncio
async def test_run_backtest_async_idempotent_when_already_succeeded(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
    seed_strategy,
) -> None:
    """A duplicate dispatch of a SUCCEEDED run is a no-op."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=make_request_payload(),
            request_hash="9" * 64,
            engine_version="v1",
        )
        await persistence.update_status(
            session, run_id=run.id, status=BacktestRunStatus.RUNNING
        )
        await persistence.update_status(
            session,
            run_id=run.id,
            status=BacktestRunStatus.SUCCEEDED,
            completed_at=datetime.now(UTC),
        )
        await session.commit()

    # No engine patch needed — the duplicate-dispatch guard returns
    # before any engine call.
    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "SUCCEEDED"

    # Status unchanged
    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_run_backtest_async_idempotent_when_already_running(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
    seed_strategy,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=make_request_payload(),
            request_hash="8" * 64,
            engine_version="v1",
        )
        await persistence.update_status(
            session, run_id=run.id, status=BacktestRunStatus.RUNNING
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "RUNNING"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "RUNNING"


@pytest.mark.asyncio
async def test_run_backtest_async_unknown_run_id_returns_unknown(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
) -> None:
    """An unknown run_id (never persisted) yields UNKNOWN, not an exception."""
    result = await celery_tasks._run_backtest_async(uuid.uuid4())
    assert result == "UNKNOWN"


# ─── _build_error_payload ──────────────────────────────────────────────


def test_build_error_payload_captures_top_frame() -> None:
    try:
        raise ValueError("ramen noodle slippage")
    except ValueError as e:
        payload = celery_tasks._build_error_payload(e)
    assert payload["type"] == "ValueError"
    assert "ramen noodle slippage" in payload["message"]
    assert "File " in payload["traceback_first_line"]


def test_build_error_payload_truncates_long_messages() -> None:
    big = "x" * 5000
    try:
        raise RuntimeError(big)
    except RuntimeError as e:
        payload = celery_tasks._build_error_payload(e)
    assert len(payload["message"]) == 1024


# ─── BACKTEST_QUEUE constant ───────────────────────────────────────────


def test_backtest_queue_constant_exposed() -> None:
    """The constant is exported for future Day-5 dedicated-worker wiring."""
    assert celery_tasks.BACKTEST_QUEUE == "backtest"


def test_run_backtest_task_is_registered_as_celery_task() -> None:
    """@shared_task wrapping verified via the wrapped function's signature."""
    # @shared_task wraps the function — calling .name on the wrapper
    # returns the registered task name. Use that as proof of registration.
    assert hasattr(celery_tasks.run_backtest_task, "name")
    assert (
        celery_tasks.run_backtest_task.name
        == "app.backtest_extension.run_backtest_task"
    )
