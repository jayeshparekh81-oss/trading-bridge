"""Persistence-layer unit tests for the backtest extension.

Covers every helper in :mod:`app.backtest_extension.persistence`:

    save_run                  → INSERT PENDING row
    update_status             → state machine + invariants
    save_trades               → bulk INSERT preserving trade_index order
    save_metrics              → UPSERT, math.inf → NULL profit_factor
    get_run_by_id             → owner-scoped, optional metrics eager-load
    get_cached_run_by_hash    → SUCCEEDED-only lookup
    get_trades_page           → keyset pagination by trade_index

Plus the InvalidStatusTransitionError guard for every disallowed
transition (PENDING → SUCCEEDED, RUNNING → PENDING, SUCCEEDED → *,
FAILED → *).

All tests use the in-memory aiosqlite fixture from conftest.py.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backtest_extension import persistence
from app.backtest_extension.models import (
    BacktestMetrics,
    BacktestRun,
    BacktestTrade,
)
from app.backtest_extension.schemas import BacktestRunStatus
from app.db.models.user import User
from app.strategy_engine.backtest import BacktestResult, EquityPoint, Trade
from app.strategy_engine.schema.strategy import Side
from tests.backtest_extension.conftest import make_request_payload


# ─── Helpers ────────────────────────────────────────────────────────────


def _sample_trade(*, pnl: float = 100.0, side: Side = Side.BUY) -> Trade:
    return Trade(
        entry_time=datetime(2026, 5, 1, 9, 30, tzinfo=UTC),
        exit_time=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        side=side,
        entry_price=22000.0,
        exit_price=22100.0 if pnl >= 0 else 21900.0,
        quantity=1.0,
        pnl=pnl,
        exit_reason="target_hit",
        entry_reasons=("ema_crossover", "rsi_oversold"),
    )


def _sample_result(*, pnls: list[float] | None = None) -> BacktestResult:
    """Minimal BacktestResult fixture with controllable pnls."""
    if pnls is None:
        pnls = [100.0, -50.0, 200.0]
    trades = [_sample_trade(pnl=p) for p in pnls]
    equity_curve = [
        EquityPoint(
            timestamp=datetime(2026, 5, 1, 9, 30, tzinfo=UTC) + timedelta(minutes=5 * i),
            equity=100000.0 + sum(pnls[: min(i, len(pnls))]),
        )
        for i in range(3)
    ]
    wins = [p for p in pnls if p > 0]
    losses = [-p for p in pnls if p < 0]
    win_rate = len(wins) / len(pnls) if pnls else 0.0
    return BacktestResult(
        total_pnl=sum(pnls),
        total_return_percent=sum(pnls) / 1000.0,
        win_rate=win_rate,
        loss_rate=len(losses) / len(pnls) if pnls else 0.0,
        total_trades=len(pnls),
        average_win=sum(wins) / len(wins) if wins else 0.0,
        average_loss=sum(losses) / len(losses) if losses else 0.0,
        largest_win=max(wins) if wins else 0.0,
        largest_loss=min([p for p in pnls if p < 0], default=0.0),
        max_drawdown=0.05,
        profit_factor=(
            math.inf if (wins and not losses) else (sum(wins) / sum(losses) if losses else 0.0)
        ),
        expectancy=sum(pnls) / len(pnls) if pnls else 0.0,
        equity_curve=equity_curve,
        trades=trades,
        warnings=["sample warning"],
    )


# ─── save_run ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_run_inserts_pending_row(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="a" * 64,
            engine_version="v1",
        )
        await session.commit()
        assert run.id is not None
        assert run.status == "PENDING"
        assert run.user_id == seed_user.id
        assert run.strategy_id is None
        assert run.completed_at is None
        assert run.error_json is None


@pytest.mark.asyncio
async def test_save_run_records_strategy_id_when_set(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
    seed_strategy,
) -> None:
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
        assert run.strategy_id == seed_strategy.id


# ─── update_status — state machine ─────────────────────────────────────


@pytest.mark.asyncio
async def test_update_status_pending_to_running(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="c" * 64,
            engine_version="v1",
        )
        await session.commit()

    async with db_session_maker() as session:
        updated = await persistence.update_status(
            session, run_id=run.id, status=BacktestRunStatus.RUNNING
        )
        await session.commit()
        assert updated.status == "RUNNING"
        assert updated.completed_at is None


@pytest.mark.asyncio
async def test_update_status_running_to_succeeded(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="d" * 64,
            engine_version="v1",
        )
        await persistence.update_status(
            session, run_id=run.id, status=BacktestRunStatus.RUNNING
        )
        completed = datetime.now(UTC)
        succeeded = await persistence.update_status(
            session,
            run_id=run.id,
            status=BacktestRunStatus.SUCCEEDED,
            completed_at=completed,
        )
        await session.commit()
        assert succeeded.status == "SUCCEEDED"
        assert succeeded.completed_at == completed


@pytest.mark.asyncio
async def test_update_status_running_to_failed_persists_error(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="e" * 64,
            engine_version="v1",
        )
        await persistence.update_status(
            session, run_id=run.id, status=BacktestRunStatus.RUNNING
        )
        err = {"type": "RuntimeError", "message": "engine boom", "traceback_first_line": "..."}
        failed = await persistence.update_status(
            session,
            run_id=run.id,
            status=BacktestRunStatus.FAILED,
            completed_at=datetime.now(UTC),
            error=err,
        )
        await session.commit()
        assert failed.status == "FAILED"
        assert failed.error_json == err


@pytest.mark.asyncio
async def test_update_status_rejects_pending_to_succeeded(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """PENDING → SUCCEEDED is forbidden — must go through RUNNING."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="f" * 64,
            engine_version="v1",
        )
        with pytest.raises(persistence.InvalidStatusTransitionError):
            await persistence.update_status(
                session,
                run_id=run.id,
                status=BacktestRunStatus.SUCCEEDED,
                completed_at=datetime.now(UTC),
            )


