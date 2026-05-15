"""Tests for :mod:`app.services.strategy_tester_service` (Phase B).

Two halves:

    * Pure-helper tests for :func:`compute_drawdown_series` — no DB.
    * Async service tests against a real in-memory aiosqlite engine,
      seeding markers via the Phase A :mod:`app.services.marker_emitter`
      (the production write path) so the integration is end-to-end
      from emitter → reader.

Coverage focus areas (per spec):
    * Empty markers (no trades) — return zeros / Nones.
    * Single open trade (no exit yet).
    * Multiple closed trades, profitable + losing mix.
    * Mode filtering (BACKTEST vs PAPER vs LIVE).
    * Pagination on get_trades.
    * Equity curve with various starting_equity values.
    * Drawdown calculation correctness.
"""

from __future__ import annotations

import math
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
from app.db.models.trade_marker import MarkerExitReason, MarkerMode, MarkerSide
from app.db.models.user import User
from app.services.marker_emitter import emit_entry_marker, emit_exit_marker
from app.services.strategy_tester_service import (
    aggregate_metrics,
    build_equity_curve,
    compute_drawdown_series,
    get_trades,
)


# ═══════════════════════════════════════════════════════════════════════
# Pure helper — compute_drawdown_series
# ═══════════════════════════════════════════════════════════════════════


