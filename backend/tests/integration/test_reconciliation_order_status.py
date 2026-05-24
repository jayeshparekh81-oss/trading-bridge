"""Tests for the reconciliation order-status poll + write-back pass.

Incident 2026-05-20: live entry order ``222260520454106`` sat in Dhan
TRANSIT/pending and was never reconciled, because the loop only diffed
open-position *sets* and never read ``strategy_executions`` or polled order
status. ``_reconcile_order_status`` closes that gap. These tests drive the
public ``reconcile_once`` seam against a fake broker.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_signal import StrategySignal
from app.schemas.broker import OrderStatus
from app.workers.reconciliation_loop import reconcile_once
from tests.integration.conftest import _seed_user_with_strategy

pytestmark = pytest.mark.asyncio


async def _seed_live_pending_execution(
    maker: async_sessionmaker[AsyncSession],
    *,
    broker_order_id: str = "TEST-ORDER-1",
    placed_age_hours: float = 1.0,
    broker_status: str | None = None,
) -> dict[str, Any]:
    """Seed user + Dhan cred + LIVE strategy + ENTRY signal + a non-terminal
    entry execution leg. Returns the seed id dict plus signal/execution ids."""
    seed = await _seed_user_with_strategy(maker, email=f"recon-{uuid4().hex[:8]}@t.com")
    async with maker() as s:
        strat = await s.get(Strategy, seed["strategy_id"])
        # _list_credentials_backing_live_strategies requires a LIVE strategy.
        strat.is_paper = False
        sig = StrategySignal(
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            raw_payload={},
            symbol="BSE-MAY2026-FUT",
            action="ENTRY",
            status="executed",
        )
        s.add(sig)
        await s.flush()
        ex = StrategyExecution(
            signal_id=sig.id,
            broker_credential_id=seed["credential_id"],
            leg_number=1,
            leg_role="entry",
            symbol="BSE-MAY2026-FUT",
            side="buy",
            quantity=375,
            order_type="MARKET",
            broker_order_id=broker_order_id,
            broker_status=broker_status,
            broker_response={"raw": {"orderStatus": "TRANSIT"}, "status": "pending"},
            placed_at=datetime.now(UTC) - timedelta(hours=placed_age_hours),
            completed_at=None,
        )
        s.add(ex)
        await s.commit()
        seed["signal_id"] = sig.id
        seed["execution_id"] = ex.id
    return seed


def _install_order_broker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    detail: dict[str, Any] | None = None,
    raises: Exception | None = None,
) -> None:
    """Wire a fake broker whose ``get_order_detail`` returns ``detail`` (or
    raises ``raises``). ``get_positions`` returns [] so the position-set
    diff contributes nothing."""

    class _Broker:
        def __init__(self, _creds: Any) -> None:
            pass

        async def is_session_valid(self) -> bool:
            return True

        async def login(self) -> bool:
            return True

        async def get_positions(self) -> list[Any]:
            return []

        async def get_order_detail(self, broker_order_id: str) -> dict[str, Any]:
            if raises is not None:
                raise raises
            assert detail is not None
            return detail

    monkeypatch.setattr("app.brokers.registry.get_broker_class", lambda _name: _Broker)


class TestReconcileOrderStatus:
    async def test_transit_polled_to_complete_writes_back(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        seed = await _seed_live_pending_execution(db_session_maker)
        _install_order_broker(
            monkeypatch,
            detail={
                "status": OrderStatus.COMPLETE,
                "filled_qty": 375,
                "avg_price": Decimal("2350.5"),
                "raw": {"orderStatus": "TRADED"},
            },
        )

        async with db_session_maker() as s:
            drift = await reconcile_once(s)

        assert drift == 0  # COMPLETE is normal progress, not operator drift
        async with db_session_maker() as s:
            ex = await s.get(StrategyExecution, seed["execution_id"])
        assert ex is not None
        assert ex.broker_status == OrderStatus.COMPLETE.value
        assert ex.completed_at is not None
        assert ex.price == Decimal("2350.5")
        assert ex.broker_response.get("filled_qty") == 375

    async def test_transit_polled_to_rejected_marks_failed(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        seed = await _seed_live_pending_execution(db_session_maker)
        _install_order_broker(
            monkeypatch,
            detail={
                "status": OrderStatus.REJECTED,
                "filled_qty": None,
                "avg_price": None,
                "raw": {"orderStatus": "REJECTED"},
            },
        )

        async with db_session_maker() as s:
            drift = await reconcile_once(s)

        assert drift == 1  # REJECTED is drift the operator should see
        async with db_session_maker() as s:
            ex = await s.get(StrategyExecution, seed["execution_id"])
        assert ex is not None
        assert ex.broker_status == OrderStatus.REJECTED.value
        assert ex.error_code == "BROKER_NOT_FILLED"
        assert ex.completed_at is not None

    async def test_transit_still_pending_no_writeback(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        seed = await _seed_live_pending_execution(db_session_maker)
        _install_order_broker(
            monkeypatch,
            detail={
                "status": OrderStatus.PENDING,
                "filled_qty": None,
                "avg_price": None,
                "raw": {"orderStatus": "TRANSIT"},
            },
        )

        async with db_session_maker() as s:
            drift = await reconcile_once(s)

        assert drift == 0
        async with db_session_maker() as s:
            ex = await s.get(StrategyExecution, seed["execution_id"])
        assert ex is not None
        assert ex.broker_status is None  # still in flight — untouched
        assert ex.completed_at is None

    async def test_network_error_is_graceful(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.core.exceptions import BrokerConnectionError

        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        seed = await _seed_live_pending_execution(db_session_maker)
        _install_order_broker(
            monkeypatch,
            raises=BrokerConnectionError("simulated outage", broker_name="dhan"),
        )

        async with db_session_maker() as s:
            drift = await reconcile_once(s)  # must NOT raise

        assert drift == 0
        async with db_session_maker() as s:
            ex = await s.get(StrategyExecution, seed["execution_id"])
        assert ex is not None
        assert ex.broker_status is None  # untouched on broker failure
        assert ex.completed_at is None

    async def test_old_execution_excluded_by_age_cutoff(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The 24h bound keeps long-stuck historical rows (the 2026-05-20
        phantom) out of scope — they must NOT be silently mutated."""
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        seed = await _seed_live_pending_execution(db_session_maker, placed_age_hours=96.0)
        _install_order_broker(
            monkeypatch,
            detail={
                "status": OrderStatus.COMPLETE,
                "filled_qty": 375,
                "avg_price": Decimal("2350.5"),
                "raw": {},
            },
        )

        async with db_session_maker() as s:
            drift = await reconcile_once(s)

        assert drift == 0
        async with db_session_maker() as s:
            ex = await s.get(StrategyExecution, seed["execution_id"])
        assert ex is not None
        assert ex.broker_status is None  # too old → never polled/mutated
        assert ex.completed_at is None
