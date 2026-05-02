"""Tests for Gates B / C / E on ``POST /api/webhook/strategy/{token}``.

Gates A (manual kill switch) was wired in Task #3 — covered by
:mod:`test_strategy_webhook_kill_switch`. Gate D (volatility CB OR
consecutive-loss CB) is deferred to a Tier-2 polish task.

This module covers the three gates wired in Task #5:

* **Gate B — User active** — request-time DB read of ``users.is_active``.
* **Gate C — Max daily trades** — request-time check of the per-user
  Redis counter against :class:`KillSwitchConfig.max_daily_trades`.
* **Gate E — Post-trade auto-trip** — post-success hook in
  ``_process_signal_in_background`` that calls
  :meth:`KillSwitchService.check_and_trigger`. When today's daily P&L
  has crossed ``-max_daily_loss_inr``, it flips the Redis kill switch
  to TRIPPED so the next webhook is rejected by Gate A.

All tests rely on the conftest's StaticPool + position-loop-disabled
fixture so seeded ``users`` rows are visible to the request session.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import redis_client
from app.services.kill_switch_service import kill_switch_service
from tests.integration.conftest import (
    HMAC_HEADER,
    _seed_user_with_strategy,
    _sign,
)


def _payload(*, action: str = "BUY", signal_id: str | None = None) -> bytes:
    """Native TRADETRI payload — BUY triggers the entry executor + post-trade hooks."""
    body: dict[str, Any] = {
        "action": action,
        "symbol": "NIFTY",
        "quantity": 1,
        "order_type": "market",
        "price": 22500.0,
    }
    if signal_id is not None:
        body["signal_id"] = signal_id
    return json.dumps(body).encode("utf-8")


def _post(client: TestClient, token: str, *, action: str = "BUY", signal_id: str | None = None) -> Any:
    body = _payload(action=action, signal_id=signal_id)
    return client.post(
        f"/api/webhook/strategy/{token}",
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )


# ═══════════════════════════════════════════════════════════════════════
# Gate B — User active check
# ═══════════════════════════════════════════════════════════════════════


class TestGateBUserInactive:
    def test_inactive_user_returns_403(
        self,
        client: TestClient,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """``users.is_active = False`` → 403 + legacy detail string."""
        import asyncio

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-b-inactive@tradetri.com",
                user_active=False,
            )
        )

        resp = _post(client, seeded["token_plain"], action="EXIT", signal_id="b-inact-1")
        assert resp.status_code == 403, resp.text
        assert resp.json() == {"detail": "User account is inactive."}

    def test_per_user_user_a_inactive_user_b_active(
        self,
        client: TestClient,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Disabling user A doesn't affect user B."""
        import asyncio

        seed_a = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-b-a@tradetri.com",
                user_active=False,
            )
        )
        seed_b = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-b-b@tradetri.com",
                user_active=True,
            )
        )

        a = _post(client, seed_a["token_plain"], action="EXIT", signal_id="b-a-1")
        b = _post(client, seed_b["token_plain"], action="EXIT", signal_id="b-b-1")

        assert a.status_code == 403, a.text
        assert b.status_code == 202, b.text


# ═══════════════════════════════════════════════════════════════════════
# Gate C — Max daily trades
# ═══════════════════════════════════════════════════════════════════════


