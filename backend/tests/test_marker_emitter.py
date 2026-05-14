"""Tests for ``app.services.marker_emitter`` + ``app.schemas.trade_marker``.

Real in-memory aiosqlite engine — same pattern as
``tests/test_kill_switch_service.py``. The five emitter coroutines are
exercised through actual ORM round-trips so the SQL paths (filters,
aggregates, dedup) are covered, not just the Python wrapper logic.

The SQLite engine doesn't enforce CHECK constraints under aiosqlite by
default (they're DDL-only, not validated on INSERT), so wrong-side
``exit_reason``/``pnl`` writes are caught by the Pydantic validators
in :class:`TradeMarkerCreate` instead — verified here too.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
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
from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
    TradeMarker,
)
from app.db.models.user import User
from app.schemas.trade_marker import (
    SignalMetadata,
    TradeMarkerBulkCreate,
    TradeMarkerCreate,
    TradeMarkerFilter,
)
from app.services.marker_emitter import (
    bulk_emit_markers,
    emit_entry_marker,
    emit_exit_marker,
    get_markers_by_strategy,
    get_strategy_summary,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory aiosqlite DB with all tables created."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def user(session: AsyncSession) -> User:
    u = User(
        email="phase-a@tradetri.com",
        password_hash="x",
        is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


@pytest_asyncio.fixture
async def strategy(session: AsyncSession, user: User) -> Strategy:
    s = Strategy(
        user_id=user.id,
        name="phase-a-test-strategy",
        is_active=True,
    )
    session.add(s)
    await session.flush()
    return s


def _ts(offset_seconds: int = 0) -> datetime:
    """Deterministic tz-aware timestamp shifted by ``offset_seconds``."""
    return datetime(2026, 5, 14, 9, 15, 0, tzinfo=UTC) + timedelta(
        seconds=offset_seconds
    )


# ═══════════════════════════════════════════════════════════════════════
# Schema validators
# ═══════════════════════════════════════════════════════════════════════


class TestTradeMarkerCreateValidators:
    def test_naive_timestamp_rejected(self, user: User, strategy: Strategy) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=datetime(2026, 5, 14, 9, 15),  # naive
                mode=MarkerMode.PAPER,
            )

    def test_exit_reason_on_entry_rejected(
        self, user: User, strategy: Strategy
    ) -> None:
        with pytest.raises(ValueError, match="exit_reason"):
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(),
                mode=MarkerMode.PAPER,
                exit_reason=MarkerExitReason.STOP_LOSS,
            )

    def test_pnl_on_entry_rejected(
        self, user: User, strategy: Strategy
    ) -> None:
        with pytest.raises(ValueError, match="pnl"):
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(),
                mode=MarkerMode.PAPER,
                pnl=Decimal("500"),
            )

    def test_exit_reason_on_exit_accepted(
        self, user: User, strategy: Strategy
    ) -> None:
        payload = TradeMarkerCreate(
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22550"),
            quantity=50,
            timestamp_utc=_ts(60),
            mode=MarkerMode.PAPER,
            pnl=Decimal("2500"),
            exit_reason=MarkerExitReason.TAKE_PROFIT,
        )
        assert payload.exit_reason == MarkerExitReason.TAKE_PROFIT
        assert payload.pnl == Decimal("2500")

    def test_negative_price_rejected(
        self, user: User, strategy: Strategy
    ) -> None:
        with pytest.raises(ValueError):
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("0"),
                quantity=50,
                timestamp_utc=_ts(),
                mode=MarkerMode.PAPER,
            )

    def test_zero_quantity_rejected(
        self, user: User, strategy: Strategy
    ) -> None:
        with pytest.raises(ValueError):
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=0,
                timestamp_utc=_ts(),
                mode=MarkerMode.PAPER,
            )


class TestTradeMarkerFilter:
    def test_naive_from_ts_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            TradeMarkerFilter(
                strategy_id=uuid.uuid4(),
                mode=MarkerMode.PAPER,
                from_ts=datetime(2026, 5, 14, 9, 15),
            )

    def test_default_pagination(self) -> None:
        f = TradeMarkerFilter(
            strategy_id=uuid.uuid4(),
            mode=MarkerMode.PAPER,
        )
        assert f.limit == 100
        assert f.offset == 0

    def test_limit_capped_at_500(self) -> None:
        with pytest.raises(ValueError):
            TradeMarkerFilter(
                strategy_id=uuid.uuid4(),
                mode=MarkerMode.PAPER,
                limit=501,
            )


class TestSignalMetadata:
    def test_forward_compat_extra_allowed(self) -> None:
        m = SignalMetadata.model_validate(
            {
                "broker_order_id": "ABC123",
                "future_field": "some-future-value",
            }
        )
        assert m.broker_order_id == "ABC123"
        # extra='allow' should round-trip the unknown key.
        d = m.model_dump()
        assert d.get("future_field") == "some-future-value"


class TestTradeMarkerBulkCreate:
    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValueError):
            TradeMarkerBulkCreate(markers=[])


# ═══════════════════════════════════════════════════════════════════════
# emit_entry_marker
# ═══════════════════════════════════════════════════════════════════════


class TestEmitEntryMarker:
    @pytest.mark.asyncio
    async def test_writes_row(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        row = await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="nifty",  # lowercased on purpose
            exchange="nse",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
            metadata=SignalMetadata(broker_order_id="ORD-1"),
        )
        assert row.id is not None
        assert row.side == MarkerSide.LONG_ENTRY.value
        assert row.symbol == "NIFTY"  # service uppercases
        assert row.exchange == "NSE"
        assert row.signal_metadata["broker_order_id"] == "ORD-1"

    @pytest.mark.asyncio
    async def test_rejects_exit_side(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        with pytest.raises(ValueError, match="non-entry"):
            await emit_entry_marker(
                session,
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_EXIT,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(),
                mode=MarkerMode.PAPER,
            )

    @pytest.mark.asyncio
    async def test_idempotent_within_one_second(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        kwargs = dict(
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            mode=MarkerMode.PAPER,
        )
        first = await emit_entry_marker(
            session, timestamp_utc=_ts(), **kwargs
        )
        # Re-emit within the same wall-clock second: same row id back.
        second = await emit_entry_marker(
            session,
            timestamp_utc=_ts().replace(microsecond=500_000),
            **kwargs,
        )
        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_metadata_dict_coerced(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        row = await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
            metadata={"broker_order_id": "ORD-2", "custom": "value"},
        )
        assert row.signal_metadata["broker_order_id"] == "ORD-2"
        assert row.signal_metadata.get("custom") == "value"

    @pytest.mark.asyncio
    async def test_none_metadata_becomes_empty_dict(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        row = await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
        )
        assert row.signal_metadata == {}


# ═══════════════════════════════════════════════════════════════════════
# emit_exit_marker
# ═══════════════════════════════════════════════════════════════════════


class TestEmitExitMarker:
    @pytest.mark.asyncio
    async def test_writes_linked_row(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        entry = await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
        )
        exit_row = await emit_exit_marker(
            session,
            entry_marker_id=entry.id,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22550"),
            quantity=50,
            timestamp_utc=_ts(60),
            mode=MarkerMode.PAPER,
            pnl=Decimal("2500"),
            exit_reason=MarkerExitReason.TAKE_PROFIT,
        )
        assert exit_row.linked_marker_id == entry.id
        assert exit_row.exit_reason == MarkerExitReason.TAKE_PROFIT.value
        assert exit_row.pnl == Decimal("2500")

    @pytest.mark.asyncio
    async def test_rejects_entry_side(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        with pytest.raises(ValueError, match="non-exit"):
            await emit_exit_marker(
                session,
                entry_marker_id=None,
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(),
                mode=MarkerMode.PAPER,
                pnl=Decimal("0"),
                exit_reason=MarkerExitReason.SIGNAL,
            )

    @pytest.mark.asyncio
    async def test_orphan_exit_allowed(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        row = await emit_exit_marker(
            session,
            entry_marker_id=None,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.SHORT_EXIT,
            price=Decimal("22500"),
            quantity=25,
            timestamp_utc=_ts(),
            mode=MarkerMode.LIVE,
            pnl=Decimal("-500"),
            exit_reason=MarkerExitReason.STOP_LOSS,
        )
        assert row.linked_marker_id is None
        assert row.pnl == Decimal("-500")

    @pytest.mark.asyncio
    async def test_metadata_dict_coerced(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        row = await emit_exit_marker(
            session,
            entry_marker_id=None,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22550"),
            quantity=50,
            timestamp_utc=_ts(120),
            mode=MarkerMode.PAPER,
            pnl=Decimal("2500"),
            exit_reason=MarkerExitReason.MANUAL,
            metadata={"notes": "user squared off"},
        )
        assert row.signal_metadata.get("notes") == "user squared off"


# ═══════════════════════════════════════════════════════════════════════
# bulk_emit_markers
# ═══════════════════════════════════════════════════════════════════════


class TestBulkEmitMarkers:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(
        self, session: AsyncSession
    ) -> None:
        out = await bulk_emit_markers(session, markers=[])
        assert out == []

    @pytest.mark.asyncio
    async def test_writes_all_rows(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        payloads = [
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(i * 60),
                mode=MarkerMode.BACKTEST,
            )
            for i in range(5)
        ]
        rows = await bulk_emit_markers(session, markers=payloads)
        assert len(rows) == 5
        assert all(r.id is not None for r in rows)
        # Re-running the same batch hits dedup and yields the same ids.
        rows2 = await bulk_emit_markers(session, markers=payloads)
        assert [r.id for r in rows2] == [r.id for r in rows]

    @pytest.mark.asyncio
    async def test_mixed_new_and_dedup(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        # Seed one row.
        first = await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.BACKTEST,
        )
        payloads = [
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(),  # dup
                mode=MarkerMode.BACKTEST,
            ),
            TradeMarkerCreate(
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(120),  # fresh
                mode=MarkerMode.BACKTEST,
            ),
        ]
        rows = await bulk_emit_markers(session, markers=payloads)
        assert len(rows) == 2
        assert rows[0].id == first.id
        assert rows[1].id != first.id


# ═══════════════════════════════════════════════════════════════════════
# get_markers_by_strategy
# ═══════════════════════════════════════════════════════════════════════


class TestGetMarkersByStrategy:
    @pytest.mark.asyncio
    async def test_filters_by_mode(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
        )
        await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22600"),
            quantity=50,
            timestamp_utc=_ts(60),
            mode=MarkerMode.LIVE,
        )

        rows, total = await get_markers_by_strategy(
            session, strategy_id=strategy.id, mode=MarkerMode.PAPER
        )
        assert total == 1
        assert len(rows) == 1
        assert rows[0].mode == MarkerMode.PAPER.value

    @pytest.mark.asyncio
    async def test_filters_by_window_and_symbol_and_side(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        # 3 markers across 2 symbols + 2 sides.
        await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
        )
        await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="BANKNIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("48000"),
            quantity=15,
            timestamp_utc=_ts(60),
            mode=MarkerMode.PAPER,
        )
        await emit_exit_marker(
            session,
            entry_marker_id=None,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22550"),
            quantity=50,
            timestamp_utc=_ts(120),
            mode=MarkerMode.PAPER,
            pnl=Decimal("2500"),
            exit_reason=MarkerExitReason.TAKE_PROFIT,
        )

        # Filter: NIFTY + LONG_ENTRY only.
        rows, total = await get_markers_by_strategy(
            session,
            strategy_id=strategy.id,
            mode=MarkerMode.PAPER,
            symbol="NIFTY",
            side=MarkerSide.LONG_ENTRY,
        )
        assert total == 1
        assert rows[0].symbol == "NIFTY"
        assert rows[0].side == MarkerSide.LONG_ENTRY.value

        # Filter: window.
        rows, total = await get_markers_by_strategy(
            session,
            strategy_id=strategy.id,
            mode=MarkerMode.PAPER,
            from_ts=_ts(30),
            to_ts=_ts(90),
        )
        assert total == 1
        assert rows[0].symbol == "BANKNIFTY"

    @pytest.mark.asyncio
    async def test_pagination(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        for i in range(7):
            await emit_entry_marker(
                session,
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500") + Decimal(i),
                quantity=50,
                timestamp_utc=_ts(i * 60),
                mode=MarkerMode.PAPER,
            )

        page1, total = await get_markers_by_strategy(
            session,
            strategy_id=strategy.id,
            mode=MarkerMode.PAPER,
            limit=3,
            offset=0,
        )
        page2, _ = await get_markers_by_strategy(
            session,
            strategy_id=strategy.id,
            mode=MarkerMode.PAPER,
            limit=3,
            offset=3,
        )
        assert total == 7
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].timestamp_utc < page2[0].timestamp_utc


# ═══════════════════════════════════════════════════════════════════════
# get_strategy_summary
# ═══════════════════════════════════════════════════════════════════════


class TestGetStrategySummary:
    @pytest.mark.asyncio
    async def test_empty_strategy_returns_zeroes(
        self,
        session: AsyncSession,
        strategy: Strategy,
    ) -> None:
        summary = await get_strategy_summary(
            session, strategy_id=strategy.id, mode=MarkerMode.PAPER
        )
        assert summary.trade_count == 0
        assert summary.total_pnl == Decimal("0")
        assert summary.win_rate == 0.0
        assert summary.avg_pnl == Decimal("0")

    @pytest.mark.asyncio
    async def test_mixed_wins_and_losses(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        pnls = [Decimal("1000"), Decimal("-500"), Decimal("250"), Decimal("-100")]
        for i, p in enumerate(pnls):
            await emit_exit_marker(
                session,
                entry_marker_id=None,
                strategy_id=strategy.id,
                user_id=user.id,
                symbol="NIFTY",
                exchange="NSE",
                side=MarkerSide.LONG_EXIT,
                price=Decimal("22500"),
                quantity=50,
                timestamp_utc=_ts(i * 60),
                mode=MarkerMode.PAPER,
                pnl=p,
                exit_reason=MarkerExitReason.SIGNAL,
            )
        # An entry row must NOT contribute.
        await emit_entry_marker(
            session,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(999),
            mode=MarkerMode.PAPER,
        )

        summary = await get_strategy_summary(
            session, strategy_id=strategy.id, mode=MarkerMode.PAPER
        )
        assert summary.trade_count == 4
        assert summary.total_pnl == Decimal("650")
        assert summary.win_rate == 0.5  # 2 / 4
        assert summary.avg_pnl == Decimal("650") / Decimal("4")

    @pytest.mark.asyncio
    async def test_mode_isolation(
        self,
        session: AsyncSession,
        user: User,
        strategy: Strategy,
    ) -> None:
        await emit_exit_marker(
            session,
            entry_marker_id=None,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
            pnl=Decimal("1000"),
            exit_reason=MarkerExitReason.TAKE_PROFIT,
        )
        await emit_exit_marker(
            session,
            entry_marker_id=None,
            strategy_id=strategy.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(60),
            mode=MarkerMode.LIVE,
            pnl=Decimal("5000"),
            exit_reason=MarkerExitReason.TAKE_PROFIT,
        )

        paper = await get_strategy_summary(
            session, strategy_id=strategy.id, mode=MarkerMode.PAPER
        )
        live = await get_strategy_summary(
            session, strategy_id=strategy.id, mode=MarkerMode.LIVE
        )
        assert paper.total_pnl == Decimal("1000")
        assert live.total_pnl == Decimal("5000")
