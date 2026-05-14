"""Tests for :mod:`app.api.trade_markers` (Phase A HTTP routes).

The route is not registered in ``main.py`` (PATCH_INSTRUCTIONS_PHASE_A
gates that), so we mount a private :class:`FastAPI` instance that
includes only ``trade_markers.router`` for the test run — same pattern
as ``tests/api/test_chart_markers.py``.

DB strategy: real in-memory aiosqlite engine wired into the
``get_session`` dependency. This gives us actual SQL execution (so
the ``side``/``mode`` filter compositions, pagination, and aggregate
queries are exercised, not just the FastAPI plumbing).
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
from app.api.trade_markers import router as trade_markers_router
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
    """Fresh aiosqlite engine + sessionmaker per test."""
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
    """Insert one user + two strategies (one owned, one foreign)."""
    _engine, maker = engine_and_session
    async with maker() as s:
        u = User(
            email="phase-a-api@tradetri.com",
            password_hash="x",
            is_active=True,
        )
        s.add(u)
        await s.flush()

        owned = Strategy(user_id=u.id, name="owned", is_active=True)
        s.add(owned)

        other_user = User(
            email="other@tradetri.com",
            password_hash="x",
            is_active=True,
        )
        s.add(other_user)
        await s.flush()

        foreign = Strategy(
            user_id=other_user.id, name="foreign", is_active=True
        )
        s.add(foreign)
        await s.commit()
        yield u, owned, foreign


def _ts(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 5, 14, 9, 15, 0, tzinfo=UTC) + timedelta(
        seconds=offset_seconds
    )


@pytest_asyncio.fixture
async def seeded_with_markers(
    engine_and_session, seeded
) -> tuple[User, Strategy, Strategy]:
    """Seed two PAPER markers + one LIVE marker against ``owned``."""
    _engine, maker = engine_and_session
    user, owned, foreign = seeded
    async with maker() as s:
        entry = await emit_entry_marker(
            s,
            strategy_id=owned.id,
            user_id=user.id,
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=_ts(),
            mode=MarkerMode.PAPER,
        )
        await emit_exit_marker(
            s,
            entry_marker_id=entry.id,
            strategy_id=owned.id,
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
        await emit_entry_marker(
            s,
            strategy_id=owned.id,
            user_id=user.id,
            symbol="BANKNIFTY",
            exchange="NSE",
            side=MarkerSide.SHORT_ENTRY,
            price=Decimal("48000"),
            quantity=15,
            timestamp_utc=_ts(120),
            mode=MarkerMode.LIVE,
        )
        await s.commit()
    return user, owned, foreign


@pytest.fixture
def app(engine_and_session, seeded_with_markers) -> FastAPI:
    _engine, maker = engine_and_session
    user, _owned, _foreign = seeded_with_markers

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    def _override_user() -> User:
        return user

    app = FastAPI()
    app.include_router(trade_markers_router)
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_active_user] = _override_user
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# GET /api/markers
# ═══════════════════════════════════════════════════════════════════════


class TestListMarkers:
    def test_paper_mode_returns_two(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={"strategy_id": str(owned.id), "mode": "PAPER"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["markers"]) == 2
        # Ordered by timestamp ascending.
        ts0 = body["markers"][0]["timestamp_utc"]
        ts1 = body["markers"][1]["timestamp_utc"]
        assert ts0 < ts1

    def test_live_mode_returns_one(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={"strategy_id": str(owned.id), "mode": "LIVE"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["markers"][0]["symbol"] == "BANKNIFTY"

    def test_missing_mode_400(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers", params={"strategy_id": str(owned.id)}
        )
        # FastAPI returns 422 for missing required query params.
        assert resp.status_code == 422

    def test_foreign_strategy_403(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, _owned, foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={"strategy_id": str(foreign.id), "mode": "PAPER"},
        )
        assert resp.status_code == 403
        assert "access nahi hai" in resp.json()["detail"]

    def test_nonexistent_strategy_403_not_404(
        self, client: TestClient
    ) -> None:
        resp = client.get(
            "/api/markers",
            params={
                "strategy_id": str(uuid.uuid4()),
                "mode": "PAPER",
            },
        )
        # 403 deliberately — existence must not be probable.
        assert resp.status_code == 403

    def test_filter_symbol_and_side(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={
                "strategy_id": str(owned.id),
                "mode": "PAPER",
                "symbol": "NIFTY",
                "side": "LONG_EXIT",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["markers"][0]["side"] == "LONG_EXIT"

    def test_pagination(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={
                "strategy_id": str(owned.id),
                "mode": "PAPER",
                "limit": 1,
                "offset": 1,
            },
        )
        body = resp.json()
        assert body["total"] == 2
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert len(body["markers"]) == 1

    def test_limit_over_500_rejected(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={
                "strategy_id": str(owned.id),
                "mode": "PAPER",
                "limit": 501,
            },
        )
        assert resp.status_code == 422

    def test_naive_from_ts_rejected(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={
                "strategy_id": str(owned.id),
                "mode": "PAPER",
                "from": "2026-05-14T09:15:00",  # naive
            },
        )
        assert resp.status_code == 400
        assert "timezone-aware" in resp.json()["detail"]

    def test_inverted_window_rejected(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            "/api/markers",
            params={
                "strategy_id": str(owned.id),
                "mode": "PAPER",
                "from": "2026-05-15T09:15:00+00:00",
                "to": "2026-05-14T09:15:00+00:00",
            },
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════
# GET /api/markers/strategy/{id}/summary
# ═══════════════════════════════════════════════════════════════════════


class TestSummary:
    def test_paper_summary(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            f"/api/markers/strategy/{owned.id}/summary",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["trade_count"] == 1
        # JSON serialises Decimal as string under model_dump_json default.
        assert Decimal(body["total_pnl"]) == Decimal("2500")
        assert body["win_rate"] == 1.0
        assert Decimal(body["avg_pnl"]) == Decimal("2500")

    def test_live_summary_no_exits(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, owned, _foreign = seeded_with_markers
        resp = client.get(
            f"/api/markers/strategy/{owned.id}/summary",
            params={"mode": "LIVE"},
        )
        body = resp.json()
        assert body["trade_count"] == 0
        assert Decimal(body["total_pnl"]) == Decimal("0")
        assert body["win_rate"] == 0.0

    def test_foreign_strategy_summary_403(
        self,
        client: TestClient,
        seeded_with_markers: tuple[User, Strategy, Strategy],
    ) -> None:
        _user, _owned, foreign = seeded_with_markers
        resp = client.get(
            f"/api/markers/strategy/{foreign.id}/summary",
            params={"mode": "PAPER"},
        )
        assert resp.status_code == 403