class TestGateCMaxDailyTrades:
    def test_count_at_cap_blocks_next_request(
        self,
        client: TestClient,
        fake_redis: fake_aioredis.FakeRedis,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Pre-bump the Redis counter to the cap; next webhook → 403.

        Cap is set to 2 (not the default 50) for test speed. Mechanism is
        identical — same ``check_max_daily_trades`` call, same legacy
        detail string ``"Max daily trades reached (N/M)."``.
        """
        import asyncio

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-c-cap@tradetri.com",
                kill_switch_max_trades=2,
            )
        )

        # Pre-bump the daily-trades counter to the cap (2).
        async def _pre_bump() -> None:
            await kill_switch_service.increment_daily_trades(seeded["user_id"])
            await kill_switch_service.increment_daily_trades(seeded["user_id"])

        asyncio.get_event_loop().run_until_complete(_pre_bump())

        resp = _post(client, seeded["token_plain"], action="EXIT", signal_id="c-cap-1")
        assert resp.status_code == 403, resp.text
        assert resp.json() == {"detail": "Max daily trades reached (2/2)."}

    def test_per_user_buckets(
        self,
        client: TestClient,
        fake_redis: fake_aioredis.FakeRedis,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """User A's saturated counter does not leak into user B's bucket."""
        import asyncio

        seed_a = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-c-a@tradetri.com",
                kill_switch_max_trades=1,
            )
        )
        seed_b = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-c-b@tradetri.com",
                kill_switch_max_trades=1,
            )
        )

        async def _saturate_a() -> None:
            await kill_switch_service.increment_daily_trades(seed_a["user_id"])

        asyncio.get_event_loop().run_until_complete(_saturate_a())

        a = _post(client, seed_a["token_plain"], action="EXIT", signal_id="c-a-1")
        b = _post(client, seed_b["token_plain"], action="EXIT", signal_id="c-b-1")

        assert a.status_code == 403, a.text
        assert "1/1" in a.json()["detail"]
        assert b.status_code == 202, b.text


# ═══════════════════════════════════════════════════════════════════════
# Gate E — Post-trade auto-trip
# ═══════════════════════════════════════════════════════════════════════


class TestGateEAutoTrip:
    def test_bad_pnl_trips_kill_switch_after_executed_trade(
        self,
        client: TestClient,
        fake_redis: fake_aioredis.FakeRedis,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: Any,
    ) -> None:
        """Pre-set a losing daily P&L; after one BUY runs through paper-mode,
        ``check_and_trigger`` flips the kill switch to TRIPPED.

        The square-off path inside ``check_and_trigger`` is a no-op via
        monkeypatch — we're testing the GATE fires, not the square-off
        mechanics (covered by the kill_switch_service unit suite).
        """
        import asyncio

        # Square-off side-effect would try to call real broker SDKs;
        # short-circuit it for this test.
        monkeypatch.setattr(
            "app.services.kill_switch_service.KillSwitchService._execute_emergency_square_off",
            _AsyncReturning(([], [])),
        )

        seeded = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-e-trip@tradetri.com",
                kill_switch_max_loss_inr=Decimal("10000"),
            )
        )

        # Seed a losing daily P&L of -15,000 (below the -10,000 threshold).
        async def _seed_bad_pnl() -> None:
            await redis_client.set_daily_pnl(
                seeded["user_id"], Decimal("-15000"), redis_client=fake_redis
            )

        asyncio.get_event_loop().run_until_complete(_seed_bad_pnl())

        resp = _post(client, seeded["token_plain"], action="BUY", signal_id="e-trip-1")
        assert resp.status_code == 202, resp.text

        # FastAPI BackgroundTasks runs synchronously after the response
        # returns under TestClient, so by here _process_signal_in_background
        # has already executed the post-trade hook.
        async def _read_status() -> str:
            return await redis_client.get_kill_switch_status(
                seeded["user_id"], redis_client=fake_redis
            )

        status = asyncio.get_event_loop().run_until_complete(_read_status())
        assert status == redis_client.KILL_SWITCH_TRIPPED, (
            f"Expected kill switch TRIPPED, got {status!r}. "
            "Post-trade auto-trip did not fire."
        )

    def test_per_user_only_breaching_user_is_tripped(
        self,
        client: TestClient,
        fake_redis: fake_aioredis.FakeRedis,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: Any,
    ) -> None:
        """User A has a losing P&L; user B does not.

        After A's trade, A's switch trips and B's stays ACTIVE.
        """
        import asyncio

        monkeypatch.setattr(
            "app.services.kill_switch_service.KillSwitchService._execute_emergency_square_off",
            _AsyncReturning(([], [])),
        )

        seed_a = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-e-a@tradetri.com",
                kill_switch_max_loss_inr=Decimal("10000"),
            )
        )
        seed_b = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(
                db_session_maker,
                email="gate-e-b@tradetri.com",
                kill_switch_max_loss_inr=Decimal("10000"),
            )
        )

        async def _seed_pnls() -> None:
            await redis_client.set_daily_pnl(
                seed_a["user_id"], Decimal("-15000"), redis_client=fake_redis
            )
            # User B: leave P&L untouched (defaults to 0 in Redis).

        asyncio.get_event_loop().run_until_complete(_seed_pnls())

        ra = _post(client, seed_a["token_plain"], action="BUY", signal_id="e-pa-1")
        rb = _post(client, seed_b["token_plain"], action="BUY", signal_id="e-pb-1")
        assert ra.status_code == 202, ra.text
        assert rb.status_code == 202, rb.text

        async def _read_both() -> tuple[str, str]:
            sa = await redis_client.get_kill_switch_status(
                seed_a["user_id"], redis_client=fake_redis
            )
            sb = await redis_client.get_kill_switch_status(
                seed_b["user_id"], redis_client=fake_redis
            )
            return sa, sb

        status_a, status_b = asyncio.get_event_loop().run_until_complete(_read_both())
        assert status_a == redis_client.KILL_SWITCH_TRIPPED
        assert status_b == redis_client.KILL_SWITCH_ACTIVE


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


class _AsyncReturning:
    """Awaitable callable returning a fixed value — Gate E side-effect stub."""

    def __init__(self, value: Any) -> None:
        self._value = value

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._value