class TestComputeDrawdownSeries:
    def test_empty_input_returns_empty_list(self) -> None:
        assert compute_drawdown_series([]) == []

    def test_monotonic_growth_zero_drawdown(self) -> None:
        out = compute_drawdown_series([100.0, 110.0, 120.0, 130.0])
        assert out == [0.0, 0.0, 0.0, 0.0]

    def test_dip_then_recovery(self) -> None:
        # peak after step 1 = 120, dips to 90 → drawdown = (120-90)/120 = 25%
        out = compute_drawdown_series([100.0, 120.0, 90.0, 130.0])
        assert out[0] == pytest.approx(0.0)
        assert out[1] == pytest.approx(0.0)
        assert out[2] == pytest.approx(25.0)
        # New peak 130 — drawdown resets to zero.
        assert out[3] == pytest.approx(0.0)

    def test_strictly_decreasing(self) -> None:
        out = compute_drawdown_series([100.0, 90.0, 80.0, 70.0])
        # peak stays 100; drawdown grows.
        assert out == pytest.approx([0.0, 10.0, 20.0, 30.0])

    def test_zero_starting_peak_yields_zero(self) -> None:
        # Degenerate case — caller passed all zeros.
        assert compute_drawdown_series([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]

    def test_negative_peak_protected_from_div_by_zero(self) -> None:
        # All negatives → peak stays first value (negative) → guard returns 0.
        out = compute_drawdown_series([-100.0, -200.0, -50.0])
        assert all(x == 0.0 for x in out)

    def test_single_point_yields_zero(self) -> None:
        assert compute_drawdown_series([100.0]) == [0.0]


# ═══════════════════════════════════════════════════════════════════════
# DB fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def engine_and_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    yield engine, maker
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_strategy(
    engine_and_session,
) -> AsyncIterator[tuple[User, Strategy]]:
    _engine, maker = engine_and_session
    async with maker() as s:
        u = User(
            email="phase-b-svc@tradetri.com",
            password_hash="x",
            is_active=True,
        )
        s.add(u)
        await s.flush()
        strat = Strategy(user_id=u.id, name="phase-b-svc-strat", is_active=True)
        s.add(strat)
        await s.commit()
        yield u, strat


def _ts(seconds: int = 0) -> datetime:
    """Anchor: 2026-05-14 09:15:00 UTC + offset seconds."""
    return datetime(2026, 5, 14, 9, 15, 0, tzinfo=UTC) + timedelta(seconds=seconds)


async def _seed_closed_trade(
    session: AsyncSession,
    *,
    user: User,
    strategy: Strategy,
    symbol: str,
    side: MarkerSide,
    entry_price: Decimal,
    exit_price: Decimal,
    qty: int,
    pnl: Decimal,
    entry_ts: datetime,
    exit_ts: datetime,
    mode: MarkerMode = MarkerMode.PAPER,
    exit_reason: MarkerExitReason = MarkerExitReason.SIGNAL,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Emit one entry+linked exit pair via the production emitter.

    Returns (entry_id, exit_id). Caller commits when ready.
    """
    exit_side = (
        MarkerSide.LONG_EXIT if side == MarkerSide.LONG_ENTRY else MarkerSide.SHORT_EXIT
    )
    entry = await emit_entry_marker(
        session,
        strategy_id=strategy.id,
        user_id=user.id,
        symbol=symbol,
        exchange="NSE",
        side=side,
        price=entry_price,
        quantity=qty,
        timestamp_utc=entry_ts,
        mode=mode,
    )
    exit_row = await emit_exit_marker(
        session,
        entry_marker_id=entry.id,
        strategy_id=strategy.id,
        user_id=user.id,
        symbol=symbol,
        exchange="NSE",
        side=exit_side,
        price=exit_price,
        quantity=qty,
        timestamp_utc=exit_ts,
        mode=mode,
        pnl=pnl,
        exit_reason=exit_reason,
    )
    return entry.id, exit_row.id


# ═══════════════════════════════════════════════════════════════════════
# aggregate_metrics
# ═══════════════════════════════════════════════════════════════════════


class TestAggregateMetricsEmpty:
    @pytest.mark.asyncio
    async def test_no_markers_returns_zero_shape(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            m = await aggregate_metrics(
                strategy_id=strat.id,
                mode=MarkerMode.PAPER,
                from_ts=None,
                to_ts=None,
                db=s,
            )
        assert m.total_pnl == Decimal("0")
        assert m.win_rate_pct == 0.0
        assert m.profit_factor is None
        assert m.total_trades == 0
        assert m.profitable_trades == 0
        assert m.max_drawdown_pct == 0.0
        assert m.sharpe_ratio_proxy is None
        assert m.avg_win == Decimal("0")
        assert m.avg_loss == Decimal("0")
        assert m.expectancy == Decimal("0")


class TestAggregateMetricsClosedTrades:
    @pytest.mark.asyncio
    async def test_three_closed_mix(
        self, engine_and_session, seeded_strategy
    ) -> None:
        """3 trades: +500, -200, +300 → win_rate 2/3, total +600."""
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("22500"), exit_price=Decimal("22510"),
                qty=50, pnl=Decimal("500"),
                entry_ts=_ts(0), exit_ts=_ts(60),
            )
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("22500"), exit_price=Decimal("22496"),
                qty=50, pnl=Decimal("-200"),
                entry_ts=_ts(120), exit_ts=_ts(180),
            )
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("22500"), exit_price=Decimal("22506"),
                qty=50, pnl=Decimal("300"),
                entry_ts=_ts(240), exit_ts=_ts(300),
            )
            await s.commit()

            m = await aggregate_metrics(
                strategy_id=strat.id,
                mode=MarkerMode.PAPER,
                from_ts=None,
                to_ts=None,
                db=s,
            )

        assert m.total_trades == 3
        assert m.profitable_trades == 2
        assert m.total_pnl == Decimal("600")
        assert m.win_rate_pct == pytest.approx(2 / 3 * 100)
        # gross_profit = 800, gross_loss = 200 → profit_factor = 4.0
        assert m.profit_factor == pytest.approx(4.0)
        assert m.avg_win == Decimal("400")  # (500 + 300) / 2
        assert m.avg_loss == Decimal("-200")  # only one loss
        assert m.largest_win == Decimal("500")
        assert m.largest_loss == Decimal("-200")
        # Expectancy = (2/3)*400 + (1/3)*(-200) = 266.67 - 66.67 = 200
        assert m.expectancy == pytest.approx(Decimal("200"), abs=Decimal("0.01"))
        # Sharpe proxy is defined for >=2 trades with non-zero variance.
        assert m.sharpe_ratio_proxy is not None

    @pytest.mark.asyncio
    async def test_all_wins_profit_factor_is_none(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            for i in range(3):
                await _seed_closed_trade(
                    s, user=user, strategy=strat, symbol="NIFTY",
                    side=MarkerSide.LONG_ENTRY,
                    entry_price=Decimal("100"), exit_price=Decimal("110"),
                    qty=10, pnl=Decimal("100"),
                    entry_ts=_ts(i * 120), exit_ts=_ts(i * 120 + 60),
                )
            await s.commit()
            m = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, db=s,
            )
        assert m.total_trades == 3
        assert m.profitable_trades == 3
        assert m.win_rate_pct == 100.0
        # All wins, no losses → profit_factor undefined → None.
        assert m.profit_factor is None

    @pytest.mark.asyncio
    async def test_all_losses_profit_factor_zero(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            for i in range(2):
                await _seed_closed_trade(
                    s, user=user, strategy=strat, symbol="NIFTY",
                    side=MarkerSide.LONG_ENTRY,
                    entry_price=Decimal("100"), exit_price=Decimal("90"),
                    qty=10, pnl=Decimal("-100"),
                    entry_ts=_ts(i * 120), exit_ts=_ts(i * 120 + 60),
                )
            await s.commit()
            m = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, db=s,
            )
        assert m.total_trades == 2
        assert m.profitable_trades == 0
        assert m.win_rate_pct == 0.0
        assert m.profit_factor == 0.0  # No wins AND losses present → 0, not None.

    @pytest.mark.asyncio
    async def test_open_only_no_metrics(
        self, engine_and_session, seeded_strategy
    ) -> None:
        """Entries without exits don't contribute to realised metrics."""
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await emit_entry_marker(
                s, strategy_id=strat.id, user_id=user.id,
                symbol="NIFTY", exchange="NSE",
                side=MarkerSide.LONG_ENTRY,
                price=Decimal("22500"), quantity=50,
                timestamp_utc=_ts(0), mode=MarkerMode.PAPER,
            )
            await s.commit()
            m = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, db=s,
            )
        assert m.total_trades == 0  # No closed trades.
        assert m.total_pnl == Decimal("0")


class TestAggregateMetricsModeFiltering:
    @pytest.mark.asyncio
    async def test_paper_excludes_live(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("110"),
                qty=10, pnl=Decimal("100"),
                entry_ts=_ts(0), exit_ts=_ts(60),
                mode=MarkerMode.PAPER,
            )
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="BANKNIFTY",
                side=MarkerSide.SHORT_ENTRY,
                entry_price=Decimal("48000"), exit_price=Decimal("47900"),
                qty=15, pnl=Decimal("1500"),
                entry_ts=_ts(120), exit_ts=_ts(180),
                mode=MarkerMode.LIVE,
            )
            await s.commit()

            paper = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, db=s,
            )
            live = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.LIVE,
                from_ts=None, to_ts=None, db=s,
            )
            backtest = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.BACKTEST,
                from_ts=None, to_ts=None, db=s,
            )

        assert paper.total_trades == 1
        assert paper.total_pnl == Decimal("100")
        assert live.total_trades == 1
        assert live.total_pnl == Decimal("1500")
        assert backtest.total_trades == 0  # No backtest markers seeded.


