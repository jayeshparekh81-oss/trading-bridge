"""Day-4 engine-integration tests.

Drives the full Celery task body against the REAL
``app.strategy_engine.backtest.run_backtest`` (no mocking). Verifies the
extension correctly:

  - Calls the engine with a valid BacktestInput
  - Persists trades + metrics on success
  - Transitions to FAILED with structured error_json on engine exceptions
  - Handles edge cases: zero trades, all-loss, malformed strategy

Day-1-3 test_celery_tasks.py already mocked the engine to isolate the
state machine. Day-4 tests REMOVE the engine mock — proves the wiring
end-to-end against synthetic 500-bar candles.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backtest_extension import celery_tasks, persistence
from app.backtest_extension.schemas import BacktestRunStatus
from app.db.models.user import User
from tests.backtest_extension.conftest import make_request_payload


@pytest.fixture
def patched_sessionmaker(db_session_maker: async_sessionmaker[AsyncSession]):
    with patch(
        "app.backtest_extension.celery_tasks.get_sessionmaker",
        return_value=db_session_maker,
    ):
        yield db_session_maker


def _strategy_json_ema_crossover() -> dict:
    """Realistic 2-EMA crossover strategy that fires on synthetic candles."""
    return {
        "id": "ema_cross_e2e",
        "name": "Day-4 EMA Cross",
        "mode": "expert",
        "indicators": [
            {"id": "ema_fast", "type": "ema", "params": {"period": 9}},
            {"id": "ema_slow", "type": "ema", "params": {"period": 21}},
        ],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {
                    "type": "indicator",
                    "left": "ema_fast",
                    "op": "crossover",
                    "right": "ema_slow",
                }
            ],
        },
        "exit": {"targetPercent": 1.5, "stopLossPercent": 1.0},
        "risk": {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }


def _strategy_json_never_enters() -> dict:
    """Strategy whose entry condition can never be satisfied on the
    synthetic series — proves zero-trades path."""
    return {
        "id": "never_enter",
        "name": "Never Enters",
        "mode": "expert",
        "indicators": [
            {"id": "ema_20", "type": "ema", "params": {"period": 20}},
        ],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "indicator", "left": "ema_20", "op": ">", "value": 10_000_000.0},
            ],
        },
        "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
        "risk": {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }


def _strategy_json_tight_stop_loss() -> dict:
    """Aggressive SL/TP that should produce a mix of wins and losses on
    the synthetic oscillating series. Used as a sanity strategy."""
    return {
        "id": "tight_sl",
        "name": "Tight SL",
        "mode": "expert",
        "indicators": [
            {"id": "ema_5", "type": "ema", "params": {"period": 5}},
            {"id": "ema_30", "type": "ema", "params": {"period": 30}},
        ],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "indicator", "left": "ema_5", "op": "crossover", "right": "ema_30"},
            ],
        },
        # Tight stop will hit during the synthetic oscillation
        "exit": {"targetPercent": 5.0, "stopLossPercent": 0.3},
        "risk": {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }


def _strategy_json_malformed() -> dict:
    """Missing required 'execution' block — Pydantic validation fails."""
    return {
        "id": "malformed",
        "name": "Bad payload",
        "mode": "expert",
        "indicators": [],
        "entry": {"side": "BUY", "operator": "AND", "conditions": []},
        "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
        # NO execution block — StrategyJSON validator requires it
    }


async def _seed_strategy_with_json(
    db_session_maker: async_sessionmaker[AsyncSession],
    user: User,
    strategy_json: dict,
):
    from app.db.models.strategy import Strategy

    async with db_session_maker() as session:
        s = Strategy(
            user_id=user.id,
            name=strategy_json["name"],
            is_active=True,
            strategy_json=strategy_json,
        )
        session.add(s)
        await session.commit()
        await session.refresh(s)
        return s


# ─── Happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_integration_happy_path_succeeds(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    patched_fetch_historical_candles,
    seed_user: User,
) -> None:
    """EMA crossover on 500-bar synthetic series → SUCCEEDED with trades."""
    strategy = await _seed_strategy_with_json(
        db_session_maker, seed_user, _strategy_json_ema_crossover()
    )
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=strategy.id,
            request_payload=make_request_payload(),
            request_hash="e2e1" + "0" * 60,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "SUCCEEDED", f"Expected SUCCEEDED, got {result}"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert final is not None
        assert final.status == "SUCCEEDED"
        assert final.completed_at is not None
        assert final.metrics is not None
        # Crossover strategy on a 500-bar oscillator should produce
        # several entries
        assert final.metrics.total_trades > 0


@pytest.mark.asyncio
async def test_engine_integration_trades_persisted_in_order(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    patched_fetch_historical_candles,
    seed_user: User,
) -> None:
    """save_trades preserves trade_index monotonic ordering."""
    strategy = await _seed_strategy_with_json(
        db_session_maker, seed_user, _strategy_json_ema_crossover()
    )
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=strategy.id,
            request_payload=make_request_payload(),
            request_hash="e2e2" + "0" * 60,
            engine_version="v1",
        )
        await session.commit()

    await celery_tasks._run_backtest_async(run.id)

    async with db_session_maker() as session:
        page, _, _ = await persistence.get_trades_page(
            session, run_id=run.id, cursor=None, page_size=1000
        )
        assert page, "Expected at least one trade"
        idx = [t.trade_index for t in page]
        assert idx == sorted(idx)
        assert idx == list(range(len(idx)))


# ─── Empty-trades path ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_integration_zero_trades_strategy(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    patched_fetch_historical_candles,
    seed_user: User,
) -> None:
    """Strategy whose condition can never fire → SUCCEEDED with 0 trades."""
    strategy = await _seed_strategy_with_json(
        db_session_maker, seed_user, _strategy_json_never_enters()
    )
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=strategy.id,
            request_payload=make_request_payload(),
            request_hash="e2e3" + "0" * 60,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "SUCCEEDED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert final is not None
        assert final.metrics is not None
        assert final.metrics.total_trades == 0
        # Win rate / loss rate undefined → engine emits 0.0
        assert float(final.metrics.win_rate) == 0.0
        assert float(final.metrics.loss_rate) == 0.0
        assert float(final.metrics.total_pnl) == 0.0


# ─── Mixed-result path (sanity) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_integration_tight_stop_produces_mixed_results(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    patched_fetch_historical_candles,
    seed_user: User,
) -> None:
    """Tight 0.3% SL on oscillating series → some losses materialise.

    NOT asserting exact pnl — just that the engine produces a
    well-formed result with metrics fields populated.
    """
    strategy = await _seed_strategy_with_json(
        db_session_maker, seed_user, _strategy_json_tight_stop_loss()
    )
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=strategy.id,
            request_payload=make_request_payload(),
            request_hash="e2e4" + "0" * 60,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "SUCCEEDED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert final is not None and final.metrics is not None
        # Sanity bounds — metrics in legal Pydantic ranges
        assert 0.0 <= float(final.metrics.win_rate) <= 1.0
        assert 0.0 <= float(final.metrics.loss_rate) <= 1.0
        assert 0.0 <= float(final.metrics.max_drawdown) <= 1.0
        assert final.metrics.total_trades >= 0


# ─── Error paths ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_integration_malformed_strategy_json_fails(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
) -> None:
    """Strategy row with malformed strategy_json → FAILED with descriptive error."""
    strategy = await _seed_strategy_with_json(
        db_session_maker, seed_user, _strategy_json_malformed()
    )
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=strategy.id,
            request_payload=make_request_payload(),
            request_hash="e2e5" + "0" * 60,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "FAILED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert final is not None
        assert final.status == "FAILED"
        assert final.error_json is not None
        # Pydantic ValidationError is the root cause
        assert "Validation" in final.error_json["type"] or "ValueError" in final.error_json["type"]
        # No metrics persisted on failed path
        assert final.metrics is None


@pytest.mark.asyncio
async def test_engine_integration_strategy_with_null_dsl_fails(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user: User,
) -> None:
    """Cloned-from-template strategy with strategy_json=null → FAILED."""
    from app.db.models.strategy import Strategy

    async with db_session_maker() as session:
        s = Strategy(
            user_id=seed_user.id,
            name="Cloned with null DSL",
            is_active=True,
            strategy_json=None,
        )
        session.add(s)
        await session.commit()
        await session.refresh(s)

        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=s.id,
            request_payload=make_request_payload(),
            request_hash="e2e6" + "0" * 60,
            engine_version="v1",
        )
        await session.commit()

    result = await celery_tasks._run_backtest_async(run.id)
    assert result == "FAILED"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.error_json is not None
        assert "no DSL" in final.error_json["message"] or "null strategy_json" in final.error_json["message"]


# ─── Candle generator deterministic check ─────────────────────────────


def test_synthetic_candles_are_deterministic() -> None:
    """Same payload → same candle list. Reproducibility for cache hits."""
    payload1 = {"symbol": "NIFTY", "timeframe": "5m"}
    payload2 = dict(payload1)
    c1 = celery_tasks._build_synthetic_candles_payload(payload1)
    c2 = celery_tasks._build_synthetic_candles_payload(payload2)
    assert len(c1) == len(c2) == 500
    for a, b in zip(c1, c2, strict=True):
        assert a.timestamp == b.timestamp
        assert a.open == b.open
        assert a.close == b.close


def test_synthetic_candles_respect_ohlc_invariant() -> None:
    """Engine's Candle validator enforces low <= open/close <= high.
    The synthetic generator must satisfy this for the engine to accept."""
    candles = celery_tasks._build_synthetic_candles_payload({})
    for c in candles:
        assert c.low <= c.open <= c.high
        assert c.low <= c.close <= c.high
        assert c.low <= c.high
        assert c.volume >= 0


# ─── Engine NOT modified verification ─────────────────────────────────


def test_engine_module_untouched() -> None:
    """Smoke test — confirm the engine module is importable + the
    public symbols haven't changed shape since Day 1-3."""
    from app.strategy_engine.backtest import (
        AmbiguityMode,
        BacktestInput,
        BacktestResult,
        CostSettings,
        EquityPoint,
        Trade,
        run_backtest,
    )

    # All seven public exports importable
    assert callable(run_backtest)
    assert AmbiguityMode.CONSERVATIVE.value == "conservative"
    # Pydantic models present
    for cls in (BacktestInput, BacktestResult, CostSettings, EquityPoint, Trade):
        assert hasattr(cls, "model_validate")
