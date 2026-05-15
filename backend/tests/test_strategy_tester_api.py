"""HTTP-route tests for :mod:`app.api.strategy_tester` (Phase B).

The router isn't registered in ``main.py`` (PATCH_INSTRUCTIONS_PHASE_B
gates that), so we mount a private :class:`FastAPI` instance that
includes only ``strategy_tester.router`` for the test run — same pattern
as ``tests/test_trade_markers_api.py``.

DB strategy: real in-memory aiosqlite engine wired into ``get_session``
so the actual SQL composition (entry/exit pairing, mode filter,
pagination) is exercised, not just the FastAPI plumbing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_current_active_user
from app.api.strategy_tester import router as strategy_tester_router
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.trade_marker import MarkerExitReason, MarkerMode, MarkerSide
from app.db.models.user import User
from app.db.session import get_session
from app.services.marker_emitter import emit_entry_marker, emit_exit_marker


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
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
async def seeded(
    engine_and_session,
) -> AsyncIterator[tuple[User, Strategy, Strategy]]:
    """Seed: one user owning one strategy + a foreign user/strategy."""
    _engine, maker = engine_and_session
    async with maker() as s:
        u = User(
            email="phase-b-api@tradetri.com",
            password_hash="x",
            is_active=True,
        )
        s.add(u)
        await s.flush()
        owned = Strategy(user_id=u.id, name="phase-b-owned", is_active=True)
        s.add(owned)

        other = User(
            email="other-phase-b@tradetri.com",
            password_hash="x",
            is_active=True,
        )
        s.add(other)
        await s.flush()
        foreign = Strategy(user_id=other.id, name="phase-b-foreign", is_active=True)
        s.add(foreign)
        await s.commit()
        yield u, owned, foreign


def _ts(seconds: int = 0) -> datetime:
    return datetime(2026, 5, 14, 9, 15, 0, tzinfo=UTC) + timedelta(seconds=seconds)


@pytest_asyncio.fixture
async def seeded_with_trades(
    engine_and_session, seeded
) -> tuple[User, Strategy, Strategy]:
    """Seed two PAPER closed trades + one LIVE open trade against ``owned``."""
    _engine, maker = engine_and_session
    user, owned, foreign = seeded
    async with maker() as s:
        # Closed trade #1 — winner (+500).
        e1 = await emit_entry_marker(
            s, strategy_id=owned.id, user_id=user.id,
            symbol="NIFTY", exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"), quantity=50,
            timestamp_utc=_ts(0), mode=MarkerMode.PAPER,
        )
        await emit_exit_marker(
            s, entry_marker_id=e1.id, strategy_id=owned.id, user_id=user.id,
            symbol="NIFTY", exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22510"), quantity=50,
            timestamp_utc=_ts(60), mode=MarkerMode.PAPER,
            pnl=Decimal("500"), exit_reason=MarkerExitReason.TAKE_PROFIT,
        )
        # Closed trade #2 — loser (−200).
        e2 = await emit_entry_marker(
            s, strategy_id=owned.id, user_id=user.id,
            symbol="NIFTY", exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"), quantity=50,
            timestamp_utc=_ts(120), mode=MarkerMode.PAPER,
        )
        await emit_exit_marker(
            s, entry_marker_id=e2.id, strategy_id=owned.id, user_id=user.id,
            symbol="NIFTY", exchange="NSE",
            side=MarkerSide.LONG_EXIT,
            price=Decimal("22496"), quantity=50,
            timestamp_utc=_ts(180), mode=MarkerMode.PAPER,
            pnl=Decimal("-200"), exit_reason=MarkerExitReason.STOP_LOSS,
        )
        # Open LIVE trade.
        await emit_entry_marker(
            s, strategy_id=owned.id, user_id=user.id,
            symbol="BANKNIFTY", exchange="NSE",
            side=MarkerSide.SHORT_ENTRY,
            price=Decimal("48000"), quantity=15,
            timestamp_utc=_ts(240), mode=MarkerMode.LIVE,
        )
        await s.commit()
    return user, owned, foreign


@pytest.fixture
def app(engine_and_session, seeded_with_trades) -> FastAPI:
    """FastAPI test app with auth + session deps overridden."""
    _engine, maker = engine_and_session
    user, _owned, _foreign = seeded_with_trades

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    def _override_user() -> User:
        return user

    app = FastAPI()
    app.include_router(strategy_tester_router)
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_active_user] = _override_user
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def app_no_auth(engine_and_session, seeded_with_trades) -> FastAPI:
    """Same as ``app`` but WITHOUT the auth override — used to assert 401."""
    _engine, maker = engine_and_session

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = FastAPI()
    app.include_router(strategy_tester_router)
    app.dependency_overrides[get_session] = _override_session
    return app


@pytest.fixture
def client_no_auth(app_no_auth: FastAPI) -> TestClient:
    return TestClient(app_no_auth)


# ═══════════════════════════════════════════════════════════════════════
# /metrics
# ═══════════════════════════════════════════════════════════════════════


class TestMetricsEndpoint:
    def test_owned_paper_returns_two_trades(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/metrics",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_trades"] == 2
        assert body["profitable_trades"] == 1
        assert Decimal(body["total_pnl"]) == Decimal("300")
        assert body["win_rate_pct"] == 50.0

    def test_live_returns_zero_trades_open_only(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/metrics",
            params={"mode": "LIVE"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # The seeded LIVE marker is an open entry — no exits, no closed
        # trades. Metrics is over EXITs, so all-zero.
        assert body["total_trades"] == 0
        assert Decimal(body["total_pnl"]) == Decimal("0")

    def test_backtest_empty(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/metrics",
            params={"mode": "BACKTEST"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_trades"] == 0

    def test_missing_mode_422(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(f"/api/strategy-tester/{owned.id}/metrics")
        assert resp.status_code == 422

    def test_foreign_strategy_403(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, _owned, foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{foreign.id}/metrics",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 403
        assert "access nahi hai" in resp.json()["detail"]

    def test_nonexistent_strategy_403_not_404(
        self, client: TestClient
    ) -> None:
        resp = client.get(
            f"/api/strategy-tester/{uuid.uuid4()}/metrics",
            params={"mode": "PAPER"},
        )
        # 403 deliberately — existence must not be probable.
        assert resp.status_code == 403

    def test_unauthenticated_401(
        self,
        client_no_auth: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client_no_auth.get(
            f"/api/strategy-tester/{owned.id}/metrics",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 401

    def test_naive_from_ts_400(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/metrics",
            params={"mode": "PAPER", "from": "2026-05-14T09:15:00"},
        )
        assert resp.status_code == 400
        assert "timezone-aware" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════
# /equity
# ═══════════════════════════════════════════════════════════════════════


class TestEquityEndpoint:
    def test_owned_paper_walks_two_trades(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/equity",
            params={"mode": "PAPER", "starting_equity": "100000"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Anchor + 2 trades = 3 points.
        assert len(body["points"]) == 3
        assert Decimal(body["starting_equity"]) == Decimal("100000")
        assert Decimal(body["points"][0]["equity"]) == Decimal("100000")
        assert Decimal(body["points"][1]["equity"]) == Decimal("100500")
        assert Decimal(body["points"][2]["equity"]) == Decimal("100300")
        assert Decimal(body["ending_equity"]) == Decimal("100300")
        assert Decimal(body["max_equity"]) == Decimal("100500")
        assert Decimal(body["min_equity"]) == Decimal("100000")

    def test_starting_equity_default_100k(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/equity",
            params={"mode": "PAPER"},  # no starting_equity → default
        )
        assert resp.status_code == 200
        assert Decimal(resp.json()["starting_equity"]) == Decimal("100000")

    def test_custom_starting_equity(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/equity",
            params={"mode": "PAPER", "starting_equity": "50000"},
        )
        body = resp.json()
        assert Decimal(body["starting_equity"]) == Decimal("50000")
        assert Decimal(body["points"][0]["equity"]) == Decimal("50000")
        assert Decimal(body["points"][1]["equity"]) == Decimal("50500")
        assert Decimal(body["points"][2]["equity"]) == Decimal("50300")

    def test_starting_equity_must_be_positive(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/equity",
            params={"mode": "PAPER", "starting_equity": "0"},
        )
        assert resp.status_code == 422

    def test_foreign_strategy_403(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, _owned, foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{foreign.id}/equity",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# /trades
# ═══════════════════════════════════════════════════════════════════════


class TestTradesEndpoint:
    def test_owned_paper_returns_two(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 2
        assert body["pagination"]["limit"] == 100
        assert body["pagination"]["offset"] == 0
        assert body["mode"] == "PAPER"
        # Both PAPER trades are closed.
        for trade in body["trades"]:
            assert trade["exit_marker_id"] is not None
            assert trade["pnl"] is not None

    def test_live_returns_one_open(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={"mode": "LIVE"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert len(body["trades"]) == 1
        trade = body["trades"][0]
        assert trade["symbol"] == "BANKNIFTY"
        assert trade["side"] == "SHORT"
        assert trade["exit_marker_id"] is None
        assert trade["exit_time"] is None
        assert trade["pnl"] is None
        assert trade["pnl_pct"] is None
        assert trade["duration_minutes"] is None

    def test_pagination(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={"mode": "PAPER", "limit": 1, "offset": 1},
        )
        body = resp.json()
        assert body["pagination"]["total"] == 2
        assert body["pagination"]["limit"] == 1
        assert body["pagination"]["offset"] == 1
        assert len(body["trades"]) == 1

    def test_limit_over_500_rejected(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={"mode": "PAPER", "limit": 501},
        )
        assert resp.status_code == 422

    def test_symbol_filter(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={"mode": "PAPER", "symbol": "NIFTY"},
        )
        body = resp.json()
        assert body["pagination"]["total"] == 2
        assert all(t["symbol"] == "NIFTY" for t in body["trades"])

    def test_window_excludes_out_of_range(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        # Window starts after all PAPER entries (which span 0..120s).
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={
                "mode": "PAPER",
                "from": "2026-05-14T10:00:00+00:00",
            },
        )
        body = resp.json()
        assert body["pagination"]["total"] == 0

    def test_inverted_window_400(
        self,
        client: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={
                "mode": "PAPER",
                "from": "2026-05-14T11:00:00+00:00",
                "to": "2026-05-14T10:00:00+00:00",
            },
        )
        assert resp.status_code == 400

    def test_unauthenticated_401(
        self,
        client_no_auth: TestClient,
        seeded_with_trades: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_trades
        resp = client_no_auth.get(
            f"/api/strategy-tester/{owned.id}/trades",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 401
