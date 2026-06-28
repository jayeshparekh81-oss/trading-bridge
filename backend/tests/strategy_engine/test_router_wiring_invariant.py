"""Router-wiring SAFETY INVARIANT — futures fall-through must stay unchanged.

FUTURES strategies (``strategy_json IS NULL`` — the live BSE/CDSL/ANGELONE
case) MUST reach the existing executor unchanged after router-wiring. This
test guards that the router's futures branch is byte-for-byte the current
behavior:

  * ENTRY seam  (``_process_entry``)        → ``place_strategy_orders``
  * EXIT  seam  (``_process_direct_exit``)  → ``direct_exit.execute_partial``
                                              / ``direct_exit.execute_exit``

Written BEFORE the router exists (Module #2). With no router yet, these calls
happen directly, so the test PASSES NOW. After the router branch is added, the
futures branch MUST still produce these exact calls (same function, same args)
— a failure here means the wiring changed live-money behavior.

Approach: drive the two worker functions with a lightweight fake async session
and mocked executors (DB-light, no Celery/Redis). This guards the real call
sites — preferred over a unit test of the future branch predicate alone.
"""

from __future__ import annotations

from contextlib import ExitStack
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.schemas.ai_decision import AIDecisionStatus
from app.tasks.signal_execution import (
    ACTION_EXIT,
    ACTION_PARTIAL,
    ACTION_SL_HIT,
    _process_direct_exit,
    _process_entry,
)

_SIGNAL_ID = "11111111-1111-1111-1111-111111111111"
_STRATEGY_ID = "22222222-2222-2222-2222-222222222222"
_USER_ID = "33333333-3333-3333-3333-333333333333"


class _FakeSession:
    """Minimal async-session stand-in: an async context manager whose
    ``get(Model, id)`` returns our signal/strategy by model name."""

    def __init__(self, sig: object, strategy: object) -> None:
        self._sig = sig
        self._strategy = strategy
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def get(self, model: object, _pk: object) -> object | None:
        name = getattr(model, "__name__", "")
        if name == "StrategySignal":
            return self._sig
        if name == "Strategy":
            return self._strategy
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _futures_strategy() -> SimpleNamespace:
    """A FUTURES strategy stand-in — ``strategy_json=None`` mirrors the live
    BSE/CDSL/ANGELONE rows (strategy_json IS NULL)."""
    return SimpleNamespace(
        id=UUID(_STRATEGY_ID),
        name="BSE LTD Futures",
        is_active=True,
        is_paper=False,
        strategy_json=None,  # ← the live-futures discriminator
        entry_lots=2,
        ai_validation_enabled=True,
    )


def _entry_signal() -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID(_SIGNAL_ID),
        strategy_id=UUID(_STRATEGY_ID),
        user_id=UUID(_USER_ID),
        raw_payload={"side": "long"},
        symbol="BSE-JUN2026-FUT",
        action="ENTRY",
        quantity=750,
        status="received",
        notes=None,
        ai_decision=None,
        ai_reasoning=None,
        ai_confidence=None,
        validated_at=None,
        processed_at=None,
    )


def _exit_signal() -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID(_SIGNAL_ID),
        strategy_id=UUID(_STRATEGY_ID),
        user_id=UUID(_USER_ID),
        raw_payload={"side": "long", "closePct": 50},
        symbol="BSE-JUN2026-FUT",
        action="EXIT",
        quantity=750,
        status="received",
        notes=None,
        processed_at=None,
    )


def _approved_decision() -> SimpleNamespace:
    return SimpleNamespace(
        decision=AIDecisionStatus.APPROVED,
        reasoning="test-approved",
        confidence=Decimal("0.80"),
        recommended_lots=2,
    )


def _exec_result() -> SimpleNamespace:
    return SimpleNamespace(
        position_id="pos-1",
        broker_order_id="ord-1",
        broker_status="complete",
        paper_mode=False,
    )


_EXIT_RESULT = {
    "status": "executed",
    "close_qty": 2,
    "remaining": 0,
    "position_status": "closed",
    "broker_order_id": "exit-ord-1",
}


# ───────────────────────── ENTRY seam ─────────────────────────


