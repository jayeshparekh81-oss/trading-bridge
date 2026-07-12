"""Cash executor (CASH Module A) — double-lock + shares rules + paper round-trip.

Written TEST-FIRST per CASH_MODULE_SPEC_LOCKED.md. The executor must:
  * refuse when CASH_EXECUTION_ENABLED is False (default);
  * refuse when the strategy is NOT paper (double lock);
  * flag ON + paper LONG entry: position row with the equity symbol AS-IS
    (no mapper/resolver), qty in SHARES from strategy_json.entry_shares
    (default 2), min-2 + even-only ENFORCED (refuse, never silently round),
    product DELIVERY only, broker never touched;
  * SHORT refused (long-only); MIS refused anywhere (delivery-only);
  * exits: PARTIAL reduces shares; EXIT/SL_HIT close at payload price on the
    STORED position.symbol; post-close exit → no_open_position.

Module A is wiring-free: signal_execution.py and all frozen files untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

# ─── JSONB → JSON shim for the SQLite test engine ─────────────────────
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.ext.compiler import compiles as _compiles


@_compiles(_JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.services import cash_executor as CE


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _seed(maker, *, is_paper: bool, strategy_json: dict | None = None) -> tuple[Any, Any]:
    from app.core.security import encrypt_credential
    from app.db.models.broker_credential import BrokerCredential
    from app.schemas.broker import BrokerName

    sj = strategy_json if strategy_json is not None else {"instrument_type": "cash"}
    async with maker() as s:
        user = User(email=f"cash-{uuid4().hex[:8]}@t.invalid", password_hash="x",
                    is_active=True)
        s.add(user)
        await s.flush()
        cred = BrokerCredential(
            user_id=user.id, broker_name=BrokerName.DHAN,
            client_id_enc=encrypt_credential("T"),
            api_key_enc=encrypt_credential("T"),
            api_secret_enc=encrypt_credential("T"),
            access_token_enc=encrypt_credential("T"),
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC), is_active=True)
        s.add(cred)
        await s.flush()
        strat = Strategy(
            user_id=user.id, broker_credential_id=cred.id,
            name="cash-exec-test", entry_lots=1, partial_profit_lots=0,
            trail_lots=0, allowed_symbols=["RELIANCE"],
            strategy_json=sj, ai_validation_enabled=False,
            is_active=True, is_paper=is_paper)
        s.add(strat)
        await s.commit()
        return user, strat


async def _signal(maker, user, strat, *, action: str = "ENTRY",
                  payload: dict | None = None) -> Any:
    base: dict[str, Any] = {"action": action, "side": "long",
                            "symbol": "RELIANCE", "price": 2885.0,
                            "timestamp": "2026-07-14T09:20:00.000001+00:00"}
    if payload:
        base.update(payload)
    async with maker() as s:
        sig = StrategySignal(
            id=uuid4(), user_id=user.id, strategy_id=strat.id,
            symbol=base["symbol"], action=action, quantity=None,
            order_type="market", status="executing", raw_payload=base,
            received_at=datetime.now(UTC))
        s.add(sig)
        await s.commit()
        return sig


async def _positions(maker, strat) -> list[StrategyPosition]:
    async with maker() as s:
        return list((await s.execute(
            select(StrategyPosition)
            .where(StrategyPosition.strategy_id == strat.id))).scalars())


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "cash_execution_enabled", True)


@pytest.fixture
def broker_spy(monkeypatch):
    from unittest.mock import MagicMock

    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    return spy


# ═══════════════════════════════════════════════════════════════════════
# (b)(c) Gates — double lock
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_flag_off_skips(db):
    assert get_settings().cash_execution_enabled is False   # default OFF
    user, strat = await _seed(db, is_paper=True)
    sig = await _signal(db, user, strat)
    async with db() as s:
        res = await CE.execute_cash_entry(s, signal=sig, strategy=strat)
    assert res.status == "skipped_flag_off"
    assert await _positions(db, strat) == []


@pytest.mark.asyncio
async def test_flag_on_live_strategy_refused(db, flag_on, broker_spy):
    user, strat = await _seed(db, is_paper=False)
    sig = await _signal(db, user, strat)
    async with db() as s:
        res = await CE.execute_cash_entry(s, signal=sig, strategy=strat)
    assert res.status == "refused_not_paper"
    assert await _positions(db, strat) == []
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# (d) Paper LONG entry — shares rules
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paper_entry_default_two_shares(db, flag_on, broker_spy):
    user, strat = await _seed(db, is_paper=True)   # no entry_shares → default 2
    sig = await _signal(db, user, strat)
    async with db() as s:
        res = await CE.execute_cash_entry(s, signal=sig, strategy=strat)
    assert res.status == "executed", res.message
    rows = await _positions(db, strat)
    assert len(rows) == 1
    pos = rows[0]
    assert pos.symbol == "RELIANCE"                 # AS-IS, no mapper
    assert pos.side == "long"
    assert pos.total_quantity == 2                  # SHARES default
    assert Decimal(pos.avg_entry_price) == Decimal("2885.0")
    assert pos.status == "open"
    broker_spy.assert_not_called()


@pytest.mark.asyncio
async def test_paper_entry_entry_shares_from_strategy_json(db, flag_on, broker_spy):
    user, strat = await _seed(
        db, is_paper=True,
        strategy_json={"instrument_type": "cash", "entry_shares": 10})
    sig = await _signal(db, user, strat)
    async with db() as s:
        res = await CE.execute_cash_entry(s, signal=sig, strategy=strat)
    assert res.status == "executed", res.message
    assert (await _positions(db, strat))[0].total_quantity == 10
    broker_spy.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_shares,why", [(1, "below min"), (0, "below min"),
                                            (3, "odd"), (7, "odd"), (-4, "below min")])
async def test_bad_shares_refused_not_rounded(db, flag_on, broker_spy, bad_shares, why):
    user, strat = await _seed(
        db, is_paper=True,
        strategy_json={"instrument_type": "cash", "entry_shares": bad_shares})
    sig = await _signal(db, user, strat)
    async with db() as s:
        res = await CE.execute_cash_entry(s, signal=sig, strategy=strat)
    assert res.status == "refused_shares", (bad_shares, why, res.status)
    assert await _positions(db, strat) == []        # REFUSED, never rounded
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# (e) LONG-only  (f) DELIVERY-only
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"side": "short"},
    {"signal_direction": "SHORT_ENTRY"},
    {"type": "SHORT_ENTRY"},
])
async def test_short_entry_refused(db, flag_on, broker_spy, payload):
    user, strat = await _seed(db, is_paper=True)
    sig = await _signal(db, user, strat, payload=payload)
    async with db() as s:
        res = await CE.execute_cash_entry(s, signal=sig, strategy=strat)
    assert res.status == "refused_short"
    assert await _positions(db, strat) == []
    broker_spy.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("sj_extra,payload", [
    ({"product_type": "MIS"}, None),                       # config MIS
    ({"product_type": "INTRADAY"}, None),                  # config intraday
    (None, {"product_type": "MIS"}),                       # request MIS
])
async def test_mis_refused_everywhere(db, flag_on, broker_spy, sj_extra, payload):
    sj = {"instrument_type": "cash"}
    if sj_extra:
        sj.update(sj_extra)
    user, strat = await _seed(db, is_paper=True, strategy_json=sj)
    sig = await _signal(db, user, strat, payload=payload)
    async with db() as s:
        res = await CE.execute_cash_entry(s, signal=sig, strategy=strat)
    assert res.status == "refused_product"
    assert await _positions(db, strat) == []
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# (g) Exits — stored symbol, shares reduce/close
# ═══════════════════════════════════════════════════════════════════════


async def _open_position(db, shares: int = 10):
    settings = get_settings()
    old = settings.cash_execution_enabled
    settings.cash_execution_enabled = True
    try:
        user, strat = await _seed(
            db, is_paper=True,
            strategy_json={"instrument_type": "cash", "entry_shares": shares})
        entry = await _signal(db, user, strat)
        async with db() as s:
            res = await CE.execute_cash_entry(s, signal=entry, strategy=strat)
            assert res.status == "executed", res.message
        return user, strat
    finally:
        settings.cash_execution_enabled = old


@pytest.mark.asyncio
async def test_partial_reduces_shares(db, flag_on, broker_spy):
    user, strat = await _open_position(db, shares=10)
    sig = await _signal(db, user, strat, action="PARTIAL",
                        payload={"price": 2900.0, "closePct": 50})
    async with db() as s:
        res = await CE.execute_cash_exit(s, signal=sig, strategy=strat,
                                         action_kind="partial")
    assert res.status == "executed", res.message
    pos = (await _positions(db, strat))[0]
    assert pos.remaining_quantity == 5
    assert pos.status == "partial"
    assert pos.symbol == "RELIANCE"                 # stored symbol untouched
    broker_spy.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("action,kind", [("EXIT", "exit"), ("SL_HIT", "sl_hit")])
async def test_exit_closes_at_payload_price(db, flag_on, broker_spy, action, kind):
    user, strat = await _open_position(db, shares=10)
    sig = await _signal(db, user, strat, action=action, payload={"price": 2985.0})
    async with db() as s:
        res = await CE.execute_cash_exit(s, signal=sig, strategy=strat,
                                         action_kind=kind)
    assert res.status == "executed", res.message
    pos = (await _positions(db, strat))[0]
    assert pos.status == "closed"
    assert pos.remaining_quantity == 0
    # (2985 − 2885) × 10 shares
    assert Decimal(pos.final_pnl) == Decimal("100") * 10
    assert res.symbol == "RELIANCE"                 # stored, never re-resolved
    broker_spy.assert_not_called()


@pytest.mark.asyncio
async def test_post_close_exit_is_noop(db, flag_on):
    user, strat = await _open_position(db, shares=4)
    sig1 = await _signal(db, user, strat, action="EXIT", payload={"price": 2900.0})
    async with db() as s:
        await CE.execute_cash_exit(s, signal=sig1, strategy=strat, action_kind="exit")
    sig2 = await _signal(db, user, strat, action="EXIT", payload={"price": 2910.0})
    async with db() as s:
        res = await CE.execute_cash_exit(s, signal=sig2, strategy=strat,
                                         action_kind="exit")
    assert res.status == "no_open_position"


@pytest.mark.asyncio
async def test_exit_flag_off_skips(db):
    user, strat = await _open_position(db, shares=4)
    assert get_settings().cash_execution_enabled is False
    sig = await _signal(db, user, strat, action="EXIT", payload={"price": 2900.0})
    async with db() as s:
        res = await CE.execute_cash_exit(s, signal=sig, strategy=strat,
                                         action_kind="exit")
    assert res.status == "skipped_flag_off"