# ═══════════════════════════════════════════════════════════════════════
# build_equity_curve
# ═══════════════════════════════════════════════════════════════════════


class TestBuildEquityCurve:
    @pytest.mark.asyncio
    async def test_empty_returns_single_anchor(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            curve = await build_equity_curve(
                strategy_id=strat.id,
                mode=MarkerMode.PAPER,
                starting_equity=Decimal("50000"),
                from_ts=None,
                to_ts=None,
                db=s,
            )
        assert len(curve.points) == 1
        assert curve.points[0].equity == Decimal("50000")
        assert curve.points[0].drawdown_pct == 0.0
        assert curve.points[0].trade_id_or_none is None
        assert curve.starting_equity == Decimal("50000")
        assert curve.ending_equity == Decimal("50000")

    @pytest.mark.asyncio
    async def test_three_trades_walk(
        self, engine_and_session, seeded_strategy
    ) -> None:
        """+500, -200, +300 → equity 100000 → 100500 → 100300 → 100600."""
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            _e1, x1 = await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("105"),
                qty=100, pnl=Decimal("500"),
                entry_ts=_ts(0), exit_ts=_ts(60),
            )
            _e2, x2 = await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("98"),
                qty=100, pnl=Decimal("-200"),
                entry_ts=_ts(120), exit_ts=_ts(180),
            )
            _e3, x3 = await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("103"),
                qty=100, pnl=Decimal("300"),
                entry_ts=_ts(240), exit_ts=_ts(300),
            )
            await s.commit()
            curve = await build_equity_curve(
                strategy_id=strat.id,
                mode=MarkerMode.PAPER,
                starting_equity=Decimal("100000"),
                from_ts=None,
                to_ts=None,
                db=s,
            )
        # 1 anchor + 3 trades = 4 points.
        assert len(curve.points) == 4
        assert curve.points[0].equity == Decimal("100000")
        assert curve.points[1].equity == Decimal("100500")
        assert curve.points[2].equity == Decimal("100300")
        assert curve.points[3].equity == Decimal("100600")
        assert curve.points[1].trade_id_or_none == x1
        assert curve.points[2].trade_id_or_none == x2
        assert curve.points[3].trade_id_or_none == x3
        assert curve.starting_equity == Decimal("100000")
        assert curve.ending_equity == Decimal("100600")
        assert curve.max_equity == Decimal("100600")
        assert curve.min_equity == Decimal("100000")
        # Drawdown after second trade: peak 100500, dropped to 100300 →
        # (500-300)/100500 * 100 ≈ 0.199%.
        assert curve.points[2].drawdown_pct == pytest.approx(
            (100500 - 100300) / 100500 * 100, abs=1e-6
        )
        # Anchor drawdown is 0 (peak == self).
        assert curve.points[0].drawdown_pct == 0.0
        # New peak at point 3 → drawdown back to 0.
        assert curve.points[3].drawdown_pct == 0.0

    @pytest.mark.asyncio
    async def test_starting_equity_variants(
        self, engine_and_session, seeded_strategy
    ) -> None:
        """Same trades, different starting equity → drawdown % shifts."""
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("110"),
                qty=10, pnl=Decimal("100"),
                entry_ts=_ts(0), exit_ts=_ts(60),
            )
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("90"),
                qty=10, pnl=Decimal("-100"),
                entry_ts=_ts(120), exit_ts=_ts(180),
            )
            await s.commit()

            small = await build_equity_curve(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                starting_equity=Decimal("1000"),
                from_ts=None, to_ts=None, db=s,
            )
            large = await build_equity_curve(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                starting_equity=Decimal("1000000"),
                from_ts=None, to_ts=None, db=s,
            )
        # small: 1000 → 1100 → 1000. Peak 1100, drop to 1000 →
        #   drawdown ≈ 9.09%.
        assert small.points[2].drawdown_pct == pytest.approx(
            (1100 - 1000) / 1100 * 100, abs=1e-6
        )
        # large: 1000000 → 1000100 → 1000000. drawdown ≈ 0.01%.
        assert large.points[2].drawdown_pct == pytest.approx(
            (1000100 - 1000000) / 1000100 * 100, abs=1e-6
        )


