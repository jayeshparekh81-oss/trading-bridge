"""Tests for :mod:`app.middleware.security`.

Each middleware is wired into a bare FastAPI app so we can assert on
headers/status without the full ``create_app`` lifespan overhead.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from app.middleware.security import (
    RequestIDMiddleware,
    RequestSizeLimitMiddleware,
    ResponseTimingMiddleware,
    SecurityHeadersMiddleware,
    SensitiveDataFilterMiddleware,
    TrustedProxyMiddleware,
)


# ═══════════════════════════════════════════════════════════════════════
# Security headers
# ═══════════════════════════════════════════════════════════════════════


def _app_with(middleware_cls, **kwargs) -> FastAPI:
    app = FastAPI()
    app.add_middleware(middleware_cls, **kwargs)

    @app.get("/p")
    async def _p() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/boom")
    async def _boom() -> JSONResponse:
        return JSONResponse(status_code=500, content={"secret": "leak"})

    @app.get("/html")
    async def _html() -> PlainTextResponse:
        return PlainTextResponse("<h1>hi</h1>")

    return app


class TestSecurityHeaders:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(_app_with(SecurityHeadersMiddleware))

    def test_all_headers_present(self, client: TestClient) -> None:
        headers = client.get("/p").headers
        for key in (
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
            "X-Permitted-Cross-Domain-Policies",
            "Cache-Control",
            "Pragma",
        ):
            assert key in headers, f"missing {key}"

    def test_csp_relaxed_for_docs(self) -> None:
        app = _app_with(SecurityHeadersMiddleware)

        @app.get("/docs")
        async def _docs() -> PlainTextResponse:
            return PlainTextResponse("<html>docs</html>")

        with TestClient(app) as c:
            resp = c.get("/docs")
        assert "Content-Security-Policy" not in resp.headers

    def test_extra_headers(self) -> None:
        app = _app_with(SecurityHeadersMiddleware, extra={"X-Custom": "yes"})
        with TestClient(app) as c:
            assert c.get("/p").headers["X-Custom"] == "yes"


# ═══════════════════════════════════════════════════════════════════════
# Request ID
# ═══════════════════════════════════════════════════════════════════════


class TestRequestID:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(_app_with(RequestIDMiddleware))

    def test_generates_unique_ids(self, client: TestClient) -> None:
        a = client.get("/p").headers["X-Request-ID"]
        b = client.get("/p").headers["X-Request-ID"]
        assert a != b
        assert len(a) >= 16

    def test_honours_upstream_id(self, client: TestClient) -> None:
        resp = client.get("/p", headers={"X-Request-ID": "trace-abc12345"})
        assert resp.headers["X-Request-ID"] == "trace-abc12345"

    def test_rejects_bogus_upstream_id(self, client: TestClient) -> None:
        resp = client.get("/p", headers={"X-Request-ID": "x"})
        assert resp.headers["X-Request-ID"] != "x"


# ═══════════════════════════════════════════════════════════════════════
# Response timing
# ═══════════════════════════════════════════════════════════════════════


class TestResponseTiming:
    def test_header_present_and_positive(self) -> None:
        client = TestClient(_app_with(ResponseTimingMiddleware))
        resp = client.get("/p")
        val = float(resp.headers["X-Process-Time"])
        assert val >= 0


# ═══════════════════════════════════════════════════════════════════════
# Trusted proxy
# ═══════════════════════════════════════════════════════════════════════


class TestTrustedProxy:
    """TestClient sets ``request.client.host = "testclient"`` which is not a
    real IP, so we override via a tiny sub-app that rewrites the scope."""

    def _client(self, trusted: list[str], peer_ip: str = "127.0.0.1") -> TestClient:
        app = FastAPI()
        app.add_middleware(TrustedProxyMiddleware, trusted_proxies=trusted)

        @app.middleware("http")
        async def _spoof_peer(request: Request, call_next):  # type: ignore[no-untyped-def]
            # Starlette exposes the peer via ``request.scope["client"]`` — rewrite
            # it to a real IP so the trusted-proxy CIDR match behaves.
            request.scope["client"] = (peer_ip, 0)
            return await call_next(request)

        @app.get("/whoami")
        async def _w(request: Request) -> dict[str, str | None]:
            return {"ip": getattr(request.state, "client_ip", None)}

        return TestClient(app)

    def test_trusted_peer_honours_forwarded(self) -> None:
        with self._client(trusted=["127.0.0.0/8"]) as c:
            resp = c.get("/whoami", headers={"X-Forwarded-For": "8.8.8.8"})
        assert resp.json()["ip"] == "8.8.8.8"

    def test_untrusted_peer_uses_peer_ip(self) -> None:
        with self._client(trusted=["10.0.0.0/8"]) as c:
            resp = c.get("/whoami", headers={"X-Forwarded-For": "8.8.8.8"})
        assert resp.json()["ip"] == "127.0.0.1"

    def test_bad_trusted_cidr_is_logged_not_crashed(self) -> None:
        with self._client(trusted=["not-a-cidr"]) as c:
            resp = c.get("/whoami")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# Request size limit
# ═══════════════════════════════════════════════════════════════════════


class TestRequestSizeLimit:
    def test_rejects_oversize(self) -> None:
        app = FastAPI()
        app.add_middleware(RequestSizeLimitMiddleware, max_bytes=100)

        @app.post("/p")
        async def _p() -> dict[str, str]:
            return {"ok": "true"}

        body = "a" * 500
        with TestClient(app) as c:
            resp = c.post("/p", content=body, headers={"Content-Type": "text/plain"})
        assert resp.status_code == 413

    def test_allows_small_body(self) -> None:
        app = FastAPI()
        app.add_middleware(RequestSizeLimitMiddleware, max_bytes=100)

        @app.post("/p")
        async def _p() -> dict[str, str]:
            return {"ok": "true"}

        with TestClient(app) as c:
            resp = c.post("/p", content="x", headers={"Content-Type": "text/plain"})
        assert resp.status_code == 200

    def test_invalid_content_length(self) -> None:
        app = FastAPI()
        app.add_middleware(RequestSizeLimitMiddleware, max_bytes=100)

        @app.post("/p")
        async def _p() -> dict[str, str]:
            return {"ok": "true"}

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/p",
                content="abc",
                headers={"Content-Length": "not-int", "Content-Type": "text/plain"},
            )
        # Starlette may rebuild Content-Length; either 400 or 200 depending on rewrite.
        assert resp.status_code in (200, 400)


# ═══════════════════════════════════════════════════════════════════════
# Sensitive-data filter
# ═══════════════════════════════════════════════════════════════════════


class TestSensitiveFilter:
    def test_scrubs_5xx_body(self) -> None:
        client = TestClient(_app_with(SensitiveDataFilterMiddleware))
        resp = client.get("/boom")
        body = resp.json()
        assert body == {"detail": "internal error", "request_id": None}

    def test_passes_2xx_unchanged(self) -> None:
        client = TestClient(_app_with(SensitiveDataFilterMiddleware))
        resp = client.get("/p")
        assert resp.json() == {"ok": "true"}


# ═══════════════════════════════════════════════════════════════════════
# Stack composition via create_app
# ═══════════════════════════════════════════════════════════════════════


class TestStack:
    @pytest.fixture
    def app_client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        from unittest.mock import AsyncMock, MagicMock

        class _Conn:
            async def execute(self, *a, **kw):
                return MagicMock()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

        class _Engine:
            def connect(self):
                return _Conn()

            async def dispose(self):
                return None

        monkeypatch.setattr("app.db.session.get_engine", lambda: _Engine())
        monkeypatch.setattr("app.db.session.dispose_engine", AsyncMock(return_value=None))
        fake_redis = MagicMock()
        fake_redis.ping = AsyncMock(return_value=True)
        fake_redis.aclose = AsyncMock(return_value=None)
        monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

        from app.main import create_app

        return TestClient(create_app())

    def test_health_has_all_headers(self, app_client: TestClient) -> None:
        with app_client as c:
            resp = c.get("/health")
        assert "X-Request-ID" in resp.headers
        assert "X-Process-Time" in resp.headers
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
