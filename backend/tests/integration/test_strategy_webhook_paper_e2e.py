"""End-to-end paper-mode test for ``POST /api/webhook/strategy/{token}``.

Drives the full strategy pipeline with the broker network call short-
circuited by ``strategy_paper_mode=True``:

    HMAC-signed POST  →  webhook receiver
                      →  StrategySignal row (status=received)
                      →  background AI validator (bypassed by
                         strategy.ai_validation_enabled=False)
                      →  strategy_executor in paper mode
                      →  StrategyExecution + StrategyPosition rows
                      →  signal.status='executed', broker_order_id='PAPER-…'

Stack: aiosqlite in-memory DB, fakeredis for the kill-switch & cache,
real Pydantic + real ``app.main.create_app()``. No broker SDK is hit
because the executor's paper branch never touches it.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import generate_webhook_token
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from tests.integration.conftest import HMAC_HEADER, _sign


def _payload(**overrides: Any) -> bytes:
    """Native TRADETRI payload — the strategy receiver's primary shape."""
    base: dict[str, Any] = {
        "action": "BUY",
        "symbol": "NIFTY",
        "quantity": 1,
        "order_type": "market",
        "price": 22500.0,
    }
    base.update(overrides)
    return json.dumps(base).encode("utf-8")


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


def _wait_for_executed(
    db_session_maker: async_sessionmaker[AsyncSession],
    signal_id: uuid.UUID,
    *,
    timeout_s: float = 5.0,
) -> StrategySignal:
    """Poll until the signal reaches a terminal status.

    FastAPI's TestClient runs ``BackgroundTasks`` synchronously after
    the response, so this should resolve on the first iteration. The
    loop is defence-in-depth for slow CI machines.
    """
    deadline = time.perf_counter() + timeout_s

    async def _poll() -> StrategySignal:
        while True:
            async with db_session_maker() as s:
                row = await s.get(StrategySignal, signal_id)
                if row is not None and row.status in {
                    "executed",
                    "rejected",
                    "failed",
                }:
                    return row
            if time.perf_counter() > deadline:
                async with db_session_maker() as s:
                    last = await s.get(StrategySignal, signal_id)
                raise AssertionError(
                    f"signal {signal_id} did not reach terminal status in "
                    f"{timeout_s}s — last status: "
                    f"{last.status if last else 'missing'}"
                )
            await asyncio.sleep(0.05)

    return asyncio.get_event_loop().run_until_complete(_poll())


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestHappyPath:
    def test_paper_buy_flows_to_executed_position(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        body = _payload(action="BUY", quantity=1)
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["queued_for_processing"] is True
        signal_id = uuid.UUID(data["signal_id"])

        sig = _wait_for_executed(db_session_maker, signal_id)
        assert sig.status == "executed", f"notes={sig.notes!r}"

        async def _fetch_position() -> StrategyPosition | None:
            async with db_session_maker() as s:
                stmt = select(StrategyPosition).where(
                    StrategyPosition.signal_id == signal_id
                )
                return (await s.execute(stmt)).scalar_one_or_none()

        position = asyncio.get_event_loop().run_until_complete(_fetch_position())
        assert position is not None, "executor must open a strategy_position"
        assert position.status == "open"
        assert position.total_quantity == 1
        assert position.remaining_quantity == 1


class TestSignature:
    def test_invalid_signature_returns_401(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: "deadbeef", "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_missing_signature_returns_401(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401


class TestQuantityCeiling:
    def test_quantity_above_ceiling_rejected_400(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        # Convention switched from lots to contracts; ceiling is 10000.
        # Pick a value comfortably above to exercise the rejection path.
        body = _payload(quantity=20000)
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400
        # New structured error format (post direct-exit refactor):
        # detail is a dict with `code` + `message`, not a string.
        detail = resp.json()["detail"]
        assert detail["code"] == "quantity_exceeds_ceiling"
        assert "ceiling" in detail["message"].lower()


class TestUnknownToken:
    def test_unknown_token_returns_404(self, client: TestClient) -> None:
        bogus = generate_webhook_token()
        body = _payload()
        resp = client.post(
            _url(bogus),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 404


class TestPaperOrderId:
    def test_broker_order_id_starts_with_PAPER(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Paper fills mark themselves with a ``PAPER-`` prefix.

        The strategy_executor mints ``PAPER-{uuid}`` whenever
        ``settings.strategy_paper_mode`` is True. Asserting on the
        prefix is what guarantees no real broker call slipped through.
        """
        body = _payload(quantity=1)
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 202
        signal_id = uuid.UUID(resp.json()["signal_id"])
        sig = _wait_for_executed(db_session_maker, signal_id)
        assert sig.status == "executed"

        async def _fetch_position() -> StrategyPosition | None:
            async with db_session_maker() as s:
                stmt = select(StrategyPosition).where(
                    StrategyPosition.signal_id == signal_id
                )
                return (await s.execute(stmt)).scalar_one_or_none()

        pos = asyncio.get_event_loop().run_until_complete(_fetch_position())
        assert pos is not None
        # The broker_order_id is on strategy_executions (one row per leg);
        # fetch via signal to keep the assertion broker-agnostic.
        async def _fetch_executions() -> list[Any]:
            from app.db.models.strategy_execution import StrategyExecution

            async with db_session_maker() as s:
                stmt = select(StrategyExecution).where(
                    StrategyExecution.signal_id == signal_id
                )
                return list((await s.execute(stmt)).scalars().all())

        executions = asyncio.get_event_loop().run_until_complete(
            _fetch_executions()
        )
        assert executions, "executor must persist a strategy_executions row"
        for ex in executions:
            assert ex.broker_order_id.startswith("PAPER-"), ex.broker_order_id
