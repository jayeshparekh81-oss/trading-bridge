"""EXPIRY_ROLLOVER_SPEC tests 6-12 — the CROSS-BOUNDARY exit class.

THE GOVERNING SENTENCE (EXPIRY_ROLLOVER_SPEC.md): the N=5 rule governs ENTRY SELECTION ONLY.
Exits and partials always follow the position they belong to — the stored
``open_position.symbol`` — on both sides of every switch, forever.

THE FAILURE THIS GUARDS (catastrophic-if-wrong): a position is ENTERED in AUG before the N=5
boundary. Five calendar days before AUG expires the resolver starts serving SEP to new entries —
correctly. If an EXIT for that AUG position were re-resolved at that moment it would carry SEP,
the symbol-keyed exit lookup would miss the AUG position, and the exit would silently no-op —
leaving a live position to run into physical settlement. That is the same shape as the 14:30
expiry-day bug (fixed 2026-05-26), arriving through the new N=5 door.

WHAT THESE ASSERT, per the spec: the ACTUAL SYMBOL that reaches the executor equals the ENTRY's
contract — not merely that an order was placed. The persisted ``StrategySignal.symbol`` is that
value: it is what the downstream executor consumes.

The resolver is stubbed to return the NEXT month (SEP) on every call, which is exactly what the
real N=5 policy does after the boundary (unit-proven in tests 1-5,
tests/services/test_futures_resolver.py). So if any exit path re-resolved, these tests would see
SEP and fail. Stack mirrors test_exit_skip_reresolve.py.
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
from tests.integration.conftest import HMAC_HEADER, _sign

#: the contract the position was ENTERED in, before the N=5 switch.
AUG = "BSE-AUG2026-FUT"
#: what the resolver serves to NEW ENTRIES from T-5 onward. An exit must never carry this.
SEP = "BSE-SEP2026-FUT"


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _open_position(
    maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    *,
    symbol: str = AUG,
    side: str = "buy",
) -> uuid.UUID:
    """A position ENTERED pre-switch, still open when the exit arrives post-switch."""
    async with maker() as s:
        pos = StrategyPosition(
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            broker_credential_id=seed["credential_id"],
            symbol=symbol,
            side=side,
            total_quantity=2,
            remaining_quantity=2,
            status="open",
            opened_at=datetime.now(UTC) - timedelta(days=8),  # entered before the boundary
        )
        s.add(pos)
        await s.commit()
        return pos.id


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


@pytest.fixture
def _post_boundary_resolver(monkeypatch: pytest.MonkeyPatch):
    """The resolver AFTER the N=5 switch: every call returns the next month.

    Recording the calls is half the assertion — an exit that never re-resolves cannot carry the
    wrong contract by construction, which is a stronger guarantee than "it happened to match".
    """
    calls: list[str] = []

    async def _fake(symbol: str) -> str:
        calls.append(symbol)
        return SEP

    monkeypatch.setattr("app.api.strategy_webhook.resolve_or_passthrough", _fake)
    return calls


# ════════════════════════════════════════════════════════════════════════
# Tests 6-11 — every exit class, both sides, across the boundary
# ════════════════════════════════════════════════════════════════════════
class TestCrossBoundaryExits:
    """Spec 6-11. Parametrized over the full cross-product the spec enumerates, because the
    three exit actions take DIFFERENT code paths downstream (PARTIAL reduces, EXIT/SL_HIT
    close) and the two sides resolve through different position lookups."""

    @pytest.mark.parametrize(
        ("spec_no", "action", "payload_side", "stored_side"),
        [
            (6, "PARTIAL", "long", "buy"),
            (7, "EXIT", "long", "buy"),
            (8, "SL_HIT", "long", "buy"),      # the most common exit reason
            (9, "PARTIAL", "short", "sell"),
            (10, "EXIT", "short", "sell"),
            (11, "SL_HIT", "short", "sell"),
        ],
    )
    def test_exit_carries_the_entry_contract(
        self,
        spec_no: int,
        action: str,
        payload_side: str,
        stored_side: str,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _post_boundary_resolver: list[str],
    ) -> None:
        _run(_open_position(db_session_maker, seed, symbol=AUG, side=stored_side))

        payload: dict[str, Any] = {"action": action, "symbol": "BSE1!", "side": payload_side}
        if action == "PARTIAL":
            payload["close_pct"] = 50

        resp = _post(client, seed["token_plain"], payload)
        assert resp.status_code == 202, f"spec {spec_no}: {resp.text}"

        sig = _run(_persisted_signal(db_session_maker, uuid.UUID(resp.json()["signal_id"])))
        assert sig.symbol == AUG, (
            f"spec {spec_no}: a {action} for a position entered in {AUG} must carry {AUG}, "
            f"got {sig.symbol!r}. If this is {SEP} the exit was re-resolved across the N=5 "
            "boundary and would miss the open position entirely."
        )
        assert _post_boundary_resolver == [], (
            f"spec {spec_no}: the resolver must not be CALLED for an exit-class action — "
            "pinning is structural, not a lucky match"
        )

    def test_entry_still_rolls_across_the_same_boundary(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _post_boundary_resolver: list[str],
    ) -> None:
        """The other half of the governing sentence, asserted in the same conditions: while
        exits pin, ENTRIES must still roll. A test suite that only proved pinning could be
        satisfied by a resolver that had stopped working altogether."""
        resp = _post(
            client, seed["token_plain"], {"action": "BUY", "symbol": "BSE1!", "quantity": 1}
        )
        assert resp.status_code == 202, resp.text
        sig = _run(_persisted_signal(db_session_maker, uuid.UUID(resp.json()["signal_id"])))
        assert sig.symbol == SEP, "an ENTRY after the boundary must take the next month"
        assert _post_boundary_resolver == ["BSE1!"]


# ════════════════════════════════════════════════════════════════════════
# Test 12 — the pinning regression, asserted directly (strategy_webhook.py:399-424)
# ════════════════════════════════════════════════════════════════════════
class TestPinningRegression:
    """Spec 12. Pins the MECHANISM itself, not just its effect, so a refactor that removes the
    pinning is caught even if some other layer happens to mask it."""

    def test_stored_symbol_overrides_whatever_the_payload_carried(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _post_boundary_resolver: list[str],
    ) -> None:
        """Even when the payload NAMES the wrong contract explicitly, the stored symbol wins.
        This is the case a mis-configured Pine alert produces (the 27-May BSE blocker), now
        crossed with the N=5 switch."""
        _run(_open_position(db_session_maker, seed, symbol=AUG, side="buy"))
        resp = _post(
            client,
            seed["token_plain"],
            {"action": "EXIT", "symbol": SEP, "side": "long"},   # payload insists on SEP
        )
        assert resp.status_code == 202, resp.text
        sig = _run(_persisted_signal(db_session_maker, uuid.UUID(resp.json()["signal_id"])))
        assert sig.symbol == AUG, "the STORED symbol must override an explicit wrong payload"

    def test_exit_with_no_open_position_is_benign_not_an_error(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
        _post_boundary_resolver: list[str],
    ) -> None:
        """The else-branch of the same block. A duplicate or already-closed exit must NOT 500
        and must NOT be re-resolved into a next-month order — it is logged and ignored. This is
        also what absorbs a stale exit after a manual close (RECOVERY A2)."""
        resp = _post(
            client, seed["token_plain"], {"action": "EXIT", "symbol": "BSE1!", "side": "long"}
        )
        assert resp.status_code == 202, resp.text
        sig = _run(_persisted_signal(db_session_maker, uuid.UUID(resp.json()["signal_id"])))
        assert sig.symbol == "BSE1!", (
            "with no open position the symbol is left UN-re-resolved; turning it into "
            f"{SEP} here would invent a next-month order out of a benign duplicate"
        )
        assert _post_boundary_resolver == [], "still no resolver call on an exit-class action"

    def test_pinning_applies_to_every_exit_action_and_no_entry_action(self) -> None:
        """The action set itself is load-bearing: adding an exit-class action without adding it
        here would silently give that action the ENTRY path's re-resolution."""
        from app.api.strategy_webhook import _DIRECT_EXIT_ACTIONS, _ENTRY_ACTIONS

        assert _DIRECT_EXIT_ACTIONS == frozenset({"PARTIAL", "EXIT", "SL_HIT"})
        assert not (_DIRECT_EXIT_ACTIONS & _ENTRY_ACTIONS), (
            "an action that is both entry- and exit-class would be re-resolved AND pinned"
        )
