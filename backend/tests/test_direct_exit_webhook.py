"""Direct-exit refactor tests — Pine-driven ENTRY/PARTIAL/EXIT/SL_HIT.

Mostly service-level tests against an in-memory aiosqlite DB (matches the
:mod:`tests.test_strategy_engine` pattern). Schema-only tests run without
the DB. The single idempotency test verifies the webhook hash helper —
the Redis SET-NX dedup is exercised by the integration suite already.

Coverage of the user's 15 requested tests + 1 bonus SL_HIT test.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio

# Set BEFORE app imports so get_settings() picks up paper-mode at module load.
os.environ.setdefault("STRATEGY_PAPER_MODE", "true")

from pydantic import ValidationError
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
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.schemas.broker import BrokerName
from app.schemas.strategy_webhook import (
    PositionSide,
    StrategyAction,
    StrategyWebhookPayload,
)
from app.services import direct_exit, position_manager
from app.services.strategy_executor import place_strategy_orders


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
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
async def seeded_direct_exit(db: AsyncSession) -> dict[str, Any]:
    """User + active broker credential + DIRECT_EXIT strategy.

    Strategy levels (target/SL/trail) intentionally NULL — Pine drives
    exits in this strategy class, so the position loop's autonomous math
    must not run.
    """
    user = User(email="direct-trader@example.com", password_hash="x", is_active=True)
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

    strategy = Strategy(
        user_id=user.id,
        name="bse-direct-exit",
        broker_credential_id=cred.id,
        entry_lots=4,  # ceiling 4 lots × lot_size = enough headroom for 750-1500
        partial_profit_lots=2,  # required by even-lot validator (entry must be even lots)
        ai_validation_enabled=False,
        is_active=True,
        exit_strategy_type="direct_exit",
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return {"user_id": user.id, "credential_id": cred.id, "strategy": strategy}


def _build_signal(
    *,
    seeded: dict[str, Any],
    action: str,
    side: str = "long",
    quantity: int | None = None,
    close_pct: float | None = None,
    symbol: str = "BSE-MAY2026-FUT",
    price: float = 3800.0,
    lot_size_hint: int = 375,
    signal_id_suffix: str = "",
) -> StrategySignal:
    """Build a StrategySignal row mirroring what the webhook would persist."""
    payload: dict[str, Any] = {
        "action": action,
        "side": side,
        "symbol": symbol,
        "price": price,
        "lot_size_hint": lot_size_hint,
        "signal_id": f"test_{action.lower()}_{signal_id_suffix or uuid.uuid4().hex[:8]}",
    }
    if quantity is not None:
        payload["quantity"] = quantity
    if close_pct is not None:
        payload["closePct"] = close_pct
    return StrategySignal(
        user_id=seeded["user_id"],
        strategy_id=seeded["strategy"].id,
        raw_payload=payload,
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type="market",
        status="received",
    )


async def _seed_open_position(
    db: AsyncSession,
    seeded: dict[str, Any],
    *,
    quantity: int = 750,
    side: str = "long",
) -> StrategyPosition:
    """Insert a baseline open position by running place_strategy_orders."""
    os.environ["STRATEGY_PAPER_MODE"] = "true"
    get_settings.cache_clear()

    entry_sig = _build_signal(
        seeded=seeded,
        action="ENTRY",
        side=side,
        quantity=quantity,
        signal_id_suffix="seed",
    )
    db.add(entry_sig)
    await db.flush()
    result = await place_strategy_orders(
        db, signal=entry_sig, strategy=seeded["strategy"]
    )
    await db.commit()
    pos = await db.get(StrategyPosition, result.position_id)
    assert pos is not None
    return pos


# ═══════════════════════════════════════════════════════════════════════
# 1-3. Pydantic schema — validation rules (no DB)
# ═══════════════════════════════════════════════════════════════════════


def test_buy_alias_treated_as_entry() -> None:
    """BUY/SELL accepted by schema and reported as entry actions."""
    buy = StrategyWebhookPayload.model_validate(
        {"action": "BUY", "symbol": "BSE-MAY2026-FUT", "quantity": 750}
    )
    assert buy.action == StrategyAction.BUY
    assert buy.is_entry()
    assert buy.normalized_side() == PositionSide.LONG

    sell = StrategyWebhookPayload.model_validate(
        {"action": "SELL", "symbol": "BSE-MAY2026-FUT", "quantity": 750}
    )
    assert sell.action == StrategyAction.SELL
    assert sell.is_entry()
    assert sell.normalized_side() == PositionSide.SHORT


def test_partial_action_rejects_close_pct_zero() -> None:
    """closePct must be > 0 — zero is a config bug, not a no-op."""
    with pytest.raises(ValidationError):
        StrategyWebhookPayload.model_validate(
            {
                "action": "PARTIAL",
                "side": "long",
                "symbol": "BSE-MAY2026-FUT",
                "closePct": 0,
            }
        )


def test_partial_action_rejects_close_pct_above_99() -> None:
    """closePct must be <= 99. 100 means EXIT — caller should send EXIT."""
    with pytest.raises(ValidationError):
        StrategyWebhookPayload.model_validate(
            {
                "action": "PARTIAL",
                "side": "long",
                "symbol": "BSE-MAY2026-FUT",
                "closePct": 100,
            }
        )


# ═══════════════════════════════════════════════════════════════════════
# 4. ENTRY → position state
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_entry_action_creates_position_with_full_quantity(
    db: AsyncSession, seeded_direct_exit: dict[str, Any]
) -> None:
    pos = await _seed_open_position(db, seeded_direct_exit, quantity=750)
    assert pos.total_quantity == 750
    assert pos.remaining_quantity == 750
    assert pos.status == "open"
    # Action history records the entry event.
    assert pos.last_action == "entry"
    assert isinstance(pos.action_history, list)
    assert len(pos.action_history) == 1
    assert pos.action_history[0]["action"] == "entry"
    assert pos.action_history[0]["qty"] == 750


# ═══════════════════════════════════════════════════════════════════════
# 5-7. PARTIAL paths
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_partial_action_with_close_pct_50_exits_half(
    db: AsyncSession, seeded_direct_exit: dict[str, Any]
) -> None:
    """750 × 50% = 375 → exactly 1 lot → status='partial', remaining=375."""
    pos = await _seed_open_position(db, seeded_direct_exit, quantity=750)

    sig = _build_signal(
        seeded=seeded_direct_exit,
        action="PARTIAL",
        side="long",
        close_pct=50,
        signal_id_suffix="p1",
    )
    db.add(sig)
    await db.flush()

    result = await direct_exit.execute_partial(
        db, signal=sig, strategy=seeded_direct_exit["strategy"]
    )
    await db.commit()

    assert result["status"] == "executed"
    assert result["close_qty"] == 375
    assert result["remaining"] == 375
    assert result["position_status"] == "partial"

    await db.refresh(pos)
    assert pos.remaining_quantity == 375
    assert pos.status == "partial"
    assert pos.last_action == "partial"
    actions = [h["action"] for h in pos.action_history]
    assert actions == ["entry", "partial"]

    # Audit row written
    from sqlalchemy import select as _sel

    rows = (
        await db.execute(
            _sel(StrategyExecution)
            .where(StrategyExecution.signal_id == sig.id)
            .where(StrategyExecution.leg_role == "direct_partial")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].quantity == 375
    assert rows[0].side == "sell"  # opposite of long


@pytest.mark.asyncio
async def test_partial_action_no_open_position_returns_ignored(
    db: AsyncSession, seeded_direct_exit: dict[str, Any]
) -> None:
    """No prior ENTRY → execute_partial returns ignored without erroring."""
    sig = _build_signal(
        seeded=seeded_direct_exit, action="PARTIAL", side="long", close_pct=50
    )
    db.add(sig)
    await db.flush()
    result = await direct_exit.execute_partial(
        db, signal=sig, strategy=seeded_direct_exit["strategy"]
    )
    assert result["status"] == "ignored"
    assert result["reason"] == "no_open_position"


@pytest.mark.asyncio
async def test_partial_close_qty_rounded_down_to_lot_multiple(
    db: AsyncSession, seeded_direct_exit: dict[str, Any]
) -> None:
    """750 × 33% = 247.5 → floor 247 → 0 lots (lot_size=375). Ignored.

    Mirrors server_final30mar.py's ``_qty_from_open_pct`` semantics:
    never close more than the user asked, lot-floor it.
    """
    await _seed_open_position(db, seeded_direct_exit, quantity=750)
    sig = _build_signal(
        seeded=seeded_direct_exit, action="PARTIAL", side="long", close_pct=33
    )
    db.add(sig)
    await db.flush()
    result = await direct_exit.execute_partial(
        db, signal=sig, strategy=seeded_direct_exit["strategy"]
    )
    assert result["status"] == "ignored"
    assert result["reason"] == "close_qty_below_lot"


# ═══════════════════════════════════════════════════════════════════════
# 8-9. EXIT paths
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_exit_action_closes_full_remaining_quantity(
    db: AsyncSession, seeded_direct_exit: dict[str, Any]
) -> None:
    pos = await _seed_open_position(db, seeded_direct_exit, quantity=750)

    sig = _build_signal(seeded=seeded_direct_exit, action="EXIT", side="long")
    db.add(sig)
    await db.flush()
    result = await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded_direct_exit["strategy"], leg_role="direct_exit"
    )
    await db.commit()

    assert result["status"] == "executed"
    assert result["close_qty"] == 750
    assert result["remaining"] == 0
    assert result["position_status"] == "closed"

    await db.refresh(pos)
    assert pos.remaining_quantity == 0
    assert pos.status == "closed"
    assert pos.last_action == "exit"
    assert pos.exit_reason == "direct_exit"


@pytest.mark.asyncio
async def test_exit_action_no_open_position_returns_ignored(
    db: AsyncSession, seeded_direct_exit: dict[str, Any]
) -> None:
    sig = _build_signal(seeded=seeded_direct_exit, action="EXIT", side="long")
    db.add(sig)
    await db.flush()
    result = await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded_direct_exit["strategy"]
    )
    assert result["status"] == "ignored"
    assert result["reason"] == "no_open_position"


# ═══════════════════════════════════════════════════════════════════════
# 10. Full lifecycle ENTRY → PARTIAL(50%) → EXIT
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_lifecycle_entry_partial_exit_flow_state_transitions(
    db: AsyncSession, seeded_direct_exit: dict[str, Any]
) -> None:
    """Open 2 lots → partial half → exit remaining. Audit chain ordered."""
    pos = await _seed_open_position(db, seeded_direct_exit, quantity=750)
    assert (pos.status, pos.remaining_quantity) == ("open", 750)

    p_sig = _build_signal(
        seeded=seeded_direct_exit,
        action="PARTIAL",
        side="long",
        close_pct=50,
        signal_id_suffix="lc1",
    )
    db.add(p_sig)
    await db.flush()
    await direct_exit.execute_partial(
        db, signal=p_sig, strategy=seeded_direct_exit["strategy"]
    )
    await db.refresh(pos)
    assert (pos.status, pos.remaining_quantity) == ("partial", 375)

    e_sig = _build_signal(
        seeded=seeded_direct_exit,
        action="EXIT",
        side="long",
        signal_id_suffix="lc2",
    )
    db.add(e_sig)
    await db.flush()
    await direct_exit.execute_exit(
        db, signal=e_sig, strategy=seeded_direct_exit["strategy"]
    )
    await db.refresh(pos)
    assert (pos.status, pos.remaining_quantity) == ("closed", 0)

    actions = [h["action"] for h in pos.action_history]
    assert actions == ["entry", "partial", "exit"]


# ═══════════════════════════════════════════════════════════════════════
# 11-12. position_loop conditional skip
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_position_loop_skips_direct_exit_strategy(
    db: AsyncSession,
    seeded_direct_exit: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct-exit strategy → loop logs skipped, processes 0 outcomes."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    await _seed_open_position(db, seeded_direct_exit, quantity=750)

    outcomes = await position_manager.manage_open_positions(db)
    assert outcomes == []  # direct_exit positions are skipped


@pytest.mark.asyncio
async def test_position_loop_runs_for_internal_strategy(
    db: AsyncSession,
    seeded_direct_exit: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same setup but exit_strategy_type='internal' → loop processes."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    # Flip to internal + add levels so apply_tick has triggers to evaluate.
    seeded_direct_exit["strategy"].exit_strategy_type = "internal"
    seeded_direct_exit["strategy"].partial_profit_target_pct = Decimal("1.000")
    seeded_direct_exit["strategy"].hard_sl_pct = Decimal("1.000")
    seeded_direct_exit["strategy"].trail_offset_pct = Decimal("0.500")
    await db.commit()

    await _seed_open_position(db, seeded_direct_exit, quantity=750)

    outcomes = await position_manager.manage_open_positions(db)
    assert len(outcomes) >= 1  # one outcome per processed position


# ═══════════════════════════════════════════════════════════════════════
# 13-14. Telegram alert wiring
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_partial_telegram_alert_format(
    db: AsyncSession,
    seeded_direct_exit: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PARTIAL fires SUCCESS-level Telegram with 📉 emoji + closed/remaining."""
    from app.services import telegram_alerts as alerts_mod

    sent: list[tuple[Any, str]] = []

    async def _capture(level: alerts_mod.AlertLevel, message: str) -> None:
        sent.append((level, message))

    monkeypatch.setattr(alerts_mod, "send_alert", _capture)

    await _seed_open_position(db, seeded_direct_exit, quantity=750)
    sig = _build_signal(
        seeded=seeded_direct_exit,
        action="PARTIAL",
        side="long",
        close_pct=50,
        signal_id_suffix="tg1",
    )
    db.add(sig)
    await db.flush()
    await direct_exit.execute_partial(
        db, signal=sig, strategy=seeded_direct_exit["strategy"]
    )

    assert len(sent) == 1
    level, msg = sent[0]
    assert level is alerts_mod.AlertLevel.SUCCESS
    assert "📉 PARTIAL exit" in msg
    assert "closed=" in msg
    assert "remaining=" in msg
    assert "375" in msg  # closed qty


