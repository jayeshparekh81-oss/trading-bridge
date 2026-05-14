"""Tests for :mod:`app.api.chart_markers` and the supporting service.

Day-3 prep / scaffold — the route is NOT registered in main.py yet,
so this test file mounts a private FastAPI app that includes only
the markers router (mirroring the pattern in
``conftest.py::chart_app``). Every dependency that touches the live
DB or Redis is faked.

Coverage strategy
    * Schema (chart_marker.py) — direct construction + JSON
      round-trip + invariant checks.
    * Service (chart_marker_service.py) — pure functions hit
      directly with hand-crafted PaperTradeRow MagicMocks; the
      list_sessions / list_trades dependencies are monkeypatched at
      the import site.
    * Route (chart_markers.py) — TestClient + dependency overrides.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import chart_markers as markers_route_mod
from app.api.chart_markers import _markers_cache_key
from app.api.chart_markers import router as markers_router
from app.api.deps import get_current_active_user
from app.core import redis_client
from app.db.session import get_session
from app.schemas.chart_marker import (
    ChartMarker,
    ChartMarkerKind,
    ChartMarkersResponse,
)
from app.services import chart_marker_service as svc


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def fake_redis(monkeypatch: pytest.MonkeyPatch):
    """Process-wide async Redis substituted for fakeredis."""
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_STRATEGY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_OTHER_STRATEGY_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def fake_user() -> MagicMock:
    user = MagicMock()
    user.id = _USER_ID
    user.is_active = True
    return user


@pytest.fixture
def markers_app(fake_user: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(markers_router)
    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    return app


@pytest.fixture
def client(markers_app: FastAPI) -> TestClient:
    return TestClient(markers_app)


def _trade_row(
    *,
    entry_at: datetime,
    exit_at: datetime | None = None,
    symbol: str = "NIFTY",
    side: str = "BUY",
    quantity: int = 50,
    entry_price: Decimal = Decimal("22500.00"),
    exit_price: Decimal | None = Decimal("22550.00"),
    pnl: Decimal | None = Decimal("2500.00"),
    exit_reason: str | None = "target",
) -> MagicMock:
    """Hand-crafted PaperTradeRow stand-in."""
    row = MagicMock()
    row.entry_at = entry_at
    row.exit_at = exit_at
    row.symbol = symbol
    row.side = side
    row.quantity = quantity
    row.entry_price = entry_price
    row.exit_price = exit_price
    row.pnl = pnl
    row.exit_reason = exit_reason
    return row


def _session_row(
    *,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID = _USER_ID,
    strategy_id: uuid.UUID = _STRATEGY_ID,
) -> MagicMock:
    row = MagicMock()
    row.id = session_id or uuid.uuid4()
    row.user_id = user_id
    row.strategy_id = strategy_id
    return row


def _utc(year: int, month: int, day: int, hour: int = 9, minute: int = 30) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# ═══════════════════════════════════════════════════════════════════════
# Schema layer — chart_marker.py
# ═══════════════════════════════════════════════════════════════════════


class TestChartMarkerSchema:
    def test_minimal_entry_marker_round_trips_through_json(self) -> None:
        m = ChartMarker(
            kind=ChartMarkerKind.ENTRY,
            timestamp=_utc(2026, 5, 12),
            price=Decimal("22500.50"),
            quantity=75,
            side="BUY",
        )
        as_json = m.model_dump_json()
        roundtripped = ChartMarker.model_validate_json(as_json)
        assert roundtripped == m
        # Decimal serialises as a JSON string per the chart-module wire
        # convention (matches Candle.open/close).
        assert '"22500.50"' in as_json or '"price":"22500.50"' in as_json

    def test_exit_marker_carries_pnl_and_reason(self) -> None:
        m = ChartMarker(
            kind=ChartMarkerKind.TP_HIT,
            timestamp=_utc(2026, 5, 12, 10),
            price=Decimal("22600.00"),
            quantity=75,
            side="BUY",
            pnl=Decimal("7500.00"),
            exit_reason="target",
        )
        assert m.pnl == Decimal("7500.00")
        assert m.exit_reason == "target"

    def test_extra_field_is_rejected(self) -> None:
        with pytest.raises(Exception):
            ChartMarker(  # type: ignore[call-arg]
                kind=ChartMarkerKind.ENTRY,
                timestamp=_utc(2026, 5, 12),
                price=Decimal("22500"),
                quantity=10,
                side="BUY",
                extra="leak",
            )

    def test_response_envelope_round_trip(self) -> None:
        env = ChartMarkersResponse(
            strategy_id=str(_STRATEGY_ID),
            symbol="NIFTY",
            timeframe="5m",
            from_ts=_utc(2026, 5, 12),
            to_ts=_utc(2026, 5, 12, 15, 30),
            cached=False,
            markers=[],
        )
        rt = ChartMarkersResponse.model_validate_json(env.model_dump_json())
        assert rt == env


# ═══════════════════════════════════════════════════════════════════════
# Service layer — chart_marker_service.py
# ═══════════════════════════════════════════════════════════════════════


class TestClassifyExit:
    @pytest.mark.parametrize("reason", ["target"])
    def test_target_maps_to_tp_hit(self, reason: str) -> None:
        assert svc.classify_exit(reason) == ChartMarkerKind.TP_HIT

    @pytest.mark.parametrize(
        "reason", ["stop_loss", "trailing_stop"]
    )
    def test_stop_variants_map_to_sl_hit(self, reason: str) -> None:
        assert svc.classify_exit(reason) == ChartMarkerKind.SL_HIT

    @pytest.mark.parametrize(
        "reason",
        [
            "partial",
            "indicator",
            "reverse_signal",
            "time",
            "square_off",
            "backtest_end",
            "future_unknown_exit_type_added_in_2027",
        ],
    )
    def test_other_reasons_collapse_to_exit(self, reason: str) -> None:
        assert svc.classify_exit(reason) == ChartMarkerKind.EXIT

    def test_none_defaults_to_exit_defensive(self) -> None:
        # Open trade callers don't invoke this with None, but the
        # function is defensive total.
        assert svc.classify_exit(None) == ChartMarkerKind.EXIT


class TestMarkersForTrade:
    def test_closed_trade_emits_entry_plus_exit(self) -> None:
        trade = _trade_row(
            entry_at=_utc(2026, 5, 12, 10, 0),
            exit_at=_utc(2026, 5, 12, 11, 30),
            exit_reason="target",
        )
        markers = svc._markers_for_trade(
            trade,
            from_ts=_utc(2026, 5, 12, 9, 0),
            to_ts=_utc(2026, 5, 12, 15, 30),
            symbol="NIFTY",
        )
        assert [m.kind for m in markers] == [
            ChartMarkerKind.ENTRY,
            ChartMarkerKind.TP_HIT,
        ]

    def test_open_trade_emits_only_entry(self) -> None:
        trade = _trade_row(
            entry_at=_utc(2026, 5, 12, 10, 0),
            exit_at=None,
            exit_price=None,
            pnl=None,
            exit_reason=None,
        )
        markers = svc._markers_for_trade(
            trade,
            from_ts=_utc(2026, 5, 12),
            to_ts=_utc(2026, 5, 12, 15, 30),
            symbol="NIFTY",
        )
        assert len(markers) == 1
        assert markers[0].kind == ChartMarkerKind.ENTRY

    def test_entry_outside_window_returns_empty(self) -> None:
        trade = _trade_row(entry_at=_utc(2026, 5, 11, 10, 0))
        markers = svc._markers_for_trade(
            trade,
            from_ts=_utc(2026, 5, 12),
            to_ts=_utc(2026, 5, 12, 15, 30),
            symbol="NIFTY",
        )
        assert markers == []

    def test_exit_past_upper_bound_keeps_only_entry(self) -> None:
        trade = _trade_row(
            entry_at=_utc(2026, 5, 12, 14, 0),
            exit_at=_utc(2026, 5, 13, 9, 30),  # next day
            exit_reason="square_off",
        )
        markers = svc._markers_for_trade(
            trade,
            from_ts=_utc(2026, 5, 12, 9, 0),
            to_ts=_utc(2026, 5, 12, 15, 30),
            symbol="NIFTY",
        )
        assert [m.kind for m in markers] == [ChartMarkerKind.ENTRY]

    def test_symbol_mismatch_returns_empty(self) -> None:
        trade = _trade_row(
            entry_at=_utc(2026, 5, 12, 10, 0),
            symbol="BANKNIFTY",
        )
        markers = svc._markers_for_trade(
            trade,
            from_ts=_utc(2026, 5, 12),
            to_ts=_utc(2026, 5, 12, 15, 30),
            symbol="NIFTY",
        )
        assert markers == []

    def test_stop_loss_exit_classifies_as_sl_hit(self) -> None:
        trade = _trade_row(
            entry_at=_utc(2026, 5, 12, 10, 0),
            exit_at=_utc(2026, 5, 12, 10, 30),
            exit_price=Decimal("22450.00"),
            pnl=Decimal("-3750.00"),
            exit_reason="stop_loss",
        )
        markers = svc._markers_for_trade(
            trade,
            from_ts=_utc(2026, 5, 12),
            to_ts=_utc(2026, 5, 12, 15, 30),
            symbol="NIFTY",
        )
        assert markers[1].kind == ChartMarkerKind.SL_HIT
        assert markers[1].pnl == Decimal("-3750.00")
        assert markers[1].exit_reason == "stop_loss"


class TestBuildMarkersForStrategy:
    @pytest.mark.asyncio
    async def test_no_sessions_returns_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(svc, "list_sessions", AsyncMock(return_value=[]))
        # list_trades must not even be called.
        list_trades = AsyncMock()
        monkeypatch.setattr(svc, "list_trades", list_trades)

        out = await svc.build_markers_for_strategy(
            db=AsyncMock(),
            user_id=_USER_ID,
            strategy_id=_STRATEGY_ID,
            symbol="NIFTY",
            from_ts=_utc(2026, 5, 12),
            to_ts=_utc(2026, 5, 12, 15, 30),
        )
        assert out == []
        list_trades.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_walks_every_session_and_sorts_globally(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        s1 = _session_row()
        s2 = _session_row()
        # Sessions are walked oldest first by store.list_sessions; the
        # service then must sort the FLAT marker list globally across
        # sessions, not just within each session.
        trades_for_s1 = [
            _trade_row(
                entry_at=_utc(2026, 5, 12, 11, 0),
                exit_at=_utc(2026, 5, 12, 12, 0),
            ),
        ]
        trades_for_s2 = [
            _trade_row(
                entry_at=_utc(2026, 5, 12, 9, 30),
                exit_at=_utc(2026, 5, 12, 10, 0),
                exit_reason="stop_loss",
            ),
        ]
        monkeypatch.setattr(
            svc, "list_sessions", AsyncMock(return_value=[s1, s2])
        )

        async def fake_list_trades(_db: Any, *, session_id: uuid.UUID):
            if session_id == s1.id:
                return trades_for_s1
            if session_id == s2.id:
                return trades_for_s2
            return []

        monkeypatch.setattr(
            svc,
            "list_trades",
            AsyncMock(side_effect=fake_list_trades),
        )

        out = await svc.build_markers_for_strategy(
            db=AsyncMock(),
            user_id=_USER_ID,
            strategy_id=_STRATEGY_ID,
            symbol="NIFTY",
            from_ts=_utc(2026, 5, 12),
            to_ts=_utc(2026, 5, 12, 15, 30),
        )
        # Globally sorted: s2.entry (09:30) → s2.exit (10:00) →
        # s1.entry (11:00) → s1.exit (12:00).
        assert [m.timestamp.hour for m in out] == [9, 10, 11, 12]
        assert [m.kind for m in out] == [
            ChartMarkerKind.ENTRY,
            ChartMarkerKind.SL_HIT,
            ChartMarkerKind.ENTRY,
            ChartMarkerKind.TP_HIT,
        ]


# ═══════════════════════════════════════════════════════════════════════
# Route layer — chart_markers.py
# ═══════════════════════════════════════════════════════════════════════


def _params(**overrides: Any) -> dict[str, str]:
    base = {
        "strategy_id": str(_STRATEGY_ID),
        "symbol": "NIFTY",
        "timeframe": "5m",
        "from": "2026-05-12T09:15:00+05:30",
        "to": "2026-05-12T15:30:00+05:30",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return base


def _install_db_override(
    client: TestClient,
    *,
    strategy_row: MagicMock | None,
) -> None:
    """Install a fake DB session that returns ``strategy_row`` for
    every ``execute(...)``. ``None`` simulates 'strategy not found'."""

    async def get_fake_session() -> Any:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=strategy_row)
        session.execute = AsyncMock(return_value=result)
        yield session

    client.app.dependency_overrides[get_session] = get_fake_session


def _install_build_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    markers: list[ChartMarker] | Exception,
) -> AsyncMock:
    """Stub out build_markers_for_strategy at the route's import site."""
    if isinstance(markers, Exception):
        stub = AsyncMock(side_effect=markers)
    else:
        stub = AsyncMock(return_value=markers)
    monkeypatch.setattr(
        markers_route_mod, "build_markers_for_strategy", stub
    )
    return stub


