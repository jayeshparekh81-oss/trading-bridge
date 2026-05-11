"""Fixtures for api/ tests (chart route + WS endpoint).

The chart API depends on a tall stack of integrations:

    * Postgres-backed User + BrokerCredential models (we mock the
      session entirely — no DB in unit tests).
    * Redis cache + pub/sub (fakeredis).
    * DhanBroker for security_id resolution (mocked).
    * DhanHistoricalClient (mocked at call site).
    * JWT session-token validation (real, since the function itself
      is pure crypto + a Redis blacklist check that fakeredis covers).

These fixtures provide the mocks + a FastAPI ``TestClient`` mounting
just the chart router. Tests can override the auth dependency to
inject a synthetic ``User`` without going through password flow.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chart import router as chart_router
from app.api.deps import get_current_active_user
from app.core import redis_client
from app.db.session import get_session


@pytest_asyncio.fixture(autouse=True)
async def fake_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    """Process-wide async Redis substituted for fakeredis."""
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def fake_user() -> MagicMock:
    """Minimal stand-in for :class:`app.db.models.user.User`.

    The chart route only reads ``user.id`` and (via the active-user
    dependency) ``user.is_active``; a MagicMock with those attributes
    is enough.
    """
    user = MagicMock()
    user.id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    user.is_active = True
    user.is_admin = False
    return user


@pytest.fixture
def fake_creds_row() -> MagicMock:
    """Encrypted-columns row returned by the BrokerCredential select.

    The chart route runs each column through ``decrypt_credential``,
    so the values here are the **encrypted** ciphertext placeholders
    that our patched ``decrypt_credential`` (in test_chart.py) will
    short-circuit.
    """
    row = MagicMock()
    row.client_id_enc = b"enc_client_id"
    row.api_key_enc = b"enc_api_key"
    row.api_secret_enc = b"enc_api_secret"
    row.access_token_enc = b"enc_access_token"
    row.refresh_token_enc = b"enc_refresh_token"
    row.token_expires_at = datetime(2026, 12, 31, tzinfo=UTC)
    return row


def _fake_db_session_factory(rows: dict[Any, Any]) -> Any:
    """Construct an AsyncMock that returns ``rows`` for any ``.execute``.

    Helper used by test_chart.py to script the
    ``select(BrokerCredential)`` lookup without a real DB.
    """
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(side_effect=lambda: rows.get("row"))
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture
def db_session_factory():
    """Expose the factory helper for inline use in test cases."""
    return _fake_db_session_factory


@pytest.fixture
def chart_app(fake_user: MagicMock) -> FastAPI:
    """FastAPI instance with just the chart router mounted + auth shim.

    The auth dependency override returns ``fake_user`` unconditionally,
    so tests don't have to mint JWTs for the REST endpoints. The WS
    endpoint goes through the real ``validate_session_token`` path
    (auth is in the body, not in a FastAPI dependency).
    """
    app = FastAPI()
    app.include_router(chart_router)
    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    return app


@pytest.fixture
def client(chart_app: FastAPI) -> TestClient:
    """Sync FastAPI TestClient — supports both REST and WebSocket calls."""
    return TestClient(chart_app)