@pytest.mark.asyncio
async def test_exit_telegram_alert_format(
    db: AsyncSession,
    seeded_direct_exit: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EXIT fires INFO-level Telegram with 🔴 emoji + position closed text."""
    from app.services import telegram_alerts as alerts_mod

    sent: list[tuple[Any, str]] = []

    async def _capture(level: alerts_mod.AlertLevel, message: str) -> None:
        sent.append((level, message))

    monkeypatch.setattr(alerts_mod, "send_alert", _capture)

    await _seed_open_position(db, seeded_direct_exit, quantity=750)
    sig = _build_signal(
        seeded=seeded_direct_exit,
        action="EXIT",
        side="long",
        signal_id_suffix="tg2",
    )
    db.add(sig)
    await db.flush()
    await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded_direct_exit["strategy"], leg_role="direct_exit"
    )

    assert len(sent) == 1
    level, msg = sent[0]
    assert level is alerts_mod.AlertLevel.INFO
    assert "🔴" in msg
    assert "EXIT — position closed" in msg
    assert "750" in msg  # closed full position


@pytest.mark.asyncio
async def test_sl_hit_telegram_alert_format(
    db: AsyncSession,
    seeded_direct_exit: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL_HIT fires WARNING-level Telegram with 🛑 emoji (vs EXIT's 🔴 INFO)."""
    from app.services import telegram_alerts as alerts_mod

    sent: list[tuple[Any, str]] = []

    async def _capture(level: alerts_mod.AlertLevel, message: str) -> None:
        sent.append((level, message))

    monkeypatch.setattr(alerts_mod, "send_alert", _capture)

    await _seed_open_position(db, seeded_direct_exit, quantity=750)
    sig = _build_signal(
        seeded=seeded_direct_exit,
        action="SL_HIT",
        side="long",
        signal_id_suffix="tg3",
    )
    db.add(sig)
    await db.flush()
    await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded_direct_exit["strategy"], leg_role="direct_sl"
    )

    assert len(sent) == 1
    level, msg = sent[0]
    assert level is alerts_mod.AlertLevel.WARNING
    assert "🛑" in msg
    assert "SL_HIT" in msg