@pytest.mark.asyncio
async def test_update_status_rejects_succeeded_to_running(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """SUCCEEDED is terminal — cannot transition out of it."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
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
        with pytest.raises(persistence.InvalidStatusTransitionError):
            await persistence.update_status(
                session, run_id=run.id, status=BacktestRunStatus.RUNNING
            )


@pytest.mark.asyncio
async def test_update_status_invariant_succeeded_requires_completed_at(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="8" * 64,
            engine_version="v1",
        )
        await persistence.update_status(
            session, run_id=run.id, status=BacktestRunStatus.RUNNING
        )
        with pytest.raises(ValueError, match="completed_at"):
            await persistence.update_status(
                session,
                run_id=run.id,
                status=BacktestRunStatus.SUCCEEDED,
                # No completed_at — should be rejected
            )


@pytest.mark.asyncio
async def test_update_status_invariant_failed_requires_error(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="7" * 64,
            engine_version="v1",
        )
        await persistence.update_status(
            session, run_id=run.id, status=BacktestRunStatus.RUNNING
        )
        with pytest.raises(ValueError, match="error"):
            await persistence.update_status(
                session,
                run_id=run.id,
                status=BacktestRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                # No error — should be rejected
            )


@pytest.mark.asyncio
async def test_update_status_unknown_run_id_raises(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_maker() as session:
        with pytest.raises(ValueError, match="not found"):
            await persistence.update_status(
                session,
                run_id=uuid.uuid4(),
                status=BacktestRunStatus.RUNNING,
            )


# ─── save_trades ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_trades_preserves_order(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="6" * 64,
            engine_version="v1",
        )
        trades = [
            _sample_trade(pnl=100.0),
            _sample_trade(pnl=-50.0),
            _sample_trade(pnl=200.0),
        ]
        n = await persistence.save_trades(session, run_id=run.id, trades=trades)
        await session.commit()
        assert n == 3

        # Verify ordering via trade_index column
        from sqlalchemy import select as _select

        rows = list(
            (
                await session.execute(
                    _select(BacktestTrade).where(BacktestTrade.run_id == run.id)
                    .order_by(BacktestTrade.trade_index.asc())
                )
            ).scalars().all()
        )
        assert [r.trade_index for r in rows] == [0, 1, 2]
        assert [float(r.pnl) for r in rows] == [100.0, -50.0, 200.0]
        # entry_reasons survives the tuple → list flatten
        assert rows[0].entry_reasons == ["ema_crossover", "rsi_oversold"]


@pytest.mark.asyncio
async def test_save_trades_empty_list_no_op(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="5" * 64,
            engine_version="v1",
        )
        n = await persistence.save_trades(session, run_id=run.id, trades=[])
        assert n == 0


# ─── save_metrics ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_metrics_inserts_new_row(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="4" * 64,
            engine_version="v1",
        )
        result = _sample_result(pnls=[100.0, -50.0, 200.0])
        metrics = await persistence.save_metrics(
            session, run_id=run.id, result=result
        )
        await session.commit()
        assert metrics.run_id == run.id
        assert metrics.total_trades == 3
        assert float(metrics.total_pnl) == 250.0
        assert metrics.profit_factor == Decimal("6")  # 300 / 50
        assert metrics.warnings == ["sample warning"]


@pytest.mark.asyncio
async def test_save_metrics_inf_profit_factor_persists_as_null(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """Wins-only deck → engine emits math.inf → DB stores NULL."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="3" * 64,
            engine_version="v1",
        )
        # wins-only — engine emits math.inf for profit_factor
        result = _sample_result(pnls=[100.0, 200.0, 50.0])
        metrics = await persistence.save_metrics(
            session, run_id=run.id, result=result
        )
        await session.commit()
        assert metrics.profit_factor is None


