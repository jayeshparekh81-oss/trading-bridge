"""Same-fire duplicate-ENTRY guard (worker layer).

The webhook's content-hash claim (60s TTL) absorbs identical fast retries;
this guard closes the remaining window: a replay of the SAME Pine fire
(identical ``timestamp`` payload field) arriving >60s later — or with a
byte-different body — must NOT execute a second time, because the executor
would SUM it into the open position and double live exposure.

Runs on the integration harness (aiosqlite + fakeredis + eager Celery), same
as test_strategy_webhook_async.py: each POST drives webhook → dispatch →
worker synchronously.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.strategy_signal import StrategySignal

from tests.integration.conftest import HMAC_HEADER, _sign

FIRE_TS = "2026-07-13T09:20:00.123456+00:00"


def _entry_body(fire_ts: str | None = FIRE_TS, **overrides: Any) -> bytes:
    base: dict[str, Any] = {
        "action": "BUY",
        "symbol": "NIFTY",
        "quantity": 1,
        "order_type": "market",
        "price": 22500.0,
    }
    if fire_ts is not None:
        base["timestamp"] = fire_ts
    base.update(overrides)
    return json.dumps(base).encode("utf-8")


def _post(client: TestClient, token: str, body: bytes):
    return client.post(
        f"/api/webhook/strategy/{token}",
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )


def _load_signal(db_session_maker, signal_id: uuid.UUID) -> StrategySignal | None:
    async def _load():
        async with db_session_maker() as s:
            return await s.get(StrategySignal, signal_id)

    return asyncio.get_event_loop().run_until_complete(_load())


class TestSameFireDuplicateSuppressed:
    def test_replay_with_different_body_is_suppressed(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Same fire-time, byte-different body (dual-alert / re-encode case):
        first executes, second is marked duplicate and never executes."""
        first = _post(client, seed["token_plain"], _entry_body())
        assert first.status_code == 202, first.text
        sig1 = _load_signal(db_session_maker, uuid.UUID(first.json()["signal_id"]))
        assert sig1 is not None and sig1.status == "executed", sig1.notes

        # different price → different raw body → webhook 60s hash does NOT
        # absorb it; only the worker guard can.
        second = _post(client, seed["token_plain"],
                       _entry_body(price=22501.0))
        assert second.status_code == 202, second.text
        sig2 = _load_signal(db_session_maker, uuid.UUID(second.json()["signal_id"]))
        assert sig2 is not None
        assert sig2.status == "duplicate", f"status={sig2.status} notes={sig2.notes!r}"
        assert str(sig1.id) in (sig2.notes or "")

    def test_distinct_fires_both_execute(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Different fire-times are genuine signals — no false positive."""
        r1 = _post(client, seed["token_plain"], _entry_body())
        r2 = _post(client, seed["token_plain"],
                   _entry_body(fire_ts="2026-07-13T10:45:00.654321+00:00"))
        for r in (r1, r2):
            assert r.status_code == 202, r.text
            sig = _load_signal(db_session_maker, uuid.UUID(r.json()["signal_id"]))
            assert sig is not None and sig.status == "executed", sig.notes

    def test_prior_failed_attempt_does_not_block_retry(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """A failed prior attempt (e.g. funds block) takes no duplicate slot —
        a later re-fire of the same fire-time may execute (mirrors the broker
        guard's pre-send-failure semantics)."""
        async def _seed_failed() -> None:
            async with db_session_maker() as s:
                s.add(StrategySignal(
                    id=uuid.uuid4(),
                    user_id=seed["user_id"],
                    strategy_id=seed["strategy_id"],
                    symbol="NIFTY",
                    action="ENTRY",
                    quantity=1,
                    order_type="market",
                    status="failed",
                    raw_payload={"timestamp": FIRE_TS, "action": "ENTRY"},
                    received_at=datetime.now(UTC),
                ))
                await s.commit()

        asyncio.get_event_loop().run_until_complete(_seed_failed())

        resp = _post(client, seed["token_plain"], _entry_body())
        assert resp.status_code == 202, resp.text
        sig = _load_signal(db_session_maker, uuid.UUID(resp.json()["signal_id"]))
        assert sig is not None and sig.status == "executed", sig.notes

    def test_missing_timestamp_skips_guard(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Payloads without a fire-time can't be deduped on it — they execute
        normally (guard is a no-op, never a blocker)."""
        r1 = _post(client, seed["token_plain"], _entry_body(fire_ts=None))
        r2 = _post(client, seed["token_plain"],
                   _entry_body(fire_ts=None, price=22502.0))
        for r in (r1, r2):
            assert r.status_code == 202, r.text
            sig = _load_signal(db_session_maker, uuid.UUID(r.json()["signal_id"]))
            assert sig is not None and sig.status == "executed", sig.notes

    def test_duplicate_creates_no_second_position_growth(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """The whole point: position quantity must not grow from a replay."""
        from app.db.models.strategy_position import StrategyPosition

        _post(client, seed["token_plain"], _entry_body())
        _post(client, seed["token_plain"], _entry_body(price=22503.0))

        async def _positions():
            async with db_session_maker() as s:
                rows = (await s.execute(select(StrategyPosition))).scalars().all()
                return [(p.total_quantity, p.status) for p in rows]

        positions = asyncio.get_event_loop().run_until_complete(_positions())
        assert len(positions) == 1, positions
        assert positions[0][0] == 1  # unchanged by the replay