# ═══════════════════════════════════════════════════════════════════════
# get_trades
# ═══════════════════════════════════════════════════════════════════════


class TestGetTrades:
    @pytest.mark.asyncio
    async def test_open_and_closed_mix(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            # Closed trade.
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("22500"), exit_price=Decimal("22550"),
                qty=50, pnl=Decimal("2500"),
                entry_ts=_ts(0), exit_ts=_ts(60),
                exit_reason=MarkerExitReason.TAKE_PROFIT,
            )
            # Open trade — entry only.
            open_entry = await emit_entry_marker(
                s, strategy_id=strat.id, user_id=user.id,
                symbol="BANKNIFTY", exchange="NSE",
                side=MarkerSide.SHORT_ENTRY,
                price=Decimal("48000"), quantity=15,
                timestamp_utc=_ts(120), mode=MarkerMode.PAPER,
            )
            await s.commit()

            resp = await get_trades(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None,
                limit=100, offset=0, db=s,
            )

        assert resp.pagination.total == 2
        assert len(resp.trades) == 2
        # Ordered by entry timestamp ascending.
        assert resp.trades[0].symbol == "NIFTY"
        assert resp.trades[0].side == "LONG"
        assert resp.trades[0].pnl == Decimal("2500")
        assert resp.trades[0].exit_reason == MarkerExitReason.TAKE_PROFIT
        assert resp.trades[0].duration_minutes == pytest.approx(1.0)
        # pnl_pct = 2500 / (22500 * 50) * 100 ≈ 0.222%.
        assert resp.trades[0].pnl_pct == pytest.approx(
            float(Decimal("2500") / (Decimal("22500") * Decimal("50"))) * 100,
            abs=1e-6,
        )

        assert resp.trades[1].symbol == "BANKNIFTY"
        assert resp.trades[1].side == "SHORT"
        assert resp.trades[1].entry_marker_id == open_entry.id
        assert resp.trades[1].exit_marker_id is None
        assert resp.trades[1].pnl is None
        assert resp.trades[1].pnl_pct is None
        assert resp.trades[1].duration_minutes is None
        assert resp.trades[1].exit_reason is None

    @pytest.mark.asyncio
    async def test_pagination(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            for i in range(5):
                await _seed_closed_trade(
                    s, user=user, strategy=strat, symbol=f"SYM{i}",
                    side=MarkerSide.LONG_ENTRY,
                    entry_price=Decimal("100"), exit_price=Decimal("101"),
                    qty=1, pnl=Decimal("1"),
                    entry_ts=_ts(i * 120), exit_ts=_ts(i * 120 + 60),
                )
            await s.commit()

            page = await get_trades(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None,
                limit=2, offset=2, db=s,
            )
        assert page.pagination.total == 5
        assert page.pagination.limit == 2
        assert page.pagination.offset == 2
        assert len(page.trades) == 2
        # Slice at offset 2 → SYM2, SYM3 (entries seeded SYM0..SYM4 in order).
        assert [t.symbol for t in page.trades] == ["SYM2", "SYM3"]

    @pytest.mark.asyncio
    async def test_mode_filter(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="P", side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("110"),
                qty=10, pnl=Decimal("100"),
                entry_ts=_ts(0), exit_ts=_ts(60),
                mode=MarkerMode.PAPER,
            )
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="L", side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("110"),
                qty=10, pnl=Decimal("100"),
                entry_ts=_ts(120), exit_ts=_ts(180),
                mode=MarkerMode.LIVE,
            )
            await s.commit()
            paper = await get_trades(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None,
                limit=100, offset=0, db=s,
            )
            live = await get_trades(
                strategy_id=strat.id, mode=MarkerMode.LIVE,
                from_ts=None, to_ts=None,
                limit=100, offset=0, db=s,
            )
        assert paper.pagination.total == 1
        assert paper.trades[0].symbol == "P"
        assert live.pagination.total == 1
        assert live.trades[0].symbol == "L"

    @pytest.mark.asyncio
    async def test_window_filter(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="EARLY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("101"),
                qty=1, pnl=Decimal("1"),
                entry_ts=_ts(0), exit_ts=_ts(30),
            )
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="LATE",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("101"),
                qty=1, pnl=Decimal("1"),
                entry_ts=_ts(3600), exit_ts=_ts(3660),
            )
            await s.commit()
            # Window covers only the LATE entry.
            late = await get_trades(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=_ts(1800), to_ts=_ts(7200),
                limit=100, offset=0, db=s,
            )
        assert late.pagination.total == 1
        assert late.trades[0].symbol == "LATE"

    @pytest.mark.asyncio
    async def test_short_position_pnl_pct_correct(
        self, engine_and_session, seeded_strategy
    ) -> None:
        """SHORT trade: entry 100, exit 90, qty 10, pnl 100 → pnl_pct = 10%."""
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="S",
                side=MarkerSide.SHORT_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("90"),
                qty=10, pnl=Decimal("100"),
                entry_ts=_ts(0), exit_ts=_ts(60),
            )
            await s.commit()
            resp = await get_trades(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, limit=10, offset=0, db=s,
            )
        assert resp.trades[0].side == "SHORT"
        assert resp.trades[0].pnl_pct == pytest.approx(10.0)


