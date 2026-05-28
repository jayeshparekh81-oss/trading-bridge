"""Exit-class actions must NOT re-resolve the contract symbol (14:30 fix).

Two layers:
  * unit — ``find_open_position_by_strategy`` (symbol-agnostic, side-normalized).
  * webhook — through the real handler: ENTRY re-resolves (unchanged); EXIT /
    SL_HIT / PARTIAL pin to the open position's STORED symbol and never call the
    resolver (so an expiry-day next-month roll can't orphan the exit).

Stack mirrors test_strategy_webhook_paper_e2e: aiosqlite, fakeredis, real app.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.services.position_lookup import find_open_position_by_strategy
from tests.integration.conftest import HMAC_HEADER, _sign


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


def _run(coro):
    """Drive a coroutine to completion from a sync (TestClient) test."""
    return asyncio.get_event_loop().run_until_complete(coro)


async def _add_position(
    maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    *,
    symbol: str,
    side: str = "buy",
    status: str = "open",
    opened_offset_s: int = 0,
) -> uuid.UUID:
    async with maker() as s:
        pos = StrategyPosition(
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            broker_credential_id=seed["credential_id"],
            symbol=symbol,
            side=side,
            total_quantity=1,
            remaining_quantity=1,
            status=status,
            opened_at=datetime.now(UTC) + timedelta(seconds=opened_offset_s),
        )
        s.add(pos)
        await s.commit()
        return pos.id


# ════════════════════════════════════════════════════════════════════════
# Unit — find_open_position_by_strategy
# ════════════════════════════════════════════════════════════════════════
class TestFindOpenPosition:
    async def test_finds_open_position_symbol_agnostic(
        self, db_session_maker: async_sessionmaker[AsyncSession], seed: dict[str, Any]
    ) -> None:
        await _add_position(db_session_maker, seed, symbol="BSE-MAY2026-FUT")
        async with db_session_maker() as s:
            pos = await find_open_position_by_strategy(
                s, strategy_id=seed["strategy_id"], side="long"
            )
        assert pos is not None
        assert pos.symbol == "BSE-MAY2026-FUT"

    async def test_side_normalized_long_to_buy(
        self, db_session_maker: async_sessionmaker[AsyncSession], seed: dict[str, Any]
    ) -> None:
        # Position stored as 'buy'; payload sends 'long' → must match.
        await _add_position(db_session_maker, seed, symbol="X-FUT", side="buy")
        async with db_session_maker() as s:
            assert (
                await find_open_position_by_strategy(
                    s, strategy_id=seed["strategy_id"], side="long"
                )
                is not None
            )

    async def test_closed_position_not_returned(
        self, db_session_maker: async_sessionmaker[AsyncSession], seed: dict[str, Any]
    ) -> None:
        await _add_position(db_session_maker, seed, symbol="X-FUT", status="closed")
        async with db_session_maker() as s:
            assert await find_open_position_by_strategy(s, strategy_id=seed["strategy_id"]) is None

    async def test_partial_status_counts_as_open(
        self, db_session_maker: async_sessionmaker[AsyncSession], seed: dict[str, Any]
    ) -> None:
        await _add_position(db_session_maker, seed, symbol="X-FUT", status="partial")
        async with db_session_maker() as s:
            assert (
                await find_open_position_by_strategy(s, strategy_id=seed["strategy_id"]) is not None
            )

    async def test_picks_most_recent(
        self, db_session_maker: async_sessionmaker[AsyncSession], seed: dict[str, Any]
    ) -> None:
        await _add_position(db_session_maker, seed, symbol="OLD-FUT", opened_offset_s=0)
        await _add_position(db_session_maker, seed, symbol="NEW-FUT", opened_offset_s=60)
        async with db_session_maker() as s:
            pos = await find_open_position_by_strategy(s, strategy_id=seed["strategy_id"])
        assert pos is not None
        assert pos.symbol == "NEW-FUT"

    async def test_none_when_no_open_position(
        self, db_session_maker: async_sessionmaker[AsyncSession], seed: dict[str, Any]
    ) -> None:
        async with db_session_maker() as s:
            assert await find_open_position_by_strategy(s, strategy_id=seed["strategy_id"]) is None

    async def test_malformed_side_does_not_hide_position(
        self, db_session_maker: async_sessionmaker[AsyncSession], seed: dict[str, Any]
    ) -> None:
        # Defensive: an unrecognized side must NOT filter out an open position.
        await _add_position(db_session_maker, seed, symbol="X-FUT", side="buy")
        async with db_session_maker() as s:
            assert (
                await find_open_position_by_strategy(
                    s, strategy_id=seed["strategy_id"], side="garbage"
                )
                is not None
            )


# ════════════════════════════════════════════════════════════════════════
# Webhook — gating behavior
# ════════════════════════════════════════════════════════════════════════
@pytest.fixture
def _spy_resolver(monkeypatch: pytest.MonkeyPatch):
    """Replace resolve_or_passthrough with a call-recording stub.

    Returns a next-month symbol to simulate the dangerous expiry-day roll.
    """
    calls: list[str] = []

    async def _fake(symbol: str) -> str:
        calls.append(symbol)
        return "BSE-JUN2026-FUT"  # the "rolled" symbol the bug would use

    monkeypatch.setattr("app.api.strategy_webhook.resolve_or_passthrough", _fake)
    return calls


async def _persisted_signal(
    maker: async_sessionmaker[AsyncSession], signal_id: uuid.UUID
) -> StrategySignal:
    async with maker() as s:
        sig = await s.get(StrategySignal, signal_id)
        assert sig is not None
        return sig


def _post(client: TestClient, token: str, payload: dict[str, Any]):
    body = json.dumps(payload).encode()
    return client.post(
        _url(token),
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )


class TestWebhookGating:
    def test_entry_action_uses_resolved_symbol(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _spy_resolver: list[str],
    ) -> None:
        resp = _post(
            client, seed["token_plain"], {"action": "BUY", "symbol": "BSE1!", "quantity": 1}
        )
        assert resp.status_code == 202, resp.text
        sid = uuid.UUID(resp.json()["signal_id"])
        sig = _run(_persisted_signal(db_session_maker, sid))
        assert sig.symbol == "BSE-JUN2026-FUT"  # ENTRY re-resolves (unchanged)
        assert _spy_resolver == ["BSE1!"]

    def test_exit_action_uses_stored_position_symbol(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _spy_resolver: list[str],
    ) -> None:
        _run(_add_position(db_session_maker, seed, symbol="BSE-MAY2026-FUT", side="buy"))
        resp = _post(
            client, seed["token_plain"], {"action": "EXIT", "symbol": "BSE1!", "side": "long"}
        )
        assert resp.status_code == 202, resp.text
        sid = uuid.UUID(resp.json()["signal_id"])
        sig = _run(_persisted_signal(db_session_maker, sid))
        assert sig.symbol == "BSE-MAY2026-FUT"  # STORED, not the rolled BSE-JUN
        assert _spy_resolver == []  # resolver NOT called for exits

    def test_sl_hit_uses_stored_symbol(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _spy_resolver: list[str],
    ) -> None:
        _run(_add_position(db_session_maker, seed, symbol="BSE-MAY2026-FUT", side="buy"))
        resp = _post(
            client, seed["token_plain"], {"action": "SL_HIT", "symbol": "BSE1!", "side": "long"}
        )
        assert resp.status_code == 202, resp.text
        sid = uuid.UUID(resp.json()["signal_id"])
        sig = _run(_persisted_signal(db_session_maker, sid))
        assert sig.symbol == "BSE-MAY2026-FUT"
        assert _spy_resolver == []

    def test_partial_uses_stored_symbol(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _spy_resolver: list[str],
    ) -> None:
        _run(_add_position(db_session_maker, seed, symbol="BSE-MAY2026-FUT", side="buy"))
        resp = _post(
            client,
            seed["token_plain"],
            {"action": "PARTIAL", "symbol": "BSE1!", "side": "long", "closePct": 50},
        )
        assert resp.status_code == 202, resp.text
        sid = uuid.UUID(resp.json()["signal_id"])
        sig = _run(_persisted_signal(db_session_maker, sid))
        assert sig.symbol == "BSE-MAY2026-FUT"
        assert _spy_resolver == []

    def test_exit_no_open_position_benign_no_resolve(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _spy_resolver: list[str],
    ) -> None:
        # No open position → not silent-but-dangerous: persists raw symbol,
        # does NOT re-resolve, responds normally (no retry-storm error).
        resp = _post(
            client, seed["token_plain"], {"action": "EXIT", "symbol": "BSE1!", "side": "long"}
        )
        assert resp.status_code == 202, resp.text
        sid = uuid.UUID(resp.json()["signal_id"])
        sig = _run(_persisted_signal(db_session_maker, sid))
        assert sig.symbol == "BSE1!"  # un-resolved, not rolled
        assert _spy_resolver == []