# ═══════════════════════════════════════════════════════════════════════
# 15. Idempotency — webhook hash helper
# ═══════════════════════════════════════════════════════════════════════


def test_idempotency_same_signal_id_returns_cached() -> None:
    """Two payloads with identical signal_id produce identical dedup
    hashes — the Redis SET-NX in the webhook handler then suppresses
    the duplicate. This pins the helper's behaviour; the actual Redis
    interaction is exercised in
    :mod:`tests.integration.test_strategy_webhook_idempotency`."""
    from app.api.strategy_webhook import _compute_strategy_signal_hash

    user_id = uuid.uuid4()
    raw_body_1 = b'{"action":"PARTIAL","signal_id":"abc-123"}'
    raw_body_2 = b'{"action":"PARTIAL","signal_id":"abc-123","extra":"changed"}'
    payload_1 = {"action": "PARTIAL", "signal_id": "abc-123"}
    payload_2 = {
        "action": "PARTIAL",
        "signal_id": "abc-123",
        "extra": "changed",
    }

    hash_1 = _compute_strategy_signal_hash(user_id, payload_1, raw_body_1)
    hash_2 = _compute_strategy_signal_hash(user_id, payload_2, raw_body_2)

    # Same signal_id → same hash (helper keys off signal_id when present).
    assert hash_1 == hash_2

    # And different signal_id → different hash (no false dedup).
    payload_3 = {"action": "PARTIAL", "signal_id": "xyz-999"}
    raw_body_3 = b'{"action":"PARTIAL","signal_id":"xyz-999"}'
    hash_3 = _compute_strategy_signal_hash(user_id, payload_3, raw_body_3)
    assert hash_3 != hash_1
