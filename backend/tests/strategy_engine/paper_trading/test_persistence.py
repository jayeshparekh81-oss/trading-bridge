"""DB-backed paper-trading persistence — store + bridge helpers.

Migration 010 added ``paper_sessions`` and ``paper_trades``. These
tests exercise the new ``store.py`` CRUD plus the bridge helpers
``flush_session_to_store`` and ``compute_readiness_from_db`` that the
live-orders SafetyChain (Phase 8B-2) will call.

Fixtures mirror the established ``test_kill_switch_service`` style:
SQLite in-memory engine, ``Base.metadata.create_all``, real User and
Strategy rows so the FK constraints are exercised.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.strategy_engine.paper_trading import store
from app.strategy_engine.paper_trading.persistence import (
    compute_readiness_from_db,
    flush_session_to_store,
)
from app.strategy_engine.paper_trading.store import (
    DuplicatePaperSessionError,
)
from tests.strategy_engine.paper_trading.conftest import (
    make_candle,
    make_strategy,
)

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def user(db: AsyncSession) -> User:
    u = User(email="t@x", password_hash="p", is_active=True)
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def strategy(db: AsyncSession, user: User) -> Strategy:
    s = Strategy(user_id=user.id, name="P-test", is_active=True)
    db.add(s)
    await db.flush()
    return s


# ─── store.py ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_session_inserts_row(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    row = await store.create_session(
        db,
        user_id=user.id,
        strategy_id=strategy.id,
        engine_strategy_id="eng_id_1",
        session_date=date(2026, 5, 1),
    )
    assert row.id is not None
    assert row.is_complete is False
    assert row.total_trades == 0
    assert row.total_pnl == Decimal("0")
    assert row.engine_strategy_id == "eng_id_1"


@pytest.mark.asyncio
async def test_create_session_duplicate_raises(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    await store.create_session(
        db,
        user_id=user.id,
        strategy_id=strategy.id,
        engine_strategy_id="eng_id_1",
        session_date=date(2026, 5, 1),
    )
    with pytest.raises(DuplicatePaperSessionError):
        await store.create_session(
            db,
            user_id=user.id,
            strategy_id=strategy.id,
            engine_strategy_id="eng_id_1",
            session_date=date(2026, 5, 1),
        )


@pytest.mark.asyncio
async def test_complete_session_marks_done_and_persists_totals(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    row = await store.create_session(
        db,
        user_id=user.id,
        strategy_id=strategy.id,
        engine_strategy_id="eng",
        session_date=date(2026, 5, 1),
    )
    completed = await store.complete_session(
        db,
        session_id=row.id,
        total_trades=3,
        total_pnl=Decimal("1234.5600"),
    )
    assert completed.is_complete is True
    assert completed.completed_at is not None
    assert completed.total_trades == 3
    assert completed.total_pnl == Decimal("1234.5600")


@pytest.mark.asyncio
async def test_complete_session_unknown_id_raises(
    db: AsyncSession,
) -> None:
    with pytest.raises(LookupError):
        await store.complete_session(
            db,
            session_id=uuid.uuid4(),
            total_trades=0,
            total_pnl=Decimal("0"),
        )


@pytest.mark.asyncio
async def test_get_completed_sessions_count_filters_by_user_strategy(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    """Only completed sessions matching ``(user, strategy)`` count.

    Includes a row for an unrelated strategy to verify the WHERE
    clause discriminates correctly.
    """
    other_strategy = Strategy(
        user_id=user.id, name="other", is_active=True
    )
    db.add(other_strategy)
    await db.flush()

    base = date(2026, 5, 1)
    for i in range(5):
        row = await store.create_session(
            db,
            user_id=user.id,
            strategy_id=strategy.id,
            engine_strategy_id="eng",
            session_date=base + timedelta(days=i),
        )
        await store.complete_session(
            db,
            session_id=row.id,
            total_trades=1,
            total_pnl=Decimal("10"),
        )

    # One incomplete session — must NOT count.
    await store.create_session(
        db,
        user_id=user.id,
        strategy_id=strategy.id,
        engine_strategy_id="eng",
        session_date=base + timedelta(days=10),
    )

    # One unrelated-strategy completed session — must NOT count.
    other_row = await store.create_session(
        db,
        user_id=user.id,
        strategy_id=other_strategy.id,
        engine_strategy_id="eng",
        session_date=base,
    )
    await store.complete_session(
        db,
        session_id=other_row.id,
        total_trades=1,
        total_pnl=Decimal("10"),
    )

    count = await store.get_completed_sessions_count(
        db, user_id=user.id, strategy_id=strategy.id
    )
    assert count == 5


@pytest.mark.asyncio
async def test_record_trade_attaches_to_session(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    row = await store.create_session(
        db,
        user_id=user.id,
        strategy_id=strategy.id,
        engine_strategy_id="eng",
        session_date=date(2026, 5, 1),
    )
    trade = await store.record_trade(
        db,
        session_id=row.id,
        entry_at=datetime(2026, 5, 1, 9, 30, tzinfo=UTC),
        exit_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        entry_price=Decimal("100.0000"),
        exit_price=Decimal("102.0000"),
        pnl=Decimal("2.0000"),
        exit_reason="target",
    )
    assert trade.session_id == row.id
    assert trade.symbol == "NIFTY"
    assert trade.pnl == Decimal("2.0000")

    listed = await store.list_trades(db, session_id=row.id)
    assert len(listed) == 1
    assert listed[0].id == trade.id


# ─── persistence.py — flush_session_to_store ──────────────────────────


@pytest.mark.asyncio
async def test_flush_session_to_store_persists_engine_state(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    """End-to-end: drive engine to close a trade, flush, verify DB rows.

    Uses the existing test fixtures from
    ``tests/strategy_engine/paper_trading/conftest.py`` so the engine
    behaviour matches the existing suite.
    """
    from app.strategy_engine.paper_trading import (
        clear_paper_state,
        end_session,
        process_candle,
        start_session,
    )

    clear_paper_state()

    spec = make_strategy(
        exit_block={"targetPercent": 2.0, "stopLossPercent": 1.0}
    )
    sess = start_session(spec, user_id=user.id)
    process_candle(sess, make_candle(minutes=0, open_=100.0), {})
    process_candle(sess, make_candle(minutes=1, open_=100.0), {})
    process_candle(
        sess,
        make_candle(
            minutes=2, open_=100.0, high=102.0, low=100.0, close=101.0
        ),
        {},
    )
    finished = end_session(sess)

    row_id = await flush_session_to_store(
        db,
        session=finished,
        user_id=user.id,
        strategy_id=strategy.id,
    )

    persisted = await store.get_session(db, row_id)
    assert persisted is not None
    assert persisted.is_complete is True
    assert persisted.total_trades == 1
    assert persisted.total_pnl == Decimal("2")

    trades = await store.list_trades(db, session_id=row_id)
    assert len(trades) == 1
    assert trades[0].pnl == Decimal("2")
    assert trades[0].exit_reason == "target"

    clear_paper_state()


@pytest.mark.asyncio
async def test_flush_session_to_store_idempotent(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    """Re-flushing the same engine session converges the DB row.

    The trade rows are wiped-and-reinserted so the DB always reflects
    the latest engine snapshot. The session row itself is reused
    (unique constraint on ``(user, strategy, day)``).
    """
    from app.strategy_engine.paper_trading import (
        clear_paper_state,
        end_session,
        process_candle,
        start_session,
    )

    clear_paper_state()

    spec = make_strategy(
        exit_block={"targetPercent": 2.0, "stopLossPercent": 1.0}
    )
    sess = start_session(spec, user_id=user.id)
    process_candle(sess, make_candle(minutes=0, open_=100.0), {})
    process_candle(sess, make_candle(minutes=1, open_=100.0), {})
    process_candle(
        sess,
        make_candle(
            minutes=2, open_=100.0, high=102.0, low=100.0, close=101.0
        ),
        {},
    )
    finished = end_session(sess)

    first_id = await flush_session_to_store(
        db,
        session=finished,
        user_id=user.id,
        strategy_id=strategy.id,
    )
    second_id = await flush_session_to_store(
        db,
        session=finished,
        user_id=user.id,
        strategy_id=strategy.id,
    )
    assert first_id == second_id

    trades = await store.list_trades(db, session_id=first_id)
    assert len(trades) == 1  # not duplicated.

    clear_paper_state()


# ─── persistence.py — compute_readiness_from_db ──────────────────────


@pytest.mark.asyncio
async def test_compute_readiness_from_db_blocks_below_seven_sessions(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    spec = make_strategy()
    base = date(2026, 5, 1)
    for i in range(3):
        row = await store.create_session(
            db,
            user_id=user.id,
            strategy_id=strategy.id,
            engine_strategy_id=spec.id,
            session_date=base + timedelta(days=i),
        )
        await store.complete_session(
            db,
            session_id=row.id,
            total_trades=1,
            total_pnl=Decimal("10"),
        )

    report = await compute_readiness_from_db(
        db, user_id=user.id, strategy_id=strategy.id, strategy=spec
    )
    assert report.live_ready is False
    assert any("Insufficient completed sessions" in r for r in report.blocked_reasons)


@pytest.mark.asyncio
async def test_compute_readiness_from_db_passes_when_all_gates_clear(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    spec = make_strategy()
    base = date(2026, 5, 1)
    # Seven completed sessions with one positive-pnl trade each.
    for i in range(7):
        row = await store.create_session(
            db,
            user_id=user.id,
            strategy_id=strategy.id,
            engine_strategy_id=spec.id,
            session_date=base + timedelta(days=i),
        )
        await store.record_trade(
            db,
            session_id=row.id,
            entry_at=datetime(2026, 5, 1, 9, 30, tzinfo=UTC),
            exit_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            symbol="NIFTY",
            side="BUY",
            quantity=1,
            entry_price=Decimal("100"),
            exit_price=Decimal("102"),
            pnl=Decimal("2"),
            exit_reason="target",
        )
        await store.complete_session(
            db,
            session_id=row.id,
            total_trades=1,
            total_pnl=Decimal("2"),
        )

    report = await compute_readiness_from_db(
        db, user_id=user.id, strategy_id=strategy.id, strategy=spec
    )
    assert report.completed_sessions == 7
    assert report.live_ready is True
    assert report.blocked_reasons == ()
    assert report.paper_pnl == 14.0
    assert report.paper_win_rate == 1.0


@pytest.mark.asyncio
async def test_compute_readiness_from_db_flags_no_stop_loss(
    db: AsyncSession, user: User, strategy: Strategy
) -> None:
    """Strategy without stop-loss is blocked even with seven completed sessions."""
    # Build a spec whose exit block has neither stop-loss nor trailing
    # stop. The default ``make_strategy`` carries targetPercent +
    # stopLossPercent; we replace it with a stop-loss-free variant via
    # ``model_copy``.
    spec = make_strategy()
    no_stop_exit = spec.exit.model_copy(
        update={
            "stop_loss_percent": None,
            "trailing_stop_percent": None,
        }
    )
    no_stop = spec.model_copy(update={"exit": no_stop_exit})

    base = date(2026, 5, 1)
    for i in range(7):
        row = await store.create_session(
            db,
            user_id=user.id,
            strategy_id=strategy.id,
            engine_strategy_id=no_stop.id,
            session_date=base + timedelta(days=i),
        )
        await store.record_trade(
            db,
            session_id=row.id,
            entry_at=datetime(2026, 5, 1, 9, 30, tzinfo=UTC),
            exit_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            symbol="NIFTY",
            side="BUY",
            quantity=1,
            entry_price=Decimal("100"),
            exit_price=Decimal("102"),
            pnl=Decimal("2"),
            exit_reason="target",
        )
        await store.complete_session(
            db,
            session_id=row.id,
            total_trades=1,
            total_pnl=Decimal("2"),
        )

    report = await compute_readiness_from_db(
        db,
        user_id=user.id,
        strategy_id=strategy.id,
        strategy=no_stop,
    )
    assert report.live_ready is False
    assert any("no stop loss" in r.lower() for r in report.blocked_reasons)