class TestGetChartMarkers:
    def test_happy_path_returns_markers(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        strategy = MagicMock()
        strategy.id = _STRATEGY_ID
        strategy.user_id = _USER_ID
        _install_db_override(client, strategy_row=strategy)

        markers = [
            ChartMarker(
                kind=ChartMarkerKind.ENTRY,
                timestamp=_utc(2026, 5, 12, 10),
                price=Decimal("22500"),
                quantity=50,
                side="BUY",
            ),
            ChartMarker(
                kind=ChartMarkerKind.TP_HIT,
                timestamp=_utc(2026, 5, 12, 11),
                price=Decimal("22550"),
                quantity=50,
                side="BUY",
                pnl=Decimal("2500"),
                exit_reason="target",
            ),
        ]
        _install_build_stub(monkeypatch, markers=markers)

        resp = client.get("/api/chart/markers", params=_params())
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "NIFTY"
        assert body["cached"] is False
        assert len(body["markers"]) == 2
        assert body["markers"][0]["kind"] == "ENTRY"
        assert body["markers"][1]["kind"] == "TP_HIT"

    def test_second_call_returns_cached_envelope(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        strategy = MagicMock()
        strategy.id = _STRATEGY_ID
        strategy.user_id = _USER_ID
        _install_db_override(client, strategy_row=strategy)

        build_stub = _install_build_stub(monkeypatch, markers=[])

        resp1 = client.get("/api/chart/markers", params=_params())
        assert resp1.status_code == 200
        assert resp1.json()["cached"] is False

        resp2 = client.get("/api/chart/markers", params=_params())
        assert resp2.status_code == 200
        assert resp2.json()["cached"] is True
        # Second call must NOT hit the service layer.
        assert build_stub.await_count == 1

    def test_strategy_owned_by_other_user_returns_403(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        other = MagicMock()
        other.id = _STRATEGY_ID
        other.user_id = uuid.UUID(
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        )
        _install_db_override(client, strategy_row=other)
        build = _install_build_stub(monkeypatch, markers=[])

        resp = client.get("/api/chart/markers", params=_params())
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()
        # Service layer must not have been invoked when authz fails.
        build.assert_not_awaited()

    def test_missing_strategy_returns_403_not_404_no_existence_leak(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _install_db_override(client, strategy_row=None)
        _install_build_stub(monkeypatch, markers=[])

        resp = client.get("/api/chart/markers", params=_params())
        assert resp.status_code == 403

    def test_naive_datetime_returns_400(
        self,
        client: TestClient,
    ) -> None:
        # No tz offset on `from` — must be 400, not 422 (FastAPI parses
        # ISO 8601 without offset as a naive datetime).
        params = _params(**{"from": "2026-05-12T09:15:00"})
        # Need a DB override even though it shouldn't be reached, so
        # FastAPI dependency resolution doesn't trip on the missing
        # session factory.
        strategy = MagicMock()
        strategy.id = _STRATEGY_ID
        strategy.user_id = _USER_ID
        _install_db_override(client, strategy_row=strategy)

        resp = client.get("/api/chart/markers", params=params)
        assert resp.status_code == 400
        assert "timezone" in resp.json()["detail"].lower()

    def test_inverted_window_returns_400(
        self,
        client: TestClient,
    ) -> None:
        params = _params(
            **{
                "from": "2026-05-12T15:30:00+05:30",
                "to": "2026-05-12T09:15:00+05:30",
            }
        )
        strategy = MagicMock()
        strategy.id = _STRATEGY_ID
        strategy.user_id = _USER_ID
        _install_db_override(client, strategy_row=strategy)

        resp = client.get("/api/chart/markers", params=params)
        assert resp.status_code == 400
        assert "from is greater than to" in resp.json()["detail"]

    def test_corrupt_cache_falls_through_to_fresh_build(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Stub cache_get at the route's import site so the route sees
        # garbage on its first call and falls through to a fresh build.
        # Avoids the sync-vs-async event-loop dance of seeding fakeredis
        # from a synchronous test.
        cache_get_stub = AsyncMock(return_value="{not_json")
        monkeypatch.setattr(
            markers_route_mod, "cache_get", cache_get_stub
        )
        # Silence the cache write so we can assert build_stub was called.
        monkeypatch.setattr(
            markers_route_mod, "cache_set", AsyncMock(return_value=None)
        )

        strategy = MagicMock()
        strategy.id = _STRATEGY_ID
        strategy.user_id = _USER_ID
        _install_db_override(client, strategy_row=strategy)
        build = _install_build_stub(monkeypatch, markers=[])

        resp = client.get("/api/chart/markers", params=_params())
        assert resp.status_code == 200
        assert resp.json()["cached"] is False
        build.assert_awaited_once()


class TestMarkersCacheKey:
    def test_key_uses_epoch_seconds_for_tz_invariance(self) -> None:
        sid = _STRATEGY_ID
        ts1 = datetime(2026, 5, 12, 9, 15, tzinfo=UTC)
        # Same instant, different rendering — should hit the same key.
        from datetime import timezone as _tz

        ist = _tz(timedelta(hours=5, minutes=30))
        ts1_ist = datetime(2026, 5, 12, 14, 45, tzinfo=ist)
        assert ts1.timestamp() == ts1_ist.timestamp()

        k1 = _markers_cache_key(sid, "NIFTY", "5m", ts1, ts1)
        k2 = _markers_cache_key(sid, "nifty", "5m", ts1_ist, ts1_ist)
        assert k1 == k2

    def test_key_includes_all_query_dimensions(self) -> None:
        sid = _STRATEGY_ID
        ts = datetime(2026, 5, 12, 9, 15, tzinfo=UTC)
        k = _markers_cache_key(sid, "NIFTY", "5m", ts, ts)
        assert "markers:" in k
        assert str(sid) in k
        assert "NIFTY" in k
        assert "5m" in k
