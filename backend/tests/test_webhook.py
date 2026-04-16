"""End-to-end tests for the webhook endpoint.

Exercises the full pipeline through a FastAPI ``TestClient`` with:

* in-memory aiosqlite DB wired into the request-scoped session dependency,
* fake Redis (``fakeredis.aioredis``) behind both the module singleton and
  the lifespan's ``app.state.redis``,
* a fake broker that records the normalized order the service hands it.

The point is to cover the Kill-Switch pipeline from the blueprint: rate
limit → HMAC verify → idempotency → kill switch → user gate → dispatch.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi import FastAPI
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
from app.schemas.broker import (
    BrokerName,
    OrderResponse,
    OrderStatus,
)


HMAC_HEADER = "X-Signature"
HMAC_SECRET = "test-hmac-secret-value-1234567890"


# ═══════════════════════════════════════════════════════════════════════
# Fake broker (installed in the registry for the duration of the test)
# ═══════════════════════════════════════════════════════════════════════


class _FakeBroker:
    broker_name = BrokerName.FYERS

    def __init__(self, credentials: Any) -> None:  # noqa: D401 — shape mirrors real broker
        self._creds = credentials
        self.orders: list[Any] = []

    async def login(self) -> bool:
        return True

    async def is_session_valid(self) -> bool:
        return True

    async def place_order(self, order: Any) -> OrderResponse:
        self.orders.append(order)
        return OrderResponse(
            broker_order_id="FAKE-1",
            status=OrderStatus.PENDING,
            message="ok",
        )

    async def get_positions(self) -> list[Any]:
        return []

    def normalize_symbol(self, symbol: str, exchange: Any) -> str:
        return f"{exchange.value}:{symbol}-EQ"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
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
async def seed(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Create a user + active credential + webhook token + strategy binding."""
    token_plain = generate_webhook_token()
    token_hash = hashlib.sha256(token_plain.encode()).hexdigest()

    async with db_session_maker() as s:
        user = User(
            email="trader@example.com",
            password_hash="x",
            is_active=True,
        )
        s.add(user)
        await s.flush()

        creds = BrokerCredential(
            user_id=user.id,
            broker_name=BrokerName.FYERS,
            client_id_enc=encrypt_credential("CID"),
            api_key_enc=encrypt_credential("KEY"),
            api_secret_enc=encrypt_credential("SECRET"),
            access_token_enc=encrypt_credential("TOK"),
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            is_active=True,
        )
        s.add(creds)
        await s.flush()

        webhook = WebhookToken(
            user_id=user.id,
            token_hash=token_hash,
            hmac_secret_enc=encrypt_credential(HMAC_SECRET),
            label="default",
            is_active=True,
        )
        s.add(webhook)
        await s.flush()

        strategy = Strategy(
            user_id=user.id,
            name="demo",
            webhook_token_id=webhook.id,
            broker_credential_id=creds.id,
            is_active=True,
        )
        s.add(strategy)
        await s.commit()

        return {
            "token_plain": token_plain,
            "user_id": user.id,
            "credential_id": creds.id,
            "webhook_id": webhook.id,
        }


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fake_aioredis.FakeRedis]:
    c = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> Iterator[TestClient]:
    """Wire the app: fake Redis, fake DB engine, fake session dep, fake broker."""

    # ── Redis: singleton + lifespan path ──────────────────────────────
    async def _noop_close() -> None:
        return None

    monkeypatch.setattr(
        "app.core.redis_client.get_redis", lambda: fake_redis
    )
    monkeypatch.setattr(
        "app.core.redis_client.close_redis", _noop_close
    )
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

    # ── DB engine: stub lifespan, override per-request session ────────
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

    # ── Broker registry: swap Fyers for the fake ──────────────────────
    from app.brokers.registry import BROKER_REGISTRY

    monkeypatch.setitem(BROKER_REGISTRY, BrokerName.FYERS, _FakeBroker)

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


