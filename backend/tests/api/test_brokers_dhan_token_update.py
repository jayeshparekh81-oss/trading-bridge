"""End-to-end tests for the Dhan paste-token update endpoints.

Covers ``POST /api/brokers/dhan/update-token`` and
``GET /api/brokers/dhan/status`` added in Phase 1 (2026-05-16) of the
broker-reconnect UX work.

The tests:

* Use a real in-memory SQLite engine so the atomic
  ``relink_strategies_to_new_credential`` path is exercised end-to-end
  (matches the pattern in ``tests/test_kill_switch_api.py``).
* Monkeypatch ``app.api.brokers._httpx.AsyncClient`` to fake the Dhan
  probe — no real network. The fake responds with whatever status code
  each test configures so we can pin both the happy path and every
  documented error branch.
* Substitute ``app.core.redis_client.get_redis`` with fakeredis so the
  cache-bust path exercises the real ``cache_delete`` helper.
* Override ``get_current_active_user`` via FastAPI
  ``dependency_overrides`` so we don't need a real JWT — same pattern
  used by ``tests/api/test_chart_markers.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api import brokers as brokers_module
from app.api.brokers import router as brokers_router
from app.api.deps import get_current_active_user
from app.core import redis_client, security
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.broker import BrokerName


# ═══════════════════════════════════════════════════════════════════════
# Encryption key — set once per process so encrypt/decrypt round-trip.
# Mirrors tests/test_users_api.py:_reset_cipher.
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


# ═══════════════════════════════════════════════════════════════════════
# DB — real SQLite in-memory engine + a per-test sessionmaker.
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def _sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_user(
    _sessionmaker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Active user with no broker credentials yet."""
    async with _sessionmaker() as s:
        u = User(email="dhan-test@example.com", password_hash="p", is_active=True)
        s.add(u)
        await s.commit()
        return {"user_id": str(u.id)}


# ═══════════════════════════════════════════════════════════════════════
# Fake httpx.AsyncClient for the Dhan probe.
# ═══════════════════════════════════════════════════════════════════════


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHttpxAsyncClient:
    """Drop-in replacement for ``httpx.AsyncClient`` used in tests.

    Records the access-token header and probe path on every call so
    tests can assert what was sent. Each test supplies the desired
    response (or an exception) via ``configure(...)``.
    """

    calls: list[dict[str, Any]] = []
    next_response: _FakeResponse | Exception = _FakeResponse(200)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._headers = kwargs.get("headers", {})
        self._base_url = kwargs.get("base_url", "")

    async def __aenter__(self) -> "_FakeHttpxAsyncClient":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def get(self, path: str) -> _FakeResponse:
        type(self).calls.append(
            {
                "path": path,
                "headers": dict(self._headers),
                "base_url": self._base_url,
            }
        )
        nxt = type(self).next_response
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    @classmethod
    def configure(
        cls, response: _FakeResponse | Exception = _FakeResponse(200)
    ) -> None:
        cls.calls = []
        cls.next_response = response


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[_FakeHttpxAsyncClient]]:
    """Monkeypatch ``_httpx.AsyncClient`` at the brokers import site.

    Default: respond 200 (token valid). Individual tests override via
    ``_FakeHttpxAsyncClient.configure(...)``.
    """
    _FakeHttpxAsyncClient.configure(_FakeResponse(200))
    monkeypatch.setattr(
        brokers_module._httpx, "AsyncClient", _FakeHttpxAsyncClient
    )
    yield _FakeHttpxAsyncClient


# ═══════════════════════════════════════════════════════════════════════
# Redis — the conftest.py in tests/api/ provides an autouse ``fake_redis``
# fixture that monkeypatches ``redis_client.get_redis`` for every test.
# Tests that need to read or seed keys take ``fake_redis`` as a
# parameter to receive the same instance.
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# App + TestClient — REAL get_current_active_user when no override (for
# the auth-gate test) and a fake-user override otherwise.
# ═══════════════════════════════════════════════════════════════════════


