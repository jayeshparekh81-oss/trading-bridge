"""2-lot (750 = 2x375) lifecycle quantity tests + the leg-1 entry-sizing fix.

Every quantity is a 375-multiple; the suite asserts the engine NEVER books a
sub-lot, that the ENTRY records the CONFIRMED filled qty (leg-1 fix), and that
exits decrement by the CONFIRMED fill — so a partial entry can never propagate
into a flip-to-short on exit. Drives the LIVE path (``strategy.is_paper=False``)
with a spec'd ``BrokerInterface`` mock whose ``confirm_fill`` returns a
configurable fill — no real broker, no DB-less shortcut.

Headline (leg-1):
  * entry 750 requested / 375 confirmed -> position records **375** (not 750);
  * a subsequent EXIT then closes exactly 375 -> FLAT, broker net never < 0.
  * BONUS: on the *pre-fix* mis-recorded state (750 recorded / 375 real) a full
    EXIT sends 750 (NOT clamped to the real 375) -> over-sell -> FLIP to short.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Global stays paper; the strategy's is_paper=False forces the LIVE path
# per-strategy (migration 027 / resolve_paper_mode).
os.environ.setdefault("STRATEGY_PAPER_MODE", "true")

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.brokers.base import BrokerInterface
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.schemas.broker import (
    BrokerName,
    OrderFill,
    OrderResponse,
    OrderStatus,
    OrderType,
)
from app.services import direct_exit
from app.services import strategy_executor as se

_LOT = 375  # BSE-JUN2026-FUT lot size


# ── fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_external_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the live path's external I/O so the qty/state logic runs offline:
    idempotency guard passes through, redis + telegram are no-ops."""
    import app.core.redis_client as _rc
    import app.core.signal_idempotency as _idem
    import app.services.telegram_alerts as _alerts

    monkeypatch.setattr(_idem, "check_and_set_signal_idempotent", AsyncMock(return_value=True))
    fake = MagicMock()
    fake.set = AsyncMock(return_value=True)
    fake.get = AsyncMock(return_value=None)
    fake.delete = AsyncMock(return_value=1)
    monkeypatch.setattr(_rc, "get_redis", lambda: fake)
    monkeypatch.setattr(_alerts, "send_alert", AsyncMock(return_value=None))


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db: AsyncSession) -> dict[str, Any]:
    """User + active Dhan credential + LIVE direct_exit strategy."""
    user = User(email="lc@example.com", password_hash="x", is_active=True)
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
    strat = Strategy(
        user_id=user.id,
        name="lc-bse",
        broker_credential_id=cred.id,
        entry_lots=4,  # ceiling 4 lots x 375 = 1500 >= 750
        partial_profit_lots=2,  # even-lot validator
        ai_validation_enabled=False,
        is_active=True,
        is_paper=False,  # LIVE path
        exit_strategy_type="direct_exit",
    )
    db.add(strat)
    await db.commit()
    await db.refresh(strat)
    return {"user_id": user.id, "cred_id": cred.id, "strategy": strat}


def _broker(
    *,
    filled_qty: int,
    status: OrderStatus = OrderStatus.COMPLETE,
    raw: str = "TRADED",
    avg: Decimal | None = Decimal("3800"),
    timed_out: bool = False,
    ack: OrderStatus = OrderStatus.PENDING,
) -> MagicMock:
    b = MagicMock(spec=BrokerInterface)
    b.broker_name = BrokerName.DHAN
    b.is_session_valid = AsyncMock(return_value=True)
    b.login = AsyncMock(return_value=True)
    b.validate_symbol = AsyncMock(return_value=None)
    b.get_funds = AsyncMock(return_value=Decimal("100000000"))
    b.place_order = AsyncMock(
        return_value=OrderResponse(broker_order_id="OID", status=ack, message="", raw_response={})
    )
    b.confirm_fill = AsyncMock(
        return_value=OrderFill(
            broker_order_id="OID",
            order_status=status,
            raw_status=raw,
            filled_qty=filled_qty,
            avg_price=avg,
            timed_out=timed_out,
        )
    )
    return b


def _factory(broker: MagicMock) -> Any:
    return lambda creds: broker


