"""FastAPI app tests — health endpoint, CORS, exception handlers.

The lifespan owns real DB + Redis clients, so here we patch them with
lightweight fakes before constructing :class:`TestClient`. That keeps the
suite fast and offline.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerOrderRejectedError,
    BrokerRateLimitError,
)
from app.main import create_app


class _FakeConn:
    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        return MagicMock()

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None


class _FakeEngine:
    def connect(self) -> _FakeConn:
        return _FakeConn()

    async def dispose(self) -> None:
        return None


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    """Build the app with DB + Redis mocked out — no network, no pool."""
    fake_engine = _FakeEngine()

    async def _fake_dispose() -> None:
        return None

    def _fake_get_engine() -> _FakeEngine:
        return fake_engine  # type: ignore[return-value]

    monkeypatch.setattr("app.db.session.get_engine", _fake_get_engine)
    monkeypatch.setattr("app.db.session.dispose_engine", _fake_dispose)

    fake_redis = MagicMock()
    fake_redis.ping = AsyncMock(return_value=True)
    fake_redis.aclose = AsyncMock(return_value=None)

    def _from_url(*_args: Any, **_kwargs: Any) -> MagicMock:
        return fake_redis

    monkeypatch.setattr("redis.asyncio.from_url", _from_url)

    app = create_app()
    yield app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Starlette :class:`TestClient` runs the full lifespan context."""
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════


class TestHealth:
    def test_returns_ok_when_db_and_redis_up(self, client: TestClient) -> None:
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"status": "ok", "db": True, "redis": True}

    def test_returns_degraded_when_redis_down(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_engine = _FakeEngine()

        async def _noop() -> None:
            return None

        monkeypatch.setattr("app.db.session.get_engine", lambda: fake_engine)
        monkeypatch.setattr("app.db.session.dispose_engine", _noop)

        failing_redis = MagicMock()
        failing_redis.ping = AsyncMock(side_effect=RuntimeError("boom"))
        failing_redis.aclose = AsyncMock(return_value=None)
        monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: failing_redis)

        app = create_app()
        with TestClient(app) as c:
            body = c.get("/health/ready").json()
        assert body["db"] is True
        assert body["redis"] is False
        assert body["status"] == "degraded"


# ═══════════════════════════════════════════════════════════════════════
# CORS
# ═══════════════════════════════════════════════════════════════════════


class TestCORS:
    def test_preflight_headers(self, client: TestClient) -> None:
        resp = client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)
        assert resp.headers["access-control-allow-origin"] in (
            "*", "https://example.com"
        )


# ═══════════════════════════════════════════════════════════════════════
# Routers
# ═══════════════════════════════════════════════════════════════════════


class TestRouters:
    def test_placeholder_prefixes_registered(self, app: FastAPI) -> None:
        openapi = app.openapi()
        # Placeholder routers have no paths yet, but their prefixes must
        # appear in the app's route list so later steps can hang handlers.
        route_paths = {getattr(r, "path", "") for r in app.routes}
        assert "/health" in route_paths
        assert "/openapi.json" in route_paths
        assert openapi["info"]["title"] == "Trading Bridge API"


# ═══════════════════════════════════════════════════════════════════════
# Exception handlers
# ═══════════════════════════════════════════════════════════════════════


class TestExceptionHandlers:
    @pytest.fixture
    def client_with_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Iterator[TestClient]:
        """App that surfaces a broker error on /boom/<kind>."""
        fake_engine = _FakeEngine()

        async def _noop() -> None:
            return None

        monkeypatch.setattr("app.db.session.get_engine", lambda: fake_engine)
        monkeypatch.setattr("app.db.session.dispose_engine", _noop)

        fake_redis = MagicMock()
        fake_redis.ping = AsyncMock(return_value=True)
        fake_redis.aclose = AsyncMock(return_value=None)
        monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

        app = create_app()

        @app.get("/boom/auth")
        async def _auth() -> None:
            raise BrokerAuthError("bad login", broker_name="fyers")

        @app.get("/boom/rejected")
        async def _rejected() -> None:
            raise BrokerOrderRejectedError(
                "rejected", broker_name="fyers", reason="insufficient margin"
            )

        @app.get("/boom/rate")
        async def _rate() -> None:
            raise BrokerRateLimitError(
                "too many", broker_name="fyers", retry_after=5.0
            )

        @app.get("/boom/conn")
        async def _conn() -> None:
            raise BrokerConnectionError("down", broker_name="fyers")

        with TestClient(app) as c:
            yield c

    def test_auth_error_returns_401(self, client_with_errors: TestClient) -> None:
        resp = client_with_errors.get("/boom/auth")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "BrokerAuthError"
        assert body["broker"] == "fyers"

    def test_rejected_error_returns_422_with_reason(
        self, client_with_errors: TestClient
    ) -> None:
        resp = client_with_errors.get("/boom/rejected")
        assert resp.status_code == 422
        body = resp.json()
        assert body["reason"] == "insufficient margin"

    def test_rate_limit_returns_429_with_retry(
        self, client_with_errors: TestClient
    ) -> None:
        resp = client_with_errors.get("/boom/rate")
        assert resp.status_code == 429
        assert resp.json()["retry_after"] == 5.0

    def test_connection_error_returns_502(
        self, client_with_errors: TestClient
    ) -> None:
        resp = client_with_errors.get("/boom/conn")
        assert resp.status_code == 502
