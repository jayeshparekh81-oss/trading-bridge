"""Kill-switch tests for ``POST /api/webhook/strategy/{token}``.

Pins the manual kill switch ported from legacy ``app.api.webhook``:
Redis flag ``kill:{user_id}``. Tripping it blocks all subsequent
signals — including paper-mode runs — until manually cleared.

Runs AFTER the idempotency claim and BEFORE the time-of-day guard,
mirroring legacy ordering.

Tests deliberately do NOT cover the user-active check, max-daily-trades,
circuit breaker, or post-trade auto-trip — those depend on the
verified-P&L pipeline (Migration 007) and a fixture-engine fix for
SQLite-in-memory User INSERT visibility, both scoped to a follow-up.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import redis_client
from tests.integration.conftest import (
    HMAC_HEADER,
    _seed_user_with_strategy,
    _sign,
)


def _exit_payload(signal_id: str) -> bytes:
    """EXIT skips the entry executor — keeps tests fast and deterministic.

    Post direct-exit refactor (Sun 2026-05-03): EXIT requires `side`. No
    open position in seed → handler short-circuits with `ignored:
    no_open_position` after kill-switch check, which is what these tests
    care about.
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


async def _trip(fake_redis: fake_aioredis.FakeRedis, user_id: UUID) -> None:
    """Set the kill-switch flag for ``user_id`` to ``TRIPPED`` in fake Redis."""
    await redis_client.set_kill_switch_status(
        user_id, redis_client.KILL_SWITCH_TRIPPED, redis_client=fake_redis
    )


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestKillSwitchOff:
    def test_default_active_state_admits_signal(
        self,
        client: TestClient,
        seed: dict[str, Any],
    ) -> None:
        """No flag in Redis → ``get_kill_switch_status`` returns ACTIVE → 202."""
        resp = _post(client, seed["token_plain"], signal_id="ks-off-1")
        assert resp.status_code == 202, resp.text
        assert resp.json()["status"] == "accepted"


class TestKillSwitchTripped:
    def test_tripped_returns_403_with_legacy_detail(
        self,
        client: TestClient,
        seed: dict[str, Any],
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        """TRIPPED → 403 with the same detail string the legacy webhook uses."""
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            _trip(fake_redis, seed["user_id"])
        )

        resp = _post(client, seed["token_plain"], signal_id="ks-trip-1")
        assert resp.status_code == 403, resp.text
        assert resp.json() == {
            "detail": "Kill switch is TRIPPED — trading paused."
        }


class TestPerUserKillSwitch:
    def test_user_a_tripped_does_not_block_user_b(
        self,
        client: TestClient,
        seed: dict[str, Any],
        fake_redis: fake_aioredis.FakeRedis,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Kill switch is per-user (Redis key = ``kill:{user_id}``)."""
        import asyncio

        seed_b = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker, email="kill-b@tradetri.com"
            )
        )

        asyncio.get_event_loop().run_until_complete(
            _trip(fake_redis, seed["user_id"])
        )

        a = _post(client, seed["token_plain"], signal_id="ks-a-1")
        b = _post(client, seed_b["token_plain"], signal_id="ks-b-1")

        assert a.status_code == 403, a.text
        assert b.status_code == 202, b.text


class TestKillSwitchInPaperMode:
    def test_kill_switch_blocks_even_when_paper_mode_on(
        self,
        client: TestClient,
        seed: dict[str, Any],
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        """Paper mode is a broker-call short-circuit, NOT a gate-bypass.

        The ``client`` fixture forces ``STRATEGY_PAPER_MODE=true``, so a
        TRIPPED kill switch under that fixture proves paper-mode does
        not soften the safety gate. Pinning this here so a future
        contributor can't quietly add an ``if paper_mode: return`` short-
        circuit and have it ship green.
        """
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            _trip(fake_redis, seed["user_id"])
        )

        resp = _post(client, seed["token_plain"], signal_id="ks-paper-1")
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"] == "Kill switch is TRIPPED — trading paused."