def _signal(
    seeded: dict[str, Any],
    *,
    action: str,
    side: str = "long",
    quantity: int | None = None,
    close_pct: float | None = None,
    symbol: str = "BSE-MAY2026-FUT",
) -> StrategySignal:
    payload: dict[str, Any] = {
        "action": action,
        "side": side,
        "symbol": symbol,
        "price": 3800.0,
        "lot_size_hint": _LOT,
        "signal_id": f"t_{action}_{uuid.uuid4().hex[:6]}",
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


async def _seed_position(
    db: AsyncSession,
    seeded: dict[str, Any],
    *,
    qty: int = 750,
    side: str = "buy",
) -> StrategyPosition:
    """Insert an open position directly (isolates exit tests / the bonus
    mis-recorded-state characterization from the entry path)."""
    pos = StrategyPosition(
        user_id=seeded["user_id"],
        strategy_id=seeded["strategy"].id,
        broker_credential_id=seeded["cred_id"],
        signal_id=None,
        symbol="BSE-MAY2026-FUT",
        side=side,
        total_quantity=qty,
        remaining_quantity=qty,
        avg_entry_price=Decimal("3800"),
        status="open",
        opened_at=datetime.now(UTC),
    )
    db.add(pos)
    await db.commit()
    await db.refresh(pos)
    return pos


async def _entry(
    db: AsyncSession, seeded: dict[str, Any], *, requested: int, filled: int
) -> StrategyPosition:
    sig = _signal(seeded, action="ENTRY", side="long", quantity=requested)
    db.add(sig)
    await db.flush()
    res = await se.place_strategy_orders(
        db,
        signal=sig,
        strategy=seeded["strategy"],
        broker_factory=_factory(_broker(filled_qty=filled)),
    )
    pos = await db.get(StrategyPosition, res.position_id)
    assert pos is not None
    return pos


# ── LEG-1 fix: entry sizes by CONFIRMED fill ─────────────────────────────


async def test_entry_partial_fill_sizes_by_confirmed_375(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """750 requested, broker confirms 375 -> position records 375 (the fill),
    never 750. This is the leg-1 fix."""
    pos = await _entry(db, seeded, requested=750, filled=375)
    assert pos.total_quantity == 375
    assert pos.remaining_quantity == 375


async def test_entry_full_fill_sizes_750(db: AsyncSession, seeded: dict[str, Any]) -> None:
    """750 requested, 750 confirmed -> position 750 (full fill unchanged)."""
    pos = await _entry(db, seeded, requested=750, filled=750)
    assert pos.total_quantity == 750
    assert pos.remaining_quantity == 750


async def test_entry_missing_filled_qty_raises_no_silent_fallback(
    db: AsyncSession, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """If broker_response lacks filled_qty, the entry RAISES — it must NOT
    silently fall back to the requested qty (that reinstates the bug)."""

    async def _no_filled(**kw: Any) -> dict[str, Any]:
        return {
            "broker_order_id": "OID",
            "status": "COMPLETE",
            "avg_price": "3800",
            "raw": {},
        }  # deliberately NO filled_qty

    monkeypatch.setattr(se, "_live_place_order", _no_filled)
    sig = _signal(seeded, action="ENTRY", side="long", quantity=750)
    db.add(sig)
    await db.flush()
    with pytest.raises(se.StrategyExecutorError):
        await se.place_strategy_orders(
            db,
            signal=sig,
            strategy=seeded["strategy"],
            broker_factory=_factory(_broker(filled_qty=375)),
        )


# ── HEADLINE flip-path: partial entry -> exit -> FLAT, no short flip ──────


async def test_flip_path_partial_entry_then_exit_flat_no_short(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """The full leg-1 flip-path. 2-lot (750) entry fills only 375 ->
    position records 375 (fix). A subsequent EXIT closes EXACTLY 375 -> FLAT.
    The broker sold exactly what it held (375 long), so net = 0 and never goes
    negative: no flip to short."""
    # 1. partial entry -> position 375
    pos = await _entry(db, seeded, requested=750, filled=375)
    entry_filled = 375
    assert pos.remaining_quantity == 375

    # 2. EXIT — broker holds 375 long; exit must SELL exactly 375
    exit_sig = _signal(seeded, action="EXIT")
    db.add(exit_sig)
    await db.flush()
    exit_broker = _broker(filled_qty=375)
    await direct_exit.execute_exit(
        db, signal=exit_sig, strategy=seeded["strategy"], broker_factory=_factory(exit_broker)
    )
    sent = exit_broker.place_order.await_args.args[0]
    exit_sent = sent.quantity
    exit_filled = 375

    # 3. assertions: closed exactly the held qty, FLAT, broker net never < 0
    assert exit_sent == 375  # NOT 750 — closes only what was actually held
    await db.refresh(pos)
    assert pos.remaining_quantity == 0
    assert pos.status == "closed"
    net_after = entry_filled - exit_filled  # 375 - 375 = 0
    assert net_after == 0
    assert net_after >= 0  # never short — no flip


# ── BONUS: characterize the pre-fix bug's downstream severity ─────────────


async def test_bonus_unfixed_oversized_position_oversells_and_flips(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """Severity characterization (moot AFTER the leg-1 fix, since the entry can
    no longer record 750 against a 375 fill). Simulate the *pre-fix* state: a
    position mis-recorded as 750 while the broker really holds only 375. A full
    EXIT closes ``position.remaining_quantity`` (750) — it does NOT clamp to the
    broker's real 375. So the broker sells 375 to close + 375 to open = FLIP to
    375 SHORT, while the DB marks the position closed/flat (reverse phantom)."""
    pos = await _seed_position(db, seeded, qty=750)  # mis-recorded position
    broker = _broker(filled_qty=750)  # broker fills the full 750 sell
    sig = _signal(seeded, action="EXIT")
    db.add(sig)
    await db.flush()
    await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded["strategy"], broker_factory=_factory(broker)
    )
    sent = broker.place_order.await_args.args[0]
    assert sent.quantity == 750  # over-sells — NOT clamped to the real 375
    real_long_held = 375
    net_after = real_long_held - sent.quantity  # 375 - 750
    assert net_after == -375  # FLIP to 375 SHORT — severity HIGH
    await db.refresh(pos)
    assert pos.remaining_quantity == 0  # DB says flat while broker is -375 short


# ── Part C lifecycle re-confirm (direct_exit unchanged) ──────────────────


@pytest.mark.parametrize(
    "open_qty,pct,expected",
    [
        (375, 50, 0),  # half-lot @ 1 lot -> 0 (sub-lot floored away -> ignored)
        (750, 50, 375),  # 1 lot
        (750, 33, 0),  # floor(247.5)=247 -> 0 whole lots
        (750, 99, 375),  # never the whole position (pct < 100)
        (1500, 50, 750),  # 2 lots
        (1125, 50, 375),  # floor(562.5)=562 -> 1 lot
    ],
)
def test_qty_from_open_pct_floors_to_lots(open_qty: int, pct: float, expected: int) -> None:
    assert direct_exit.qty_from_open_pct(open_qty, pct, _LOT) == expected


async def test_partial_375_fill_decrements_to_375(db: AsyncSession, seeded: dict[str, Any]) -> None:
    pos = await _seed_position(db, seeded, qty=750)
    broker = _broker(filled_qty=375)
    sig = _signal(seeded, action="PARTIAL", close_pct=50)
    db.add(sig)
    await db.flush()
    res = await direct_exit.execute_partial(
        db, signal=sig, strategy=seeded["strategy"], broker_factory=_factory(broker)
    )
    assert res["status"] == "executed"
    await db.refresh(pos)
    assert pos.remaining_quantity == 375
    assert pos.status == "partial"


async def test_partial_zero_fill_leaves_position_open_750(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    pos = await _seed_position(db, seeded, qty=750)
    broker = _broker(filled_qty=0, status=OrderStatus.REJECTED, raw="REJECTED", avg=None)
    sig = _signal(seeded, action="PARTIAL", close_pct=50)
    db.add(sig)
    await db.flush()
    res = await direct_exit.execute_partial(
        db, signal=sig, strategy=seeded["strategy"], broker_factory=_factory(broker)
    )
    assert res["status"] == "ignored"
    assert res["reason"] == "close_not_filled"
    await db.refresh(pos)
    assert pos.remaining_quantity == 750  # untouched — no phantom flatten
    assert pos.status == "open"


async def test_exit_partial_fill_375_of_750_leaves_375_partial(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """Full-SL on a 750 position, broker fills only 375 -> remaining 375,
    partial (the unfilled 375 stays open — never silently flattened)."""
    pos = await _seed_position(db, seeded, qty=750)
    broker = _broker(filled_qty=375)
    sig = _signal(seeded, action="SL_HIT")
    db.add(sig)
    await db.flush()
    await direct_exit.execute_exit(
        db,
        signal=sig,
        strategy=seeded["strategy"],
        leg_role="direct_sl",
        broker_factory=_factory(broker),
    )
    await db.refresh(pos)
    assert pos.remaining_quantity == 375
    assert pos.status == "partial"


async def test_exit_full_fill_375_flattens(db: AsyncSession, seeded: dict[str, Any]) -> None:
    pos = await _seed_position(db, seeded, qty=375)
    broker = _broker(filled_qty=375)
    sig = _signal(seeded, action="EXIT")
    db.add(sig)
    await db.flush()
    await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded["strategy"], broker_factory=_factory(broker)
    )
    await db.refresh(pos)
    assert pos.remaining_quantity == 0
    assert pos.status == "closed"


async def test_exit_zero_fill_stays_open_375(db: AsyncSession, seeded: dict[str, Any]) -> None:
    pos = await _seed_position(db, seeded, qty=375)
    broker = _broker(filled_qty=0, status=OrderStatus.REJECTED, raw="REJECTED", avg=None)
    sig = _signal(seeded, action="EXIT")
    db.add(sig)
    await db.flush()
    res = await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded["strategy"], broker_factory=_factory(broker)
    )
    assert res["status"] == "ignored"
    await db.refresh(pos)
    assert pos.remaining_quantity == 375  # no phantom flatten
    assert pos.status == "open"


async def test_full_sl_after_partial_closes_only_remaining_375(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """Over-close clamp: position already partialed to 375; a full-SL whose
    signal still carries 750 closes ``remaining_quantity`` (375), NOT 750."""
    pos = await _seed_position(db, seeded, qty=375)
    broker = _broker(filled_qty=375)
    sig = _signal(seeded, action="SL_HIT", quantity=750)
    db.add(sig)
    await db.flush()
    await direct_exit.execute_exit(
        db,
        signal=sig,
        strategy=seeded["strategy"],
        leg_role="direct_sl",
        broker_factory=_factory(broker),
    )
    sent = broker.place_order.await_args.args[0]
    assert sent.quantity == 375  # clamped to remaining — never 750
    await db.refresh(pos)
    assert pos.remaining_quantity == 0
    assert pos.status == "closed"


async def test_exit_decrement_uses_confirmed_not_requested(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """Close requested for 750 (remaining), broker confirms 375 -> decrement is
    the CONFIRMED 375, leaving 375 open — never the requested 750."""
    pos = await _seed_position(db, seeded, qty=750)
    broker = _broker(filled_qty=375)
    sig = _signal(seeded, action="EXIT")
    db.add(sig)
    await db.flush()
    await direct_exit.execute_exit(
        db, signal=sig, strategy=seeded["strategy"], broker_factory=_factory(broker)
    )
    sent = broker.place_order.await_args.args[0]
    assert sent.quantity == 750  # we ASK for the full remaining
    await db.refresh(pos)
    assert pos.remaining_quantity == 375  # but only the CONFIRMED 375 is booked
    assert pos.status == "partial"


# ── LIMIT-scope routing: CDSL now marketable-LIMIT (cutover-7) ────────────

_CDSL_ID = uuid.UUID("0252e82c-484a-4891-b0e4-496de9664d17")
_BSE_ID = uuid.UUID("89423ecc-c76e-432c-b107-0791508542f0")
_UNSCOPED_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


async def _strategy_with_id(
    db: AsyncSession, seeded: dict[str, Any], strat_id: uuid.UUID
) -> Strategy:
    strat = Strategy(
        id=strat_id,
        user_id=seeded["user_id"],
        name=f"scoped-{str(strat_id)[:8]}",
        broker_credential_id=seeded["cred_id"],
        entry_lots=2,
        partial_profit_lots=1,
        ai_validation_enabled=False,
        is_active=True,
        is_paper=False,
        exit_strategy_type="direct_exit",
    )
    db.add(strat)
    await db.commit()
    await db.refresh(strat)
    return strat


async def _routed_order(
    db: AsyncSession, seeded: dict[str, Any], strat: Strategy
) -> Any:
    """Drive a live ENTRY through place_strategy_orders; return the OrderRequest
    actually sent to the broker (the signal carries price=3800 for the basis)."""
    sig = _signal(
        {"user_id": seeded["user_id"], "strategy": strat},
        action="ENTRY",
        side="long",
        quantity=750,
    )
    db.add(sig)
    await db.flush()
    broker = _broker(filled_qty=750)
    await se.place_strategy_orders(
        db, signal=sig, strategy=strat, broker_factory=_factory(broker)
    )
    return broker.place_order.await_args.args[0]


async def test_cdsl_routes_marketable_limit(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """CDSL (0252e82c) now in _LIMIT_ORDER_STRATEGY_IDS → entry routes a
    marketable LIMIT (priced off the alert's `price`), NOT MARKET."""
    strat = await _strategy_with_id(db, seeded, _CDSL_ID)
    sent = await _routed_order(db, seeded, strat)
    assert sent.order_type is OrderType.LIMIT
    assert sent.price is not None


async def test_bse_still_routes_limit(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """BSE (89423ecc) stays LIMIT-scoped — unchanged by the CDSL add."""
    strat = await _strategy_with_id(db, seeded, _BSE_ID)
    sent = await _routed_order(db, seeded, strat)
    assert sent.order_type is OrderType.LIMIT
    assert sent.price is not None


async def test_unscoped_strategy_routes_market(
    db: AsyncSession, seeded: dict[str, Any]
) -> None:
    """A strategy NOT in the frozenset still routes MARKET — the CDSL add
    didn't widen the scope to everything."""
    strat = await _strategy_with_id(db, seeded, _UNSCOPED_ID)
    sent = await _routed_order(db, seeded, strat)
    assert sent.order_type is OrderType.MARKET
    assert sent.price is None
