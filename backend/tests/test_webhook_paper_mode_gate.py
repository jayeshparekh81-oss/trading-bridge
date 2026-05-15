"""Paper-mode safety gate tests for the legacy ``/api/webhook/{token}``.

Safety fix #1 (2026-05-15). Two layers of defence:

    1. ``main.py`` skips ``app.include_router(webhook_router)`` whenever
       ``settings.strategy_paper_mode`` is True — the URL simply does
       not exist on a paper-mode deployment.
    2. ``api/webhook.py:receive_webhook`` ALSO raises HTTP 503 in paper
       mode — covers the case where the router is mounted by a test
       harness or a misconfigured deploy.

The first test verifies the in-handler 503 guard (we force-mount the
router so the route is reachable). The second test verifies that the
modern ``POST /api/webhook/strategy/{token}`` continues to accept
requests under paper mode — its full execution path is covered by
``tests/integration/test_strategy_webhook_paper_e2e.py``; this test is
a focused regression guard that the URL itself stays available.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.webhook import router as legacy_webhook_router
from app.core import redis_client
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


HMAC_HEADER = "X-Signature"
HMAC_SECRET = "paper-gate-test-secret-9876543210"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — paper mode forced ON
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fake_aioredis.FakeRedis]:
    c = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture
def paper_mode_client(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> Iterator[TestClient]:
    """Build a TestClient with ``STRATEGY_PAPER_MODE=true``.

    ``main.py`` will NOT auto-mount the legacy webhook router in paper
    mode; we force-mount it afterwards so the in-handler 503 guard is
    reachable. Tests that assert on route-absence use the unforced app
    state and check for HTTP 404 instead.
    """
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    async def _noop_close() -> None:
        return None

    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.core.redis_client.close_redis", _noop_close)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

    class _FakeEngine:
        async def dispose(self) -> None:
            return None

        def connect(self) -> Any:
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def _ctx() -> Any:
                conn = MagicMock()
                conn.execute = AsyncMock(return_value=MagicMock())
                yield conn

            return _ctx()

    monkeypatch.setattr("app.db.session.get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(
        "app.db.session.dispose_engine", AsyncMock(return_value=None)
    )

    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as c:
        yield c


def _payload_body() -> bytes:
    """Minimal valid JSON body — the in-handler guard fires before
    parse, so the schema content doesn't matter for the 503 test."""
    return b'{"action":"BUY","symbol":"NIFTY","exchange":"NSE","quantity":1}'


def _sign(body: bytes) -> str:
    return hmac.new(HMAC_SECRET.encode(), body, hashlib.sha256).hexdigest()


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestLegacyWebhookPaperModeGate:
    def test_legacy_webhook_route_excluded_in_paper_mode(
        self, paper_mode_client: TestClient
    ) -> None:
        """``main.py``'s conditional include leaves the route unregistered
        — FastAPI returns 404 for unknown paths."""
        body = _payload_body()
        resp = paper_mode_client.post(
            "/api/webhook/sometoken1234567890abcdef",
            content=body,
            headers={HMAC_HEADER: _sign(body)},
        )
        assert resp.status_code == 404, resp.text

    def test_legacy_webhook_503_in_paper_mode(
        self, paper_mode_client: TestClient
    ) -> None:
        """If the legacy router is mounted (e.g. for testing or a
        misconfigured deploy), the in-handler guard rejects with 503.

        Note: ``SensitiveDataFilterMiddleware`` scrubs the body of every
        5xx to ``{"detail": "internal error", ...}`` in production, so
        we assert on status code only — the Hinglish detail lives in
        logs and the source, not in the HTTP response body.
        """
        # Force-mount the legacy router on the running test app so the
        # route is reachable; the in-handler guard must still fire.
        paper_mode_client.app.include_router(legacy_webhook_router)
        body = _payload_body()
        resp = paper_mode_client.post(
            "/api/webhook/sometoken1234567890abcdef",
            content=body,
            headers={HMAC_HEADER: _sign(body)},
        )
        assert resp.status_code == 503, resp.text

    def test_strategy_webhook_still_works_in_paper_mode(
        self, paper_mode_client: TestClient
    ) -> None:
        """The modern strategy webhook URL must remain available in
        paper mode — only the legacy ``/api/webhook/{token}`` path is
        gated. Asserts the route exists and is NOT serving 503 from the
        legacy gate; a 4xx from auth/token resolution is the expected
        shape on an unsigned random token (full e2e coverage lives in
        ``tests/integration/test_strategy_webhook_paper_e2e.py``)."""
        body = _payload_body()
        resp = paper_mode_client.post(
            "/api/webhook/strategy/sometoken1234567890abcdef",
            content=body,
            headers={HMAC_HEADER: _sign(body)},
        )
        # Must not 404 (route exists) and must not 503 (paper gate is
        # legacy-only). The real outcome depends on token resolution
        # (404 unknown-token, 401 HMAC, etc.) but never the legacy gate.
        assert resp.status_code != 503, (
            f"strategy webhook unexpectedly returned 503: {resp.text}"
        )
        # Route is registered — anything other than FastAPI's "Not Found"
        # confirms the strategy URL prefix is live.
        if resp.status_code == 404:
            assert "Not Found" not in resp.text or "token" in resp.text.lower(), (
                f"strategy webhook route missing under paper mode: {resp.text}"
            )
