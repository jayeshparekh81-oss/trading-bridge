"""Queue DD Phase 6d — backtest trade-markers persistence tests.

Covers:
    * Trade list → trade_markers rows (2 rows per trade — entry + exit).
    * Empty trade list → 0 rows, no DB hit.
    * Per-run idempotency: a second persist call with the same
      backtest_run_id no-ops.
    * Exit-reason mapping degrades unknown strings to SIGNAL.
    * Chart-marker projection (``_marker_to_chart``) maps each
      MarkerSide to the right Lightweight Charts shape.

Uses the shared ``db_session_maker`` + ``seed_strategy`` fixtures from
``conftest.py``. The TradeMarker table is auto-created by
``Base.metadata.create_all`` because the model is imported transitively
via app.backtest_extension.trade_markers → app.db.models.trade_marker.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backtest_extension.api import (
    ChartMarkerOut,
    _marker_to_chart,
    _SIDE_TO_LWC,
)
from app.backtest_extension.trade_markers import (
    _map_exit_reason,
    fetch_markers_for_run,
    persist_backtest_trade_markers,
)
from app.db.models.strategy import Strategy
from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
    TradeMarker,
)
from app.db.models.user import User
from app.strategy_engine.backtest import Trade as EngineTrade
from app.strategy_engine.schema.strategy import Side


# ─── helpers ─────────────────────────────────────────────────────────


def _make_trade(
    *,
    entry_ts: datetime,
    exit_ts: datetime,
    entry_price: float = 25000.0,
    exit_price: float = 25100.0,
    side: Side = Side.BUY,
    pnl: float = 100.0,
    exit_reason: str = "target",
) -> EngineTrade:
    return EngineTrade(
        entry_time=entry_ts,
        exit_time=exit_ts,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=1.0,
        pnl=pnl,
        exit_reason=exit_reason,
        entry_reasons=("ema_crossover",),
    )


# ─── tests: persist_backtest_trade_markers ───────────────────────────


@pytest.mark.asyncio
async def test_persist_writes_entry_and_exit_per_trade(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_strategy: Strategy,
) -> None:
    """Each engine Trade produces 2 marker rows: one entry, one exit.
    Sides reflect the engine's BUY → LONG_*, SELL → SHORT_* mapping."""
    backtest_run_id = uuid.uuid4()
    long_trade = _make_trade(
        entry_ts=datetime(2026, 1, 5, 9, 30, tzinfo=UTC),
        exit_ts=datetime(2026, 1, 5, 11, 0, tzinfo=UTC),
        side=Side.BUY,
    )
    short_trade = _make_trade(
        entry_ts=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
        exit_ts=datetime(2026, 1, 5, 13, 30, tzinfo=UTC),
        side=Side.SELL,
        entry_price=25200.0,
        exit_price=25100.0,
        pnl=100.0,
        exit_reason="stop_loss",
    )

    async with db_session_maker() as session:
        count = await persist_backtest_trade_markers(
            session,
            backtest_run_id=backtest_run_id,
            strategy_id=seed_strategy.id,
            user_id=seed_strategy.user_id,
            symbol="NIFTY",
            exchange="NSE",
            trades=[long_trade, short_trade],
        )
        await session.commit()

    assert count == 4, f"expected 4 marker rows (2 per trade), got {count}"

    async with db_session_maker() as session:
        rows = (
            await session.execute(
                select(TradeMarker)
                .where(TradeMarker.strategy_id == seed_strategy.id)
                .order_by(TradeMarker.timestamp_utc.asc())
            )
        ).scalars().all()

    sides = [r.side for r in rows]
    assert sides == [
        MarkerSide.LONG_ENTRY.value,
        MarkerSide.LONG_EXIT.value,
        MarkerSide.SHORT_ENTRY.value,
        MarkerSide.SHORT_EXIT.value,
    ]
    # backtest_run_id propagates through signal_metadata for the
    # per-run dedup lookup.
    assert all(
        str(r.signal_metadata.get("backtest_run_id")) == str(backtest_run_id)
        for r in rows
    )
    # exit_reason populated only on *_EXIT rows.
    assert rows[0].exit_reason is None
    assert rows[1].exit_reason == MarkerExitReason.TAKE_PROFIT.value
    assert rows[3].exit_reason == MarkerExitReason.STOP_LOSS.value


@pytest.mark.asyncio
async def test_persist_empty_trades_returns_zero(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_strategy: Strategy,
) -> None:
    """No trades → 0 rows persisted, no DB hit beyond the empty short
    circuit. The Celery hook calls this even on zero-trade runs."""
    async with db_session_maker() as session:
        count = await persist_backtest_trade_markers(
            session,
            backtest_run_id=uuid.uuid4(),
            strategy_id=seed_strategy.id,
            user_id=seed_strategy.user_id,
            symbol="NIFTY",
            exchange="NSE",
            trades=[],
        )
    assert count == 0


