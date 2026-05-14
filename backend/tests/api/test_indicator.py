"""Tests for :mod:`app.api.indicator` — POST /api/chart/indicator."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user
from app.api.indicator import router as indicator_router
from app.core import redis_client
from app.db.session import get_session
from app.services import indicator_candles
from app.services.indicators import REGISTRY
from app.services import indicator_service
from tests.services.indicators.conftest import synthesise_candles


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def _fake_redis(monkeypatch: pytest.MonkeyPatch):
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    u.is_active = True
    return u


@pytest.fixture
def indicator_app(
    fake_user: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    app = FastAPI()
    app.include_router(indicator_router)
    app.dependency_overrides[get_current_active_user] = lambda: fake_user

    async def _fake_session() -> Any:
        yield AsyncMock()

    app.dependency_overrides[get_session] = _fake_session
    return app


@pytest.fixture
def client(indicator_app: FastAPI) -> TestClient:
    return TestClient(indicator_app)


def _patch_candles(
    monkeypatch: pytest.MonkeyPatch, *, candles: list[Any]
) -> None:
    """Replace the candle fetcher with a stub returning ``candles``."""

    async def _fetch(**_kw: Any) -> list[Any]:
        return list(candles)

    monkeypatch.setattr(indicator_service, "fetch_closed_candles", _fetch)


def _payload(
    *,
    indicator: str = "sma",
    params: dict[str, Any] | None = None,
    symbol: str = "NIFTY",
    exchange: str = "NSE",
    timeframe: str = "5m",
    from_offset_minutes: int = 0,
    to_offset_minutes: int = 60 * 17,
) -> dict[str, Any]:
    """Build a valid request body."""
    base = datetime(2026, 5, 11, 3, 45, tzinfo=UTC)
    inner_params = {"indicator": indicator, **(params or {"length": 20})}
    return {
        "symbol": symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "params": inner_params,
        "from_ts": base.isoformat(),
        "to_ts": (base + timedelta(minutes=to_offset_minutes)).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════
# Happy paths
# ═══════════════════════════════════════════════════════════════════════


class TestPostIndicator:
    def test_sma_happy_path(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        candles = synthesise_candles(n=200)
        _patch_candles(monkeypatch, candles=candles)
        resp = client.post("/api/chart/indicator", json=_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["indicator"] == "sma"
        assert body["cached"] is False
        assert len(body["candle_timestamps"]) == 200
        assert len(body["series"]["value"]) == 200
        # Warmup positions are JSON null.
        assert body["series"]["value"][0] is None
        # Post-warmup positions are finite floats.
        assert isinstance(body["series"]["value"][-1], float)

    def test_macd_three_series(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candles = synthesise_candles(n=200)
        _patch_candles(monkeypatch, candles=candles)
        resp = client.post(
            "/api/chart/indicator",
            json=_payload(
                indicator="macd",
                params={
                    "fast_length": 12,
                    "slow_length": 26,
                    "signal_length": 9,
                },
            ),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["series"]) == {"macd", "signal", "histogram"}

    def test_bb_three_bands(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candles = synthesise_candles(n=200)
        _patch_candles(monkeypatch, candles=candles)
        resp = client.post(
            "/api/chart/indicator",
            json=_payload(
                indicator="bb",
                params={"length": 20, "stddev_multiplier": 2.0},
            ),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["series"]) == {"upper", "middle", "lower"}

    def test_cache_hit_on_second_call(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candles = synthesise_candles(n=200)
        _patch_candles(monkeypatch, candles=candles)
        first = client.post("/api/chart/indicator", json=_payload())
        second = client.post("/api/chart/indicator", json=_payload())
        assert first.json()["cached"] is False
        assert second.json()["cached"] is True

    def test_empty_candle_window_returns_200_with_empty_series(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_candles(monkeypatch, candles=[])
        resp = client.post("/api/chart/indicator", json=_payload())
        assert resp.status_code == 200
        body = resp.json()
        # NaN policy: empty window is 200, NOT 400.
        assert body["candle_timestamps"] == []
        assert body["series"] == {"value": []}
        assert body["last_closed_candle_ts"] is None


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════


class TestRequestValidation:
    def test_naive_from_ts_rejected(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_candles(monkeypatch, candles=[])
        body = _payload()
        # Strip the tz suffix to make the datetime naive.
        body["from_ts"] = "2026-05-11T09:15:00"
        resp = client.post("/api/chart/indicator", json=body)
        assert resp.status_code == 422  # Pydantic body validation

    def test_reversed_window_rejected(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_candles(monkeypatch, candles=[])
        body = _payload(to_offset_minutes=-60)
        resp = client.post("/api/chart/indicator", json=body)
        assert resp.status_code == 422

    def test_macd_fast_ge_slow_rejected(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/chart/indicator",
            json=_payload(
                indicator="macd",
                params={
                    "fast_length": 50,
                    "slow_length": 26,
                    "signal_length": 9,
                },
            ),
        )
        assert resp.status_code == 422

    def test_length_zero_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/chart/indicator",
            json=_payload(params={"length": 0}),
        )
        assert resp.status_code == 422

    def test_unknown_indicator_rejected(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/chart/indicator",
            json=_payload(indicator="vwap", params={"length": 20}),
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Auth-stack error propagation
# ═══════════════════════════════════════════════════════════════════════


class TestErrorPropagation:
    def test_412_no_dhan_link(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the fetcher raises HTTPException 412, route propagates it."""
        from fastapi import HTTPException

        async def _f(**_kw: Any) -> Any:
            raise HTTPException(
                status_code=412, detail="Dhan broker link nahi mila"
            )

        monkeypatch.setattr(indicator_service, "fetch_closed_candles", _f)
        resp = client.post("/api/chart/indicator", json=_payload())
        assert resp.status_code == 412
        assert "Dhan broker link" in resp.json()["detail"]

    def test_429_rate_limited(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import HTTPException

        async def _f(**_kw: Any) -> Any:
            raise HTTPException(
                status_code=429, detail="local rate cap"
            )

        monkeypatch.setattr(indicator_service, "fetch_closed_candles", _f)
        resp = client.post("/api/chart/indicator", json=_payload())
        assert resp.status_code == 429

    def test_502_upstream(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import HTTPException

        async def _f(**_kw: Any) -> Any:
            raise HTTPException(status_code=502, detail="dhan 5xx")

        monkeypatch.setattr(indicator_service, "fetch_closed_candles", _f)
        resp = client.post("/api/chart/indicator", json=_payload())
        assert resp.status_code == 502
