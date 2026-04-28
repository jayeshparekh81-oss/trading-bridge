"""Strategy execution engine — unit tests.

Covers the four moving parts that don't need a full FastAPI TestClient:

    * AI validator         — mocked Anthropic SDK, both APPROVE and REJECT.
    * Strategy executor    — paper mode end-to-end, position row opened
                             with computed target/SL/trail levels.
    * Position manager     — apply_tick covers partial profit, trailing
                             SL, and hard SL transitions.
    * Kill-switch helper   — close_position_now writes a closing
                             execution and marks the row closed.

The webhook endpoint test (HMAC, time-of-day, quantity ceiling) is the
day-1 follow-up — the helper functions it depends on are unit-tested
here so the integration test can stay thin.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Disable strategy-paper mode env-var for live tests; default True.
os.environ.setdefault("STRATEGY_PAPER_MODE", "true")

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.schemas.ai_decision import AIDecisionStatus
from app.schemas.broker import BrokerName, OrderSide
from app.services.ai_validator import validate_signal
from app.services.position_manager import apply_tick, close_position_now
from app.services.strategy_executor import (
    QUANTITY_CEILING,
    StrategyExecutorError,
    place_strategy_orders,
)

# ═══════════════════════════════════════════════════════════════════════
# Fixtures — sqlite in-memory + seeded user/cred/strategy
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory aiosqlite DB with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db: AsyncSession) -> dict[str, Any]:
    """User + active broker credential + strategy with risk config."""
    user = User(email="trader@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()

    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.FYERS,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SECRET"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred)
    await db.flush()

    strategy = Strategy(
        user_id=user.id,
        name="test-strat",
        broker_credential_id=cred.id,
        entry_lots=4,
        partial_profit_lots=2,
        partial_profit_target_pct=Decimal("1.000"),  # +1%
        trail_lots=2,
        trail_offset_pct=Decimal("0.500"),  # 0.5%
        hard_sl_pct=Decimal("1.000"),  # -1%
        ai_validation_enabled=False,  # bypass validator in executor tests
        is_active=True,
    )
    db.add(strategy)
    await db.flush()

    signal = StrategySignal(
        user_id=user.id,
        strategy_id=strategy.id,
        raw_payload={"price": "100"},
        symbol="NIFTY24500CE",
        action="BUY",
        quantity=4,
        order_type="market",
        status="received",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    await db.refresh(strategy)
    await db.refresh(cred)

    return {
        "user_id": user.id,
        "credential_id": cred.id,
        "strategy": strategy,
        "signal": signal,
    }


# ═══════════════════════════════════════════════════════════════════════
# AI validator
# ═══════════════════════════════════════════════════════════════════════


def _fake_anthropic_client(payload: dict[str, Any]) -> MagicMock:
    """Build a MagicMock that mimics ``anthropic.AsyncAnthropic``."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = (
        f'{{"decision": "{payload["decision"]}", '
        f'"reasoning": "{payload["reasoning"]}", '
        f'"confidence": {payload["confidence"]}}}'
    )
    response = MagicMock()
    response.content = [text_block]

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_ai_validator_bypass_when_disabled(seeded: dict[str, Any]) -> None:
    """ai_validation_enabled=False short-circuits without an API call."""
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], client=None
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert decision.confidence == Decimal("1.000")


@pytest.mark.asyncio
async def test_ai_validator_approve(seeded: dict[str, Any], monkeypatch) -> None:
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()

    client = _fake_anthropic_client(
        {"decision": "APPROVED", "reasoning": "all clear", "confidence": 0.85}
    )
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], client=client
    )
    assert decision.decision is AIDecisionStatus.APPROVED
    assert "all clear" in decision.reasoning
    assert decision.confidence == Decimal("0.85")


@pytest.mark.asyncio
async def test_ai_validator_reject(seeded: dict[str, Any], monkeypatch) -> None:
    seeded["strategy"].ai_validation_enabled = True
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()

    client = _fake_anthropic_client(
        {"decision": "REJECTED", "reasoning": "spam", "confidence": 0.9}
    )
    decision = await validate_signal(
        seeded["signal"], seeded["strategy"], client=client
    )
    assert decision.decision is AIDecisionStatus.REJECTED