def _build_app(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> FastAPI:
    """A bare FastAPI with just the brokers router + DB override.

    NO auth override here — tests that want unauthenticated behaviour
    use this directly; happy-path tests layer ``dependency_overrides[
    get_current_active_user]`` on top.
    """
    app = FastAPI()
    app.include_router(brokers_router)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override_session
    return app


def _fake_user(user_id: str) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = UUID(user_id)
    user.is_active = True
    return user


@pytest.fixture
def client_unauth(
    _sessionmaker: async_sessionmaker[AsyncSession],
) -> TestClient:
    """TestClient WITHOUT auth override — for the 401 gate test.

    (``fake_redis`` is autouse in tests/api/conftest.py, so the redis
    monkeypatch is in place before any of these tests run.)
    """
    app = _build_app(_sessionmaker)
    return TestClient(app)


@pytest.fixture
def client_as_user(
    _sessionmaker: async_sessionmaker[AsyncSession],
    seeded_user: dict[str, Any],
) -> TestClient:
    """TestClient + auth override returning seeded user."""
    app = _build_app(_sessionmaker)
    app.dependency_overrides[get_current_active_user] = lambda: _fake_user(
        seeded_user["user_id"]
    )
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# Constants used across tests
# ═══════════════════════════════════════════════════════════════════════


_VALID_TOKEN = "x" * 250  # Dhan tokens are JWTs ~300+ chars; 250 satisfies min_length=100.
_CLIENT_ID = "1100123456"


# ═══════════════════════════════════════════════════════════════════════
# POST /api/brokers/dhan/update-token
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateDhanToken:
    def test_update_dhan_token_requires_auth_401(
        self, client_unauth: TestClient
    ) -> None:
        """Unauthenticated request must be rejected before any DB or
        Dhan-API access."""
        resp = client_unauth.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert resp.status_code == 401, resp.text

    def test_update_dhan_token_valid_token_saves_encrypted_to_db(
        self,
        client_as_user: TestClient,
        seeded_user: dict[str, Any],
        _sessionmaker: async_sessionmaker[AsyncSession],
        _patch_httpx: type[_FakeHttpxAsyncClient],
    ) -> None:
        """Happy path: token validates with Dhan → encrypted row
        persists → response carries success contract."""
        _patch_httpx.configure(_FakeResponse(200, {"availableBalance": 12345}))

        resp = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["connection_status"] == "active"
        assert "Chart and trading are now live" in body["message"]
        assert body["token_label"] == "Dhan – Primary"
        assert "updated_at" in body

        # Probe must have been called against /fundlimit with the token
        # in the access-token header — same surface DhanBroker.login uses.
        assert len(_patch_httpx.calls) == 1
        call = _patch_httpx.calls[0]
        assert call["path"] == "/fundlimit"
        assert call["headers"]["access-token"] == _VALID_TOKEN

        # DB row exists, is active, token is encrypted (NOT stored
        # plaintext under any circumstances).
        import asyncio

        async def _read_back() -> BrokerCredential:
            async with _sessionmaker() as s:
                stmt = select(BrokerCredential).where(
                    BrokerCredential.user_id == UUID(seeded_user["user_id"]),
                    BrokerCredential.broker_name == BrokerName.DHAN,
                    BrokerCredential.is_active.is_(True),
                )
                cred = (await s.execute(stmt)).scalar_one()
                return cred

        cred = asyncio.get_event_loop().run_until_complete(_read_back())
        assert cred.is_active is True
        # Encrypted ciphertext != plaintext — Fernet output is base64 of
        # IV + ciphertext + HMAC, never the plain string.
        assert cred.access_token_enc != _VALID_TOKEN
        assert security.decrypt_credential(cred.access_token_enc) == _VALID_TOKEN
        assert security.decrypt_credential(cred.client_id_enc) == _CLIENT_ID

    def test_update_dhan_token_dhan_rejects_returns_400(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
        _sessionmaker: async_sessionmaker[AsyncSession],
        seeded_user: dict[str, Any],
    ) -> None:
        """If Dhan returns 401 to the probe, the endpoint returns 400
        WITHOUT persisting anything."""
        _patch_httpx.configure(_FakeResponse(401, {"errorCode": "DH-901"}))

        resp = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert resp.status_code == 400, resp.text
        assert "Invalid Dhan token" in resp.json()["detail"]

        # No DB row was written.
        import asyncio

        async def _count() -> int:
            async with _sessionmaker() as s:
                stmt = select(BrokerCredential).where(
                    BrokerCredential.user_id == UUID(seeded_user["user_id"])
                )
                return len((await s.execute(stmt)).scalars().all())

        assert asyncio.get_event_loop().run_until_complete(_count()) == 0

    def test_update_dhan_token_invalid_format_returns_422(
        self, client_as_user: TestClient
    ) -> None:
        """A token shorter than the JWT minimum is rejected by Pydantic
        with 422 before any Dhan round-trip."""
        resp = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": "short", "dhan_client_id": _CLIENT_ID},
        )
        assert resp.status_code == 422, resp.text
        # 422 body shape is FastAPI's standard ``{"detail": [...]}``.
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("access_token" in (err.get("loc") or []) for err in detail)

    def test_update_dhan_token_upserts_existing_credential(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
        _sessionmaker: async_sessionmaker[AsyncSession],
        seeded_user: dict[str, Any],
    ) -> None:
        """A second rotation deactivates the prior active row (so there
        is exactly one active Dhan cred per user, never duplicates).

        ``cred_relink_service`` does the deactivate-old + insert-new; this
        test pins that contract from the endpoint's perspective."""
        _patch_httpx.configure(_FakeResponse(200))

        # First rotation.
        r1 = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert r1.status_code == 200

        # Second rotation — same user, fresh token.
        fresh_token = "y" * 300
        r2 = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": fresh_token, "dhan_client_id": _CLIENT_ID},
        )
        assert r2.status_code == 200

        # Exactly one active row, holding the FRESH token. The prior
        # row exists (audit history) but is_active=false.
        import asyncio

        async def _check() -> tuple[int, int, str]:
            async with _sessionmaker() as s:
                user_id = UUID(seeded_user["user_id"])
                all_stmt = select(BrokerCredential).where(
                    BrokerCredential.user_id == user_id,
                    BrokerCredential.broker_name == BrokerName.DHAN,
                )
                rows = (await s.execute(all_stmt)).scalars().all()
                active = [r for r in rows if r.is_active]
                return (
                    len(rows),
                    len(active),
                    security.decrypt_credential(active[0].access_token_enc),
                )

        total, active_count, active_token = asyncio.get_event_loop().run_until_complete(
            _check()
        )
        assert total == 2, f"expected 2 rows (1 active + 1 deactivated), got {total}"
        assert active_count == 1, f"expected exactly 1 active Dhan cred, got {active_count}"
        assert active_token == fresh_token, "active row must hold the rotated token"

    def test_update_dhan_token_first_time_without_client_id_returns_400(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
    ) -> None:
        """First-time setup without dhan_client_id has nothing to inherit
        from → 400 with an explicit Hinglish/English nudge."""
        _patch_httpx.configure(_FakeResponse(200))

        resp = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN},
        )
        assert resp.status_code == 400, resp.text
        assert "dhan_client_id" in resp.json()["detail"]

    def test_update_dhan_token_rotation_without_client_id_inherits(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
        _sessionmaker: async_sessionmaker[AsyncSession],
        seeded_user: dict[str, Any],
    ) -> None:
        """After the first connection, rotating the token alone (no
        client_id in the body) reuses the stored client_id."""
        _patch_httpx.configure(_FakeResponse(200))

        # Initial connection.
        r1 = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert r1.status_code == 200

        # Rotation — token only, no client_id.
        fresh_token = "z" * 300
        r2 = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": fresh_token},
        )
        assert r2.status_code == 200, r2.text

        # The active row carries BOTH the fresh token AND the inherited
        # client id (proof the lookup-and-reuse path fired).
        import asyncio

        async def _read() -> BrokerCredential:
            async with _sessionmaker() as s:
                stmt = select(BrokerCredential).where(
                    BrokerCredential.user_id == UUID(seeded_user["user_id"]),
                    BrokerCredential.is_active.is_(True),
                )
                return (await s.execute(stmt)).scalar_one()

        cred = asyncio.get_event_loop().run_until_complete(_read())
        assert security.decrypt_credential(cred.access_token_enc) == fresh_token
        assert security.decrypt_credential(cred.client_id_enc) == _CLIENT_ID

    def test_update_dhan_token_busts_session_cache(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
        fake_redis: fake_aioredis.FakeRedis,
        seeded_user: dict[str, Any],
    ) -> None:
        """After a successful rotation the per-user ``dhan_session:{uid}``
        Redis key MUST be gone so DhanBroker.is_session_valid re-probes
        with the new token instead of trusting a stale '1' flag.

        Pre-seeds the cache with '1' (mirrors the state
        DhanBroker._cache_session_valid would have written) and asserts
        the key is deleted post-update.
        """
        _patch_httpx.configure(_FakeResponse(200))
        uid = seeded_user["user_id"]
        # cache_set wraps the key with the "cache:" prefix; match by
        # calling the same helper so we hit the same final key.
        import asyncio

        async def _seed_cache() -> None:
            await redis_client.cache_set(
                f"dhan_session:{uid}", "1", ttl_seconds=3600
            )

        asyncio.get_event_loop().run_until_complete(_seed_cache())
        # Sanity: the seeded value is readable.
        seeded = asyncio.get_event_loop().run_until_complete(
            redis_client.cache_get(f"dhan_session:{uid}")
        )
        assert seeded == "1"

        resp = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert resp.status_code == 200, resp.text

        # Post-rotation: key is gone (cache_get returns None on miss).
        after = asyncio.get_event_loop().run_until_complete(
            redis_client.cache_get(f"dhan_session:{uid}")
        )
        assert after is None, (
            f"dhan_session:{uid} cache key was not busted — "
            "next DhanBroker.is_session_valid will trust a stale flag"
        )

    def test_update_dhan_token_dhan_unreachable_returns_502(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
    ) -> None:
        """Network failure during the probe surfaces as 502 (do NOT
        persist a token we couldn't verify)."""
        import httpx

        _patch_httpx.configure(httpx.TimeoutException("timed out"))

        resp = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert resp.status_code == 502, resp.text


