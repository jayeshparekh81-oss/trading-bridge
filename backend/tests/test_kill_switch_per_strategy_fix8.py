"""Fix #8 — Kill switch per-strategy paper resolution + MARGIN close leg.

See /tmp/8_KILL_SWITCH.md.

Pre-fix bugs:
  A. Line 596 read ``settings.strategy_paper_mode`` (global) and
     short-circuited the broker close path for ALL positions. In
     mixed-mode (global paper, BSE LTD live per migration 027) this
     would mark the real Dhan position closed in DB while leaving
     it OPEN at the broker — silent safety regression.
  B. Line 743 hardcoded ``product_type=ProductType.INTRADAY`` on the
     close leg. A MARGIN position would be (wrongly) closed as if
     opening a NEW intraday short, leaving the carry-forward leg
     untouched. Violates permanent rule 1 (/tmp/PERMANENT_RULES.md).

Fix:
  A. Bucket positions into paper/live via
     ``paper_mode_resolver.resolve_paper_mode(strategy)`` per position.
     Mixed trips produce mixed actions.
  B. Close leg now uses ``ProductType.MARGIN``.

Tests below use the same in-memory aiosqlite pattern as
``test_reconciliation_per_strategy_fix7.py``, independent of any
broken fixture.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.brokers.base import BrokerInterface
from app.core import redis_client
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.kill_switch import KillSwitchConfig
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.user import User
from app.schemas.broker import (
    BrokerName,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderType,
    ProductType,
)
from app.services.kill_switch_service import KillSwitchService


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    yield client
    await client.aclose()


async def _seed(
    db: AsyncSession,
    *,
    live: bool,
    extra_paper_position: bool = False,
) -> dict[str, Any]:
    """One user, one credential, one or two strategies (live + maybe paper),
    one open position per strategy."""
    user = User(email="kill-test@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()
    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SECRET"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred)
    await db.flush()
    config = KillSwitchConfig(
        user_id=user.id,
        max_daily_loss_inr=Decimal("5000"),
        max_daily_trades=10,
        enabled=True,
        auto_square_off=True,
    )
    db.add(config)
    strat_live = Strategy(
        user_id=user.id,
        name="live-strat",
        broker_credential_id=cred.id,
        entry_lots=1,
        partial_profit_lots=0,
        trail_lots=0,
        allowed_symbols=["NIFTY"],
        ai_validation_enabled=False,
        is_active=True,
        is_paper=not live,
    )
    db.add(strat_live)
    await db.flush()
    db.add(
        StrategyPosition(
            user_id=user.id,
            strategy_id=strat_live.id,
            broker_credential_id=cred.id,
            symbol="NIFTY25MAY-FUT",
            side="buy",
            total_quantity=75,
            remaining_quantity=75,
            avg_entry_price=Decimal("22500.0"),
            status="open",
        )
    )
    out: dict[str, Any] = {
        "user": user,
        "cred": cred,
        "strat_live": strat_live,
    }

    if extra_paper_position:
        strat_paper = Strategy(
            user_id=user.id,
            name="paper-strat",
            broker_credential_id=cred.id,
            entry_lots=1,
            partial_profit_lots=0,
            trail_lots=0,
            allowed_symbols=["BANKNIFTY"],
            ai_validation_enabled=False,
            is_active=True,
            is_paper=True,
        )
        db.add(strat_paper)
        await db.flush()
        db.add(
            StrategyPosition(
                user_id=user.id,
                strategy_id=strat_paper.id,
                broker_credential_id=cred.id,
                symbol="BANKNIFTY25MAY-FUT",
                side="sell",
                total_quantity=15,
                remaining_quantity=15,
                avg_entry_price=Decimal("48000.0"),
                status="open",
            )
        )
        out["strat_paper"] = strat_paper

    await db.commit()
    return out


class _FakeBroker:
    """Minimal stand-in — records place_order calls so tests can assert."""

    broker_name = MagicMock()
    broker_name.value = "dhan"

    def __init__(self) -> None:
        self.place_order_calls: list[OrderRequest] = []
        self.login_called = False

    async def is_session_valid(self) -> bool:
        return True

    async def login(self) -> bool:
        self.login_called = True
        return True

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        self.place_order_calls.append(order)
        return OrderResponse(
            broker_order_id="KS-OK-1",
            status=OrderStatus.COMPLETE,
            message="filled",
            raw_response={},
        )


def _broker_factory(broker: _FakeBroker) -> Any:
    def _factory(_creds: Any) -> Any:
        return broker

    return _factory


# ═══════════════════════════════════════════════════════════════════════
# Bug A — per-strategy bucketing
# ═══════════════════════════════════════════════════════════════════════


async def test_kill_switch_calls_broker_for_live_strategy_in_mixed_global_paper(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact May-20 scenario: global STRATEGY_PAPER_MODE=true,
    one strategy is_paper=False. Kill switch must call the broker.
    Pre-Fix #8 the global flag silently routed the live position to
    the synthetic close path → real money exposure stayed open."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    from app.core.config import get_settings as _gs

    _gs.cache_clear()

    seeded = await _seed(db, live=True)
    broker = _FakeBroker()
    await redis_client.set_daily_pnl(seeded["user"].id, Decimal("-6000"))

    svc = KillSwitchService()
    result = await svc.check_and_trigger(
        seeded["user"].id,
        db,
        broker_factory=_broker_factory(broker),
    )

    assert result.triggered is True
    assert len(broker.place_order_calls) == 1
    # Bug B regression — close leg is MARGIN, not INTRADAY.
    assert broker.place_order_calls[0].product_type is ProductType.MARGIN


async def test_kill_switch_does_not_call_broker_for_paper_strategy(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-strategy is_paper=True → synthetic close, no broker call,
    regardless of global flag."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    from app.core.config import get_settings as _gs

    _gs.cache_clear()

    seeded = await _seed(db, live=False)
    broker = _FakeBroker()
    await redis_client.set_daily_pnl(seeded["user"].id, Decimal("-6000"))

    svc = KillSwitchService()
    result = await svc.check_and_trigger(
        seeded["user"].id,
        db,
        broker_factory=_broker_factory(broker),
    )

    assert result.triggered is True
    assert broker.place_order_calls == []  # synthetic close only
    assert broker.login_called is False
    # Action log still reports the synthetic close happened.
    assert len(result.actions) == 1
    assert result.actions[0].positions_squared_off == 1


async def test_kill_switch_handles_mixed_paper_and_live(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One credential, two strategies (one paper + one live). Kill
    switch fires → exactly ONE broker call (for the live position) and
    ONE synthetic close (for the paper position). Both reported in
    actions."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    from app.core.config import get_settings as _gs

    _gs.cache_clear()

    seeded = await _seed(db, live=True, extra_paper_position=True)
    broker = _FakeBroker()
    await redis_client.set_daily_pnl(seeded["user"].id, Decimal("-6000"))

    svc = KillSwitchService()
    result = await svc.check_and_trigger(
        seeded["user"].id,
        db,
        broker_factory=_broker_factory(broker),
    )

    assert result.triggered is True
    # ONE broker call — the live position. The paper position is closed
    # synthetically.
    assert len(broker.place_order_calls) == 1
    assert broker.place_order_calls[0].symbol == "NIFTY25MAY-FUT"

    # Two action logs total (paper bucket + live bucket).
    assert len(result.actions) == 2
    paper_actions = [a for a in result.actions if a.positions_squared_off >= 1]
    assert sum(a.positions_squared_off for a in paper_actions) == 2


# ═══════════════════════════════════════════════════════════════════════
# Bug B — MARGIN close leg (also asserted in mixed test above)
# ═══════════════════════════════════════════════════════════════════════


async def test_kill_switch_live_close_leg_uses_margin(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-fix asserted product_type=INTRADAY on close leg; that has
    been changed to MARGIN per permanent rule 1.  Regression test
    against accidental revert."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    from app.core.config import get_settings as _gs

    _gs.cache_clear()

    seeded = await _seed(db, live=True)
    broker = _FakeBroker()
    await redis_client.set_daily_pnl(seeded["user"].id, Decimal("-6000"))

    svc = KillSwitchService()
    await svc.check_and_trigger(
        seeded["user"].id,
        db,
        broker_factory=_broker_factory(broker),
    )

    assert len(broker.place_order_calls) == 1
    order = broker.place_order_calls[0]
    assert order.product_type is ProductType.MARGIN, (
        "Permanent rule 1: F&O close leg must be MARGIN, not INTRADAY. "
        f"Got {order.product_type.value}."
    )