async def test_entry_futures_calls_place_strategy_orders_unchanged() -> None:
    """ENTRY seam: a futures strategy must reach ``place_strategy_orders``
    once, with ``signal=sig`` and ``strategy=strategy`` (the current,
    NFO/NRML futures path). The router's futures branch must reproduce this
    call exactly."""
    sig = _entry_signal()
    strategy = _futures_strategy()
    session = _FakeSession(sig, strategy)
    place_mock = AsyncMock(return_value=_exec_result())
    kill_switch = MagicMock()
    kill_switch.increment_daily_trades = AsyncMock()
    kill_switch.check_and_trigger = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.db.session.get_sessionmaker",
                return_value=MagicMock(return_value=session),
            )
        )
        stack.enter_context(
            patch(
                "app.services.ai_validator.validate_signal",
                AsyncMock(return_value=_approved_decision()),
            )
        )
        stack.enter_context(
            patch(
                "app.services.strategy_executor.place_strategy_orders",
                place_mock,
            )
        )
        # Advisory shields are flag-gated; force OFF so the entry path goes
        # straight to the executor regardless of env/config defaults.
        stack.enter_context(
            patch("app.services.anomaly_shield_service.is_enabled", return_value=False)
        )
        stack.enter_context(
            patch("app.services.trade_dna_service.is_enabled", return_value=False)
        )
        stack.enter_context(
            patch("app.services.probability_engine.is_enabled", return_value=False)
        )
        stack.enter_context(
            patch("app.services.telegram_alerts.send_alert", AsyncMock())
        )
        stack.enter_context(
            patch(
                "app.services.kill_switch_service.kill_switch_service",
                kill_switch,
            )
        )
        await _process_entry(_SIGNAL_ID)

    place_mock.assert_awaited_once()
    call = place_mock.await_args
    # session is the first positional arg; signal/strategy are keyword args.
    assert call.args and call.args[0] is session
    assert call.kwargs["signal"] is sig
    assert call.kwargs["strategy"] is strategy
    assert call.kwargs.get("recommended_lots") == 2


# ───────────────────────── EXIT seam ─────────────────────────


@pytest.mark.parametrize(
    "action_kind, called, not_called, extra_kwargs",
    [
        (ACTION_PARTIAL, "partial", "exit", {}),
        (ACTION_EXIT, "exit", "partial", {"leg_role": "direct_exit"}),
        (ACTION_SL_HIT, "exit", "partial", {"leg_role": "direct_sl"}),
    ],
)
async def test_exit_futures_calls_direct_exit_unchanged(
    action_kind: str, called: str, not_called: str, extra_kwargs: dict[str, str]
) -> None:
    """EXIT seam: a futures strategy must reach the existing direct-exit
    handler unchanged — PARTIAL → ``execute_partial``; EXIT/SL_HIT →
    ``execute_exit`` (with the right ``leg_role``) — each with
    ``signal=sig`` and ``strategy=strategy``. The other handler must NOT be
    called. The router's futures branch must reproduce these calls exactly."""
    sig = _exit_signal()
    strategy = _futures_strategy()
    session = _FakeSession(sig, strategy)
    partial_mock = AsyncMock(return_value=dict(_EXIT_RESULT))
    exit_mock = AsyncMock(return_value=dict(_EXIT_RESULT))

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.db.session.get_sessionmaker",
                return_value=MagicMock(return_value=session),
            )
        )
        stack.enter_context(
            patch("app.services.direct_exit.execute_partial", partial_mock)
        )
        stack.enter_context(
            patch("app.services.direct_exit.execute_exit", exit_mock)
        )
        stack.enter_context(
            patch("app.services.telegram_alerts.send_alert", AsyncMock())
        )
        await _process_direct_exit(_SIGNAL_ID, action_kind)

    fn = partial_mock if called == "partial" else exit_mock
    other = exit_mock if not_called == "exit" else partial_mock

    fn.assert_awaited_once()
    other.assert_not_awaited()
    call = fn.await_args
    assert call.args and call.args[0] is session
    assert call.kwargs["signal"] is sig
    assert call.kwargs["strategy"] is strategy
    for key, value in extra_kwargs.items():
        assert call.kwargs.get(key) == value
