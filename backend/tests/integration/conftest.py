"""Shared fixtures for the strategy-webhook integration tests.

Lives at the ``tests/integration/`` level so pytest auto-discovers it
for every sibling test module — no explicit import needed for fixtures
(``db_session_maker``, ``fake_redis``, ``seed``, ``client``). Module-
level helpers (``_seed_user_with_strategy``, ``_sign``) are imported
directly:

    from tests.integration.conftest import _seed_user_with_strategy

The SQLite engine uses ``StaticPool`` + ``check_same_thread=False`` so
the seeded ``users`` row is visible to the request session — without
this, aiosqlite hands out fresh in-memory DBs per connection and the
seed's User INSERT vanishes (see Tier-1 Task #3 post-mortem).
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from decimal import Decimal
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
from sqlalchemy.pool import StaticPool

from app.core.security import encrypt_credential, generate_webhook_token
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.kill_switch import KillSwitchConfig
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.models.webhook_token import WebhookToken
from app.db.session import get_session
from app.main import create_app
from app.schemas.broker import BrokerName

# ═══════════════════════════════════════════════════════════════════════
# Constants — single source of truth for HMAC test config
# ═══════════════════════════════════════════════════════════════════════

HMAC_HEADER = "X-Signature"
HMAC_SECRET = "integration-shared-hmac-secret-1234567890"


# ═══════════════════════════════════════════════════════════════════════
# Engine / session fixture — StaticPool keeps the in-memory DB shared
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fresh in-memory aiosqlite DB, one shared connection across sessions.

    ``StaticPool`` pins the engine to a single connection so the seed's
    INSERTs and the request handler's SELECTs target the same in-memory
    database. Without this, aiosqlite's default pool can hand out
    independent connections, each backing its own private ``:memory:``
    DB — manifesting as silently-rolled-back User INSERTs.
    ``check_same_thread=False`` lets pytest fixtures (running in the
    test loop) hand the connection to the FastAPI TestClient (running
    in its own loop) without aiosqlite's thread-affinity check tripping.
    """
    # Shared-cache named in-memory DB. ``StaticPool`` alone does NOT
    # fix cross-loop visibility (TestClient runs requests in its own
    # event loop); a named ``file::memory:?cache=shared`` URI plus
    # ``uri=true`` lets the seed's loop and the request handler's loop
    # both attach to the same in-memory database via SQLite's shared
    # cache mechanism. The unique URI per engine instance prevents
    # cross-test bleed when fixtures are function-scoped.
    import uuid as _uuid

    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-test-{_uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fake_aioredis.FakeRedis]:
    """Per-test fake Redis — no persistence, no cross-test leakage."""
    c = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield c
    finally:
        await c.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Seed helper — module-level so callers can build extra users on demand
# ═══════════════════════════════════════════════════════════════════════


async def _seed_user_with_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    email: str = "integration-seed@tradetri.com",
    user_active: bool = True,
    kill_switch_max_trades: int | None = None,
    kill_switch_max_loss_inr: Decimal | None = None,
) -> dict[str, Any]:
    """Create one user + Dhan creds + token + active paper-mode strategy.

    Returns a dict with the freshly-minted IDs and the plaintext webhook
    token. Tests that need a *second* user (per-user-isolation scenarios)
    call this helper directly with a distinct email.

    Pass ``kill_switch_max_trades`` and/or ``kill_switch_max_loss_inr``
    to create a :class:`KillSwitchConfig` row (with ``enabled=True``).
    Without either, no config row is written — :meth:`check_max_daily_trades`
    short-circuits to "no cap" and :meth:`check_and_trigger` is a no-op.
    """
    token_plain = generate_webhook_token()
    token_hash = hashlib.sha256(token_plain.encode("utf-8")).hexdigest()

    async with maker() as s:
        user = User(email=email, password_hash="x", is_active=user_active)
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
            label=f"integration-seed-{email}",
            is_active=True,
        )
        s.add(webhook)
        await s.flush()

        strategy = Strategy(
            user_id=user.id,
            name=f"integration-strategy-{email}",
            webhook_token_id=webhook.id,
            broker_credential_id=cred.id,
            entry_lots=1,
            partial_profit_lots=0,
            trail_lots=0,
            allowed_symbols=["NIFTY", "BANKNIFTY", "BSE1!"],
            ai_validation_enabled=False,
            is_active=True,
        )
        s.add(strategy)

        if (
            kill_switch_max_trades is not None
            or kill_switch_max_loss_inr is not None
        ):
            ks_config = KillSwitchConfig(
                user_id=user.id,
                max_daily_trades=(
                    kill_switch_max_trades
                    if kill_switch_max_trades is not None
                    else 50
                ),
                max_daily_loss_inr=(
                    kill_switch_max_loss_inr
                    if kill_switch_max_loss_inr is not None
                    else Decimal("10000")
                ),
                enabled=True,
                auto_square_off=True,
            )
            s.add(ks_config)

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
    """One-user seed for the common case. Tests needing more users call
    :func:`_seed_user_with_strategy` directly with extra emails."""
    return await _seed_user_with_strategy(db_session_maker)


# ═══════════════════════════════════════════════════════════════════════
# FastAPI client — paper mode forced ON, fake Redis, sqlite session
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> Iterator[TestClient]:
    """TestClient wired against the in-memory DB and fake Redis."""
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
    # Disable the position-manager loop in tests — it would race with
    # the seed for the StaticPool's single connection across event loops
    # (pytest-asyncio's loop vs TestClient's). The strategy executor
    # paths under test don't depend on it firing.
    monkeypatch.setattr(
        "app.workers.position_loop.start_position_loop", lambda _app: None
    )
    monkeypatch.setattr(
        "app.workers.position_loop.stop_position_loop",
        AsyncMock(return_value=None),
    )
    # Same disable for the reconciliation loop — same cross-loop concern.
    # Reconciliation is a no-op in paper mode anyway, but the spawned
    # task would still attach to TestClient's event loop and conflict.
    monkeypatch.setattr(
        "app.workers.reconciliation_loop.start_reconciliation_loop",
        lambda _app: None,
    )
    monkeypatch.setattr(
        "app.workers.reconciliation_loop.stop_reconciliation_loop",
        AsyncMock(return_value=None),
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
# HMAC helper — used by every webhook test
# ═══════════════════════════════════════════════════════════════════════


def _sign(body: bytes, secret: str = HMAC_SECRET) -> str:
    """HMAC-SHA256 hex digest, matching ``app.core.security.verify_hmac_signature``."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