# ═══════════════════════════════════════════════════════════════════════
# GET /api/brokers/dhan/status
# ═══════════════════════════════════════════════════════════════════════


class TestDhanStatus:
    def test_get_dhan_status_returns_not_connected_when_no_credential(
        self, client_as_user: TestClient
    ) -> None:
        resp = client_as_user.get("/api/brokers/dhan/status")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {
            "connected": False,
            "label": None,
            "last_updated": None,
            "expires_estimate": None,
        }

    def test_get_dhan_status_returns_connected_when_credential_exists(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
    ) -> None:
        """Seed via the update endpoint (so we exercise the full path)
        then GET status."""
        _patch_httpx.configure(_FakeResponse(200))

        seed = client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )
        assert seed.status_code == 200

        resp = client_as_user.get("/api/brokers/dhan/status")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["connected"] is True
        assert body["label"] == "Dhan – Primary"
        assert body["last_updated"] is not None
        assert body["expires_estimate"] is not None

    def test_get_dhan_status_ignores_inactive_credentials(
        self,
        client_as_user: TestClient,
        _patch_httpx: type[_FakeHttpxAsyncClient],
        _sessionmaker: async_sessionmaker[AsyncSession],
        seeded_user: dict[str, Any],
    ) -> None:
        """If the only Dhan row is is_active=false, status reports
        not-connected (the deactivated-then-not-re-added scenario)."""
        _patch_httpx.configure(_FakeResponse(200))

        # Create then immediately soft-delete the cred.
        client_as_user.post(
            "/api/brokers/dhan/update-token",
            json={"access_token": _VALID_TOKEN, "dhan_client_id": _CLIENT_ID},
        )

        import asyncio

        async def _soft_delete() -> None:
            async with _sessionmaker() as s:
                stmt = select(BrokerCredential).where(
                    BrokerCredential.user_id == UUID(seeded_user["user_id"]),
                    BrokerCredential.is_active.is_(True),
                )
                cred = (await s.execute(stmt)).scalar_one()
                cred.is_active = False
                await s.commit()

        asyncio.get_event_loop().run_until_complete(_soft_delete())

        resp = client_as_user.get("/api/brokers/dhan/status")
        assert resp.status_code == 200
        assert resp.json()["connected"] is False

    def test_get_dhan_status_requires_auth_401(
        self, client_unauth: TestClient
    ) -> None:
        resp = client_unauth.get("/api/brokers/dhan/status")
        assert resp.status_code == 401, resp.text