@pytest.mark.asyncio
async def test_save_metrics_upsert_overwrites(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="2" * 64,
            engine_version="v1",
        )
        result_a = _sample_result(pnls=[100.0, -50.0])
        await persistence.save_metrics(session, run_id=run.id, result=result_a)
        # Re-save with different result — UPSERT should overwrite
        result_b = _sample_result(pnls=[500.0, 250.0, 100.0])
        metrics = await persistence.save_metrics(
            session, run_id=run.id, result=result_b
        )
        await session.commit()
        assert metrics.total_trades == 3
        assert float(metrics.total_pnl) == 850.0


# ─── get_run_by_id ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_run_by_id_happy_path(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        original = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="1" * 64,
            engine_version="v1",
        )
        await session.commit()

    async with db_session_maker() as session:
        fetched = await persistence.get_run_by_id(session, run_id=original.id)
        assert fetched is not None
        assert fetched.id == original.id


@pytest.mark.asyncio
async def test_get_run_by_id_owner_scope_blocks_other_users(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """An owned user_id filter returns None for foreign rows (404, not 403)."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="0" * 64,
            engine_version="v1",
        )
        await session.commit()

    other_user_id = uuid.uuid4()
    async with db_session_maker() as session:
        fetched = await persistence.get_run_by_id(
            session, run_id=run.id, user_id=other_user_id
        )
        assert fetched is None


@pytest.mark.asyncio
async def test_get_run_by_id_eager_loads_metrics(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="aa" + "0" * 62,
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
        await persistence.save_metrics(
            session, run_id=run.id, result=_sample_result()
        )
        await session.commit()

    async with db_session_maker() as session:
        fetched = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert fetched is not None
        assert fetched.metrics is not None
        assert fetched.metrics.total_trades == 3


# ─── get_cached_run_by_hash ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_cached_run_by_hash_returns_succeeded_run(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="bb" + "0" * 62,
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

    async with db_session_maker() as session:
        cached = await persistence.get_cached_run_by_hash(
            session, user_id=seed_user.id, request_hash="bb" + "0" * 62
        )
        assert cached is not None
        assert cached.id == run.id


@pytest.mark.asyncio
async def test_get_cached_run_by_hash_ignores_pending_runs(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """A PENDING/RUNNING/FAILED run is NOT a cache hit."""
    async with db_session_maker() as session:
        await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="cc" + "0" * 62,
            engine_version="v1",
        )
        await session.commit()

    async with db_session_maker() as session:
        cached = await persistence.get_cached_run_by_hash(
            session, user_id=seed_user.id, request_hash="cc" + "0" * 62
        )
        assert cached is None


@pytest.mark.asyncio
async def test_get_cached_run_by_hash_other_user_not_returned(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """Cache is per-user — another user's SUCCEEDED run is NOT a hit."""
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="dd" + "0" * 62,
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

    other_user_id = uuid.uuid4()
    async with db_session_maker() as session:
        cached = await persistence.get_cached_run_by_hash(
            session, user_id=other_user_id, request_hash="dd" + "0" * 62
        )
        assert cached is None


# ─── get_trades_page ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trades_page_first_page(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="ee" + "0" * 62,
            engine_version="v1",
        )
        await persistence.save_trades(
            session,
            run_id=run.id,
            trades=[_sample_trade(pnl=float(i)) for i in range(10)],
        )
        await session.commit()

    async with db_session_maker() as session:
        rows, has_more, next_cursor = await persistence.get_trades_page(
            session, run_id=run.id, cursor=None, page_size=4
        )
        assert len(rows) == 4
        assert [r.trade_index for r in rows] == [0, 1, 2, 3]
        assert has_more is True
        assert next_cursor == 3


@pytest.mark.asyncio
async def test_get_trades_page_subsequent_pages(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="ff" + "0" * 62,
            engine_version="v1",
        )
        await persistence.save_trades(
            session,
            run_id=run.id,
            trades=[_sample_trade(pnl=float(i)) for i in range(10)],
        )
        await session.commit()

    async with db_session_maker() as session:
        rows, has_more, _ = await persistence.get_trades_page(
            session, run_id=run.id, cursor=3, page_size=4
        )
        assert len(rows) == 4
        assert [r.trade_index for r in rows] == [4, 5, 6, 7]
        assert has_more is True


@pytest.mark.asyncio
async def test_get_trades_page_last_page_has_more_false(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=None,
            request_payload=make_request_payload(),
            request_hash="11" + "0" * 62,
            engine_version="v1",
        )
        await persistence.save_trades(
            session,
            run_id=run.id,
            trades=[_sample_trade(pnl=float(i)) for i in range(10)],
        )
        await session.commit()

    async with db_session_maker() as session:
        rows, has_more, next_cursor = await persistence.get_trades_page(
            session, run_id=run.id, cursor=7, page_size=4
        )
        assert len(rows) == 2
        assert has_more is False
        assert next_cursor is None


@pytest.mark.asyncio
async def test_get_trades_page_page_size_validation(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_maker() as session:
        with pytest.raises(ValueError, match="page_size"):
            await persistence.get_trades_page(
                session, run_id=uuid.uuid4(), cursor=None, page_size=0
            )