class TestSharpeProxy:
    @pytest.mark.asyncio
    async def test_two_identical_trades_zero_variance_returns_none(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            for i in range(2):
                await _seed_closed_trade(
                    s, user=user, strategy=strat, symbol="NIFTY",
                    side=MarkerSide.LONG_ENTRY,
                    entry_price=Decimal("100"), exit_price=Decimal("110"),
                    qty=10, pnl=Decimal("100"),
                    entry_ts=_ts(i * 120), exit_ts=_ts(i * 120 + 60),
                )
            await s.commit()
            m = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, db=s,
            )
        assert m.sharpe_ratio_proxy is None  # zero variance.

    @pytest.mark.asyncio
    async def test_one_trade_returns_none(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("110"),
                qty=10, pnl=Decimal("100"),
                entry_ts=_ts(0), exit_ts=_ts(60),
            )
            await s.commit()
            m = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, db=s,
            )
        assert m.sharpe_ratio_proxy is None

    @pytest.mark.asyncio
    async def test_two_distinct_trades_real_sharpe(
        self, engine_and_session, seeded_strategy
    ) -> None:
        _engine, maker = engine_and_session
        user, strat = seeded_strategy
        async with maker() as s:
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("110"),
                qty=10, pnl=Decimal("100"),
                entry_ts=_ts(0), exit_ts=_ts(60),
            )
            await _seed_closed_trade(
                s, user=user, strategy=strat, symbol="NIFTY",
                side=MarkerSide.LONG_ENTRY,
                entry_price=Decimal("100"), exit_price=Decimal("90"),
                qty=10, pnl=Decimal("-100"),
                entry_ts=_ts(120), exit_ts=_ts(180),
            )
            await s.commit()
            m = await aggregate_metrics(
                strategy_id=strat.id, mode=MarkerMode.PAPER,
                from_ts=None, to_ts=None, db=s,
            )
        # mean = 0, so sharpe = 0 / stdev = 0.0 (NOT None — variance > 0).
        assert m.sharpe_ratio_proxy is not None
        assert math.isfinite(m.sharpe_ratio_proxy)
        assert m.sharpe_ratio_proxy == pytest.approx(0.0, abs=1e-9)