@pytest.mark.asyncio
async def test_persist_idempotent_on_rerun(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_strategy: Strategy,
) -> None:
    """A retried Celery task that calls persist again with the SAME
    backtest_run_id must no-op — markers are already written. Without
    this, a transient failure-then-retry would double-write."""
    backtest_run_id = uuid.uuid4()
    trade = _make_trade(
        entry_ts=datetime(2026, 1, 5, 9, 30, tzinfo=UTC),
        exit_ts=datetime(2026, 1, 5, 11, 0, tzinfo=UTC),
    )

    async with db_session_maker() as session:
        first = await persist_backtest_trade_markers(
            session,
            backtest_run_id=backtest_run_id,
            strategy_id=seed_strategy.id,
            user_id=seed_strategy.user_id,
            symbol="NIFTY",
            exchange="NSE",
            trades=[trade],
        )
        await session.commit()
    assert first == 2

    async with db_session_maker() as session:
        second = await persist_backtest_trade_markers(
            session,
            backtest_run_id=backtest_run_id,
            strategy_id=seed_strategy.id,
            user_id=seed_strategy.user_id,
            symbol="NIFTY",
            exchange="NSE",
            trades=[trade],
        )
    # Second call sees existing markers tagged with the same run id —
    # returns 0, no fresh inserts. The exact count of pre-existing rows
    # is incidental; what matters is the no-op behaviour.
    assert second == 0


# ─── tests: fetch_markers_for_run ────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_markers_for_run_returns_only_matching_run(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_strategy: Strategy,
) -> None:
    """Two backtest runs on the same strategy persist their own markers;
    fetch_markers_for_run must isolate by backtest_run_id stored in
    signal_metadata, not return a mixed result."""
    run_a = uuid.uuid4()
    run_b = uuid.uuid4()
    trade_a = _make_trade(
        entry_ts=datetime(2026, 1, 5, 9, 30, tzinfo=UTC),
        exit_ts=datetime(2026, 1, 5, 11, 0, tzinfo=UTC),
        entry_price=25000.0,
    )
    # Different price + timestamp so the per-bar dedup doesn't merge them.
    trade_b = _make_trade(
        entry_ts=datetime(2026, 1, 6, 9, 30, tzinfo=UTC),
        exit_ts=datetime(2026, 1, 6, 11, 0, tzinfo=UTC),
        entry_price=25500.0,
    )

    async with db_session_maker() as session:
        await persist_backtest_trade_markers(
            session, backtest_run_id=run_a,
            strategy_id=seed_strategy.id, user_id=seed_strategy.user_id,
            symbol="NIFTY", exchange="NSE", trades=[trade_a],
        )
        await persist_backtest_trade_markers(
            session, backtest_run_id=run_b,
            strategy_id=seed_strategy.id, user_id=seed_strategy.user_id,
            symbol="NIFTY", exchange="NSE", trades=[trade_b],
        )
        await session.commit()

    async with db_session_maker() as session:
        a_rows = await fetch_markers_for_run(
            session, backtest_run_id=run_a, strategy_id=seed_strategy.id
        )
        b_rows = await fetch_markers_for_run(
            session, backtest_run_id=run_b, strategy_id=seed_strategy.id
        )

    assert len(a_rows) == 2 and len(b_rows) == 2
    assert all(
        str(r.signal_metadata["backtest_run_id"]) == str(run_a) for r in a_rows
    )
    assert all(
        str(r.signal_metadata["backtest_run_id"]) == str(run_b) for r in b_rows
    )


# ─── tests: exit-reason mapping ──────────────────────────────────────


@pytest.mark.parametrize(
    "engine_reason,expected",
    [
        ("stop_loss", MarkerExitReason.STOP_LOSS),
        ("trailing_stop", MarkerExitReason.STOP_LOSS),
        ("target", MarkerExitReason.TAKE_PROFIT),
        ("take_profit", MarkerExitReason.TAKE_PROFIT),
        ("signal", MarkerExitReason.SIGNAL),
        ("backtest_end", MarkerExitReason.SQUARE_OFF),
        ("totally_unknown_reason", MarkerExitReason.SIGNAL),  # safe default
        ("STOP_LOSS", MarkerExitReason.STOP_LOSS),  # case-insensitive
    ],
)
def test_map_exit_reason(engine_reason: str, expected: MarkerExitReason) -> None:
    assert _map_exit_reason(engine_reason) is expected


# ─── tests: chart-marker projection ──────────────────────────────────


def test_marker_to_chart_projects_long_entry_as_arrow_up_below_bar() -> None:
    """LONG_ENTRY → green arrow-up below the bar with 'BUY' label."""

    class FakeMarker:
        side = MarkerSide.LONG_ENTRY.value
        timestamp_utc = datetime(2026, 1, 5, 9, 30, tzinfo=UTC)

    out = _marker_to_chart(FakeMarker())
    assert isinstance(out, ChartMarkerOut)
    assert out.position == "belowBar"
    assert out.color == "#22c55e"
    assert out.shape == "arrowUp"
    assert out.text == "BUY"
    assert out.time == int(datetime(2026, 1, 5, 9, 30, tzinfo=UTC).timestamp())


def test_marker_to_chart_projects_long_exit_as_arrow_down_above_bar() -> None:
    """LONG_EXIT → red arrow-down above the bar with 'SELL' label."""

    class FakeMarker:
        side = MarkerSide.LONG_EXIT.value
        timestamp_utc = datetime(2026, 1, 5, 11, 0, tzinfo=UTC)

    out = _marker_to_chart(FakeMarker())
    assert out.position == "aboveBar"
    assert out.color == "#ef4444"
    assert out.shape == "arrowDown"
    assert out.text == "SELL"


def test_side_to_lwc_table_covers_all_marker_sides() -> None:
    """All four MarkerSide enum values must have a projection entry —
    otherwise the fallback (_LONG_ENTRY) would silently mis-render."""
    for side in MarkerSide:
        assert side.value in _SIDE_TO_LWC, (
            f"Missing chart projection for {side.value}"
        )
