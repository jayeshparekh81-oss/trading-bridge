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

import json
from typing import Any
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import redis_client
from tests.integration.conftest import (
    HMAC_HEADER,
    _seed_user_with_strategy,
    _sign,
)


def _exit_payload(signal_id: str) -> bytes:
    """EXIT action skips the entry executor — keeps 60-call loop fast.

    Post direct-exit refactor (Sun 2026-05-03), EXIT requires a `side`
    so the handler knows which open position to target. We don't have an
    open position in this test seed, so the handler will short-circuit
    with `ignored: no_open_position` after the rate limiter — that's
    fine for what these tests assert (rate limit only).
    """
    return json.dumps(
        {
            "action": "EXIT",
            "side": "long",
            "symbol": "NIFTY",
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