def _sign(body: bytes, secret: str = HMAC_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _payload_json(**overrides: Any) -> bytes:
    base: dict[str, Any] = {
        "action": "BUY",
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "quantity": 10,
        "order_type": "market",
        "product_type": "intraday",
    }
    base.update(overrides)
    return json.dumps(base).encode("utf-8")


def _url(token: str) -> str:
    return f"/api/webhook/{token}"


# ═══════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════


class TestHappyPath:
    def test_buy_returns_success_with_latency(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "success"
        assert data["order_id"] == "FAKE-1"
        assert isinstance(data["latency_ms"], int)
        assert data["latency_ms"] >= 0


# ═══════════════════════════════════════════════════════════════════════
# HMAC + signature
# ═══════════════════════════════════════════════════════════════════════


class TestHmac:
    def test_bad_signature_rejected_401(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: "deadbeef", "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_missing_signature_rejected_401(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# Token + user gates
# ═══════════════════════════════════════════════════════════════════════


class TestTokenAndUser:
    def test_unknown_token_returns_404(self, client: TestClient) -> None:
        bogus = generate_webhook_token()
        body = _payload_json()
        resp = client.post(
            _url(bogus),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 404

    def test_inactive_user_returns_403(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        # Deactivate the user then retry.
        import asyncio

        from sqlalchemy import update

        async def _deactivate() -> None:
            async with db_session_maker() as s:
                await s.execute(
                    update(User)
                    .where(User.id == seed["user_id"])
                    .values(is_active=False)
                )
                await s.commit()

        asyncio.get_event_loop().run_until_complete(_deactivate())

        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Payload validation
# ═══════════════════════════════════════════════════════════════════════


class TestPayload:
    def test_invalid_payload_returns_422(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = b'{"action": "BUY"}'  # missing symbol/quantity
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_missing_quantity_returns_422(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = json.dumps(
            {"action": "BUY", "symbol": "X"}
        ).encode()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Idempotency
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotency:
    def test_duplicate_returns_duplicate_status(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload_json(signal_id="abc-123")
        headers = {HMAC_HEADER: _sign(body), "Content-Type": "application/json"}
        first = client.post(_url(seed["token_plain"]), content=body, headers=headers)
        second = client.post(_url(seed["token_plain"]), content=body, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["status"] == "duplicate"

    def test_different_signal_id_not_duplicate(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body1 = _payload_json(signal_id="one")
        body2 = _payload_json(signal_id="two")
        r1 = client.post(
            _url(seed["token_plain"]),
            content=body1,
            headers={HMAC_HEADER: _sign(body1), "Content-Type": "application/json"},
        )
        r2 = client.post(
            _url(seed["token_plain"]),
            content=body2,
            headers={HMAC_HEADER: _sign(body2), "Content-Type": "application/json"},
        )
        assert r1.json()["status"] == "success"
        assert r2.json()["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════
# Kill switch
# ═══════════════════════════════════════════════════════════════════════


class TestKillSwitch:
    def test_tripped_returns_403(
        self,
        client: TestClient,
        seed: dict[str, Any],
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        import asyncio

        async def _trip() -> None:
            await redis_client.set_kill_switch_status(
                seed["user_id"],
                redis_client.KILL_SWITCH_TRIPPED,
                redis_client=fake_redis,
            )

        asyncio.get_event_loop().run_until_complete(_trip())

        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Rate limit
# ═══════════════════════════════════════════════════════════════════════


class TestRateLimit:
    def test_429_when_limit_exceeded(
        self,
        client: TestClient,
        seed: dict[str, Any],
        fake_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Collapse the limit to 1 so we can trip it in one extra call.
        monkeypatch.setattr("app.api.webhook.RATE_LIMIT_REQUESTS", 1)

        # First use unique signal_id so idempotency doesn't short-circuit.
        body1 = _payload_json(signal_id="r1")
        body2 = _payload_json(signal_id="r2")
        r1 = client.post(
            _url(seed["token_plain"]),
            content=body1,
            headers={HMAC_HEADER: _sign(body1), "Content-Type": "application/json"},
        )
        r2 = client.post(
            _url(seed["token_plain"]),
            content=body2,
            headers={HMAC_HEADER: _sign(body2), "Content-Type": "application/json"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 429


# ═══════════════════════════════════════════════════════════════════════
# Broker errors
# ═══════════════════════════════════════════════════════════════════════


class TestBrokerErrors:
    def test_rejected_order_returns_422(
        self,
        client: TestClient,
        seed: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.brokers.registry import BROKER_REGISTRY
        from app.core.exceptions import BrokerOrderRejectedError

        class _RejectingBroker(_FakeBroker):
            async def place_order(self, order: Any) -> OrderResponse:
                raise BrokerOrderRejectedError(
                    "nope",
                    broker_name="fyers",
                    reason="insufficient margin",
                )

        monkeypatch.setitem(BROKER_REGISTRY, BrokerName.FYERS, _RejectingBroker)

        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 422
        assert resp.json()["reason"] == "insufficient margin"

    def test_connection_error_returns_502(
        self,
        client: TestClient,
        seed: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.brokers.registry import BROKER_REGISTRY
        from app.core.exceptions import BrokerConnectionError

        class _DownBroker(_FakeBroker):
            async def place_order(self, order: Any) -> OrderResponse:
                raise BrokerConnectionError("down", broker_name="fyers")

        monkeypatch.setitem(BROKER_REGISTRY, BrokerName.FYERS, _DownBroker)

        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        assert resp.status_code == 502


# ═══════════════════════════════════════════════════════════════════════
# Latency reported
# ═══════════════════════════════════════════════════════════════════════


class TestLatency:
    def test_latency_ms_in_response(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload_json()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
        )
        body_json = resp.json()
        assert "latency_ms" in body_json
        assert body_json["latency_ms"] >= 0
