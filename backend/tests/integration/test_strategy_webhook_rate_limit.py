"""Rate-limit tests for ``POST /api/webhook/strategy/{token}``.

Pins the legacy 60-requests-per-60-seconds fixed-window pattern ported
from :mod:`app.api.webhook`. Asserts:

* 60 requests inside the window all succeed.
* 61st request is rejected with HTTP 429 + the legacy detail string.
* Counters are scoped per ``user_id`` — user A exhausting their bucket
  does not affect user B.
* :func:`redis_client.rate_limit_reset` releases the bucket (proxy for
  the natural window-expiry behaviour).

Tests use ``action="EXIT"`` so the rate-limit path doesn't trigger the
entry executor (which would run the full paper-trade flow per request).
EXIT signals still write a :class:`StrategySignal` row but skip
``BackgroundTasks``, keeping the 60-call sweep sub-second.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core import redis_client
from app.core.security import encrypt_credential, generate_webhook_token
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.models.webhook_token import WebhookToken
from app.db.session import get_session
from app.main import create_app
from app.schemas.broker import BrokerName

HMAC_HEADER = "X-Signature"
HMAC_SECRET = "rate-limit-test-hmac-secret-1234567890"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — mirrors test_strategy_webhook_idempotency.py
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


async def _seed_user_with_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
) -> dict[str, Any]:
    """Create one user + Dhan creds + token + active paper-mode strategy."""
    token_plain = generate_webhook_token()
    token_hash = hashlib.sha256(token_plain.encode("utf-8")).hexdigest()

    async with maker() as s:
        user = User(email=email, password_hash="x", is_active=True)
        s.add(user)
        await s.flush()

        cred = BrokerCredential(
            user_id=user.id,
            broker_name=BrokerName.DHAN,
            client_id_enc=encrypt_credential("DHAN-CID"),
            api_key_enc=encrypt_credential("DHAN-KEY"),
            api_secret_enc=encrypt_credential("DHAN-SECRET"),
            access_token_enc=encrypt_credential("DHAN-TOK"),
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            is_active=True,
        )
        s.add(cred)
        await s.flush()

        webhook = WebhookToken(
            user_id=user.id,
            token_hash=token_hash,
            hmac_secret_enc=encrypt_credential(HMAC_SECRET),
            label=f"rate-limit-test-{email}",
            is_active=True,
        )
        s.add(webhook)
        await s.flush()

        strategy = Strategy(
            user_id=user.id,
            name=f"rate-limit-strategy-{email}",
            webhook_token_id=webhook.id,
            broker_credential_id=cred.id,
            entry_lots=1,
            partial_profit_lots=0,
            trail_lots=0,
            allowed_symbols=["NIFTY", "BANKNIFTY"],
            ai_validation_enabled=False,
            is_active=True,
        )
        s.add(strategy)
        await s.commit()

        return {
            "token_plain": token_plain,
            "user_id": user.id,
            "credential_id": cred.id,
            "webhook_id": webhook.id,
            "strategy_id": strategy.id,
        }


@pytest_asyncio.fixture
async def seed(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    return await _seed_user_with_strategy(
        db_session_maker, email="rate-a@tradetri.com"
    )


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> Iterator[TestClient]:
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    from app.core import config as _config

    _config.get_settings.cache_clear()

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
    monkeypatch.setattr(
        "app.db.session.get_sessionmaker", lambda: db_session_maker
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


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _sign(body: bytes, secret: str = HMAC_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _exit_payload(signal_id: str) -> bytes:
    """EXIT action skips the entry executor — keeps 60-call loop fast."""
    return json.dumps(
        {
            "action": "EXIT",
            "symbol": "NIFTY",
            "quantity": 1,
            "order_type": "market",
            "signal_id": signal_id,
        }
    ).encode("utf-8")


def _post(client: TestClient, token: str, signal_id: str) -> Any:
    body = _exit_payload(signal_id)
    return client.post(
        f"/api/webhook/strategy/{token}",
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestWithinLimit:
    def test_60_requests_in_window_all_accepted(
        self,
        client: TestClient,
        seed: dict[str, Any],
    ) -> None:
        """60 distinct EXIT signals inside one window all return 202."""
        token = seed["token_plain"]
        for i in range(60):
            resp = _post(client, token, signal_id=f"rl-{i:03d}")
            assert resp.status_code == 202, (
                f"call #{i + 1} unexpectedly rejected: {resp.status_code} {resp.text}"
            )


class TestOverLimit:
    def test_61st_request_returns_429(
        self,
        client: TestClient,
        seed: dict[str, Any],
    ) -> None:
        """The 61st call inside the window is rejected with the legacy shape.

        Asserts HTTP 429 and ``{"detail": "Webhook rate limit exceeded."}`` —
        no ``Retry-After`` header (legacy doesn't emit one).
        """
        token = seed["token_plain"]
        for i in range(60):
            resp = _post(client, token, signal_id=f"rl-{i:03d}")
            assert resp.status_code == 202, f"call #{i + 1} should pass"

        over = _post(client, token, signal_id="rl-061")
        assert over.status_code == 429, over.text
        assert over.json() == {"detail": "Webhook rate limit exceeded."}
        # Legacy explicitly omits Retry-After; pin that so a future
        # contributor adding the header has to update the test deliberately.
        assert "retry-after" not in {h.lower() for h in over.headers.keys()}


class TestPerUserBuckets:
    def test_user_a_exhausted_does_not_affect_user_b(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate-limit key is ``webhook:{user_id}`` — buckets are per-user.

        Drops the cap to 2 so the test exhausts user A in three calls
        without iterating 60 times. Pattern mirrors the legacy
        ``TestRateLimit`` fixture in ``tests/test_webhook.py``.
        """
        monkeypatch.setattr("app.api.strategy_webhook.RATE_LIMIT_REQUESTS", 2)

        import asyncio

        seed_b = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker, email="rate-b@tradetri.com"
            )
        )

        # User A: 2 OK, 3rd → 429.
        a_first = _post(client, seed["token_plain"], signal_id="a-1")
        a_second = _post(client, seed["token_plain"], signal_id="a-2")
        a_third = _post(client, seed["token_plain"], signal_id="a-3")
        assert a_first.status_code == 202
        assert a_second.status_code == 202
        assert a_third.status_code == 429, a_third.text

        # User B: fresh bucket — 2 OK.
        b_first = _post(client, seed_b["token_plain"], signal_id="b-1")
        b_second = _post(client, seed_b["token_plain"], signal_id="b-2")
        assert b_first.status_code == 202
        assert b_second.status_code == 202


class TestWindowReset:
    def test_window_reset_releases_bucket(
        self,
        client: TestClient,
        seed: dict[str, Any],
        fake_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A fresh window admits new requests.

        We can't sleep for 60 s in a test, so we drive the cap down to 1
        and then call :func:`redis_client.rate_limit_reset` to mimic the
        natural TTL expiry. Exercises the same code path that fires once
        the Redis key TTL elapses in production.
        """
        monkeypatch.setattr("app.api.strategy_webhook.RATE_LIMIT_REQUESTS", 1)
        token = seed["token_plain"]
        user_id: UUID = seed["user_id"]

        first = _post(client, token, signal_id="w-1")
        assert first.status_code == 202

        second = _post(client, token, signal_id="w-2")
        assert second.status_code == 429

        import asyncio

        asyncio.get_event_loop().run_until_complete(
            redis_client.rate_limit_reset(
                f"webhook:{user_id}", redis_client=fake_redis
            )
        )

        third = _post(client, token, signal_id="w-3")
        assert third.status_code == 202, third.text