# ═══════════════════════════════════════════════════════════════════════
# Strategy executor — paper mode
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_executor_paper_mode_opens_position(
    db: AsyncSession, seeded: dict[str, Any], monkeypatch
) -> None:
    """Paper mode writes 4 entry rows and one position with computed levels."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    result = await place_strategy_orders(
        db, signal=seeded["signal"], strategy=seeded["strategy"]
    )
    await db.commit()

    assert result.success
    assert result.paper_mode is True
    assert len(result.execution_ids) == 4

    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    assert pos.status == "open"
    assert pos.total_quantity == 4
    assert pos.remaining_quantity == 4
    # avg=100, +1% target = 101, -1% SL = 99, 0.5% trail offset = 0.50
    assert pos.avg_entry_price == Decimal("100")
    assert pos.target_price == Decimal("101.000")
    assert pos.stop_loss_price == Decimal("99.000")
    assert pos.trail_offset == Decimal("0.500")


@pytest.mark.asyncio
async def test_executor_rejects_quantity_above_ceiling(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """Day-1 ceiling: anything > 4 lots is rejected."""
    seeded["signal"].quantity = QUANTITY_CEILING + 1
    with pytest.raises(StrategyExecutorError):
        await place_strategy_orders(
            db, signal=seeded["signal"], strategy=seeded["strategy"]
        )


@pytest.mark.asyncio
async def test_executor_rejects_unsupported_action(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """EXIT is owned by the position manager, not the executor."""
    seeded["signal"].action = "EXIT"
    with pytest.raises(StrategyExecutorError):
        await place_strategy_orders(
            db, signal=seeded["signal"], strategy=seeded["strategy"]
        )


# ═══════════════════════════════════════════════════════════════════════
# Position manager — state transitions
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def open_position(db: AsyncSession, seeded: dict[str, Any]) -> StrategyPosition:
    """Long position: entry 100, target 101, SL 99, trail 0.5."""
    monkeypatch_paper = "true"
    os.environ["STRATEGY_PAPER_MODE"] = monkeypatch_paper
    get_settings.cache_clear()

    result = await place_strategy_orders(
        db, signal=seeded["signal"], strategy=seeded["strategy"]
    )
    await db.commit()
    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    return pos


@pytest.mark.asyncio
async def test_apply_tick_books_partial_profit(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """LTP at target → 2 lots booked partial, status=partial."""
    outcome = await apply_tick(db, position=open_position, ltp=Decimal("101"))
    await db.commit()

    assert "partial_target" in outcome.triggered
    assert open_position.remaining_quantity == 2
    assert open_position.status == "partial"


@pytest.mark.asyncio
async def test_apply_tick_hits_hard_sl_closes_all(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """LTP at hard SL → entire position closed, no partial."""
    outcome = await apply_tick(db, position=open_position, ltp=Decimal("99"))
    await db.commit()

    assert "hard_sl" in outcome.triggered
    assert open_position.remaining_quantity == 0
    assert open_position.status == "closed"
    assert outcome.closed is True


@pytest.mark.asyncio
async def test_apply_tick_trailing_sl_after_high(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """Walk price up to 102, then back to 101.4 → trail (102-0.5=101.5) breached."""
    # First tick: drives partial profit at 101
    await apply_tick(db, position=open_position, ltp=Decimal("101"))
    # Push higher to 102 — updates highest_price_seen
    await apply_tick(db, position=open_position, ltp=Decimal("102"))
    # Pullback to 101.4 — breaches trail (102 - 0.5)
    outcome = await apply_tick(db, position=open_position, ltp=Decimal("101.4"))
    await db.commit()

    assert "trailing_sl" in outcome.triggered
    assert open_position.remaining_quantity == 0
    assert open_position.status == "closed"


# ═══════════════════════════════════════════════════════════════════════
# Kill switch
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_close_position_now_writes_exit_and_marks_closed(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """Force-close path: one exit row, status=closed, remaining=0."""
    starting_qty = open_position.remaining_quantity
    exit_row = await close_position_now(
        db, position=open_position, reason="kill_switch", ltp=Decimal("100.5")
    )
    await db.commit()

    assert exit_row.quantity == starting_qty
    assert exit_row.leg_role == "kill_switch"
    assert exit_row.side == OrderSide.SELL.value  # opposite of long entry
    assert open_position.status == "closed"
    assert open_position.remaining_quantity == 0


@pytest.mark.asyncio
async def test_close_position_now_idempotent_when_already_closed(
    db: AsyncSession, open_position: StrategyPosition
) -> None:
    """Calling close on an already-closed position is a no-op."""
    open_position.remaining_quantity = 0
    open_position.status = "closed"
    await db.commit()

    exit_row = await close_position_now(
        db, position=open_position, reason="kill_switch"
    )
    # No new row should be flushed; the returned object has quantity=0
    assert exit_row.quantity == 0
