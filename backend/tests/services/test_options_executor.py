"""Options executor (Brick #3, Module A) — double-lock gates + paper round-trip.

Written TEST-FIRST per the founder spec. The executor must:
  * refuse when OPTIONS_EXECUTION_ENABLED is False (default) — even for a
    paper options strategy;
  * refuse when the strategy is NOT paper — even with the flag ON (double lock);
  * with flag ON + paper: build the leg via map_pine_to_option_order, create a
    paper StrategyPosition carrying the OPTION symbol, and NEVER touch the
    broker (DhanAdapter.place_order asserted not called);
  * exits: PARTIAL reduces qty; EXIT / SL_HIT close the row at the payload
    price using the STORED position.symbol (never re-resolves).

Module A is wiring-free: signal_execution.py / strategy_executor.py /
direct_exit.py / dhan.py / futures_resolver.py are untouched, so the four
router invariant tests must stay green alongside this file.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

# ─── JSONB → JSON shim for the SQLite test engine (see integration conftest) ──
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.ext.compiler import compiles as _compiles


@_compiles(_JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.brokers.dhan import ScripMeta
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.services import options_executor as OE

# ───────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────

_NRML_OPTIONS: dict[str, Any] = {
    "option_type": "auto",
    "strike_selection": {"method": "ATM", "offset": 0},
    "expiry": "current_week",
    "premium_budget_per_lot": 18000,
    "product_type": "NRML",
    "carry_forward": True,
    "expiry_day_force_close": True,
    "no_intraday_squareoff": True,
}

_REF_DATE = date(2026, 7, 13)
_EXPIRY = _REF_DATE + timedelta(days=3)


class _FakeScripMaster:
    def __init__(self, *metas: ScripMeta) -> None:
        self._meta = {m.security_id: m for m in metas}

    def lot_size(self, security_id: str) -> int | None:
        m = self._meta.get(security_id)
        return m.lot_size if m else None


def _option_scrip(option_type: str = "CE") -> ScripMeta:
    return ScripMeta(
        security_id="44321" if option_type == "CE" else "44322",
        symbol=f"BSE-{_EXPIRY:%d%b%Y}-2400-{option_type}".upper(),
        segment="NSE_FNO",
        instrument="OPTSTK",
        lot_size=375,
        option_type=option_type,
        strike_price=Decimal("2400"),
        expiry_date=_EXPIRY,
    )


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _seed(maker, *, is_paper: bool) -> tuple[Any, Any]:
    from app.core.security import encrypt_credential
    from app.db.models.broker_credential import BrokerCredential
    from app.schemas.broker import BrokerName

    async with maker() as s:
        user = User(email=f"opt-{uuid4().hex[:8]}@t.invalid", password_hash="x",
                    is_active=True)
        s.add(user)
        await s.flush()
        # Paper placeholder FK — the executor never builds/uses a broker; the
        # credential row only satisfies strategy_positions' NOT NULL FK.
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
            broker_credential_id=cred.id,
            user_id=user.id,
            name="options-exec-test",
            entry_lots=4,
            partial_profit_lots=0,
            trail_lots=0,
            allowed_symbols=["NSE:BSE"],
            strategy_json={"options": _NRML_OPTIONS},
            ai_validation_enabled=False,
            is_active=True,
            is_paper=is_paper,
        )
        s.add(strat)
        await s.commit()
        return user, strat


async def _entry_signal(maker, user, strat, *, price: float = 180.0) -> Any:
    async with maker() as s:
        sig = StrategySignal(
            id=uuid4(), user_id=user.id, strategy_id=strat.id,
            symbol="NSE:BSE", action="ENTRY", quantity=1, order_type="market",
            status="executing",
            raw_payload={"type": "LONG_ENTRY", "spot_price": "2437",
                         "price": price,
                         "timestamp": "2026-07-13T09:20:00.000001+00:00"},
            received_at=datetime.now(UTC),
        )
        s.add(sig)
        await s.commit()
        return sig


async def _exit_signal(maker, user, strat, *, action: str, price: float,
                       close_pct: float | None = None) -> Any:
    payload: dict[str, Any] = {"type": "LONG_EXIT", "side": "long",
                               "symbol": "NSE:BSE", "price": price}
    if close_pct is not None:
        payload["closePct"] = close_pct
    async with maker() as s:
        sig = StrategySignal(
            id=uuid4(), user_id=user.id, strategy_id=strat.id,
            symbol="NSE:BSE", action=action, quantity=None, order_type="market",
            status="executing", raw_payload=payload,
            received_at=datetime.now(UTC),
        )
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
    monkeypatch.setattr(get_settings(), "options_execution_enabled", True)


@pytest.fixture
def broker_spy(monkeypatch):
    """place_order must NEVER be reached from the options paper path."""
    from unittest.mock import MagicMock

    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    return spy


# ═══════════════════════════════════════════════════════════════════════
# Gates (double lock)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_flag_off_skips_even_for_paper_strategy(db):
    assert get_settings().options_execution_enabled is False  # default OFF
    user, strat = await _seed(db, is_paper=True)
    sig = await _entry_signal(db, user, strat)
    async with db() as s:
        res = await OE.execute_options_entry(
            s, signal=sig, strategy=strat, scrip_master=_FakeScripMaster(_option_scrip()),
            reference_date=_REF_DATE)
    assert res.status == "skipped_flag_off"
    assert await _positions(db, strat) == []


@pytest.mark.asyncio
async def test_flag_on_but_live_strategy_refused(db, flag_on, broker_spy):
    user, strat = await _seed(db, is_paper=False)   # LIVE strategy
    sig = await _entry_signal(db, user, strat)
    async with db() as s:
        res = await OE.execute_options_entry(
            s, signal=sig, strategy=strat, scrip_master=_FakeScripMaster(_option_scrip()),
            reference_date=_REF_DATE)
    assert res.status == "refused_not_paper"
    assert await _positions(db, strat) == []
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# Paper entry round-trip
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paper_entry_creates_option_position_no_broker(db, flag_on, broker_spy):
    user, strat = await _seed(db, is_paper=True)
    sig = await _entry_signal(db, user, strat, price=180.0)
    async with db() as s:
        res = await OE.execute_options_entry(
            s, signal=sig, strategy=strat, scrip_master=_FakeScripMaster(_option_scrip()),
            reference_date=_REF_DATE)
    assert res.status == "executed", res.message
    rows = await _positions(db, strat)
    assert len(rows) == 1
    pos = rows[0]
    # position carries the OPTION leg symbol, not the underlying
    assert pos.symbol == f"BSE-{_EXPIRY:%d%b%Y}-2400-CE".upper()
    assert pos.side == "long"
    assert pos.total_quantity == 4 * 375          # entry_lots × lot_size
    assert pos.remaining_quantity == 4 * 375
    assert pos.status == "open"
    assert Decimal(pos.avg_entry_price) == Decimal("180.0")
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# Exits — stored symbol, never re-resolved
# ═══════════════════════════════════════════════════════════════════════


async def _open_position(db, flag_on_unused=None):
    user, strat = await _seed(db, is_paper=True)
    entry = await _entry_signal(db, user, strat, price=180.0)
    async with db() as s:
        await OE.execute_options_entry(
            s, signal=entry, strategy=strat,
            scrip_master=_FakeScripMaster(_option_scrip()), reference_date=_REF_DATE)
    return user, strat


@pytest.mark.asyncio
async def test_partial_reduces_quantity(db, flag_on, broker_spy):
    user, strat = await _open_position(db)
    sig = await _exit_signal(db, user, strat, action="PARTIAL", price=200.0,
                             close_pct=50)
    async with db() as s:
        res = await OE.execute_options_exit(
            s, signal=sig, strategy=strat, action_kind="partial")
    assert res.status == "executed", res.message
    pos = (await _positions(db, strat))[0]
    assert pos.total_quantity == 1500
    assert pos.remaining_quantity == 750           # 50% closed
    assert pos.status == "partial"
    assert pos.symbol.endswith("-CE")              # stored symbol untouched
    broker_spy.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("action,kind", [("EXIT", "exit"), ("SL_HIT", "sl_hit")])
async def test_exit_closes_at_payload_price(db, flag_on, broker_spy, action, kind):
    user, strat = await _open_position(db)
    sig = await _exit_signal(db, user, strat, action=action, price=210.0)
    async with db() as s:
        res = await OE.execute_options_exit(
            s, signal=sig, strategy=strat, action_kind=kind)
    assert res.status == "executed", res.message
    pos = (await _positions(db, strat))[0]
    assert pos.status == "closed"
    assert pos.remaining_quantity == 0
    # long premium: (210 − 180) × 1500
    assert Decimal(pos.final_pnl) == Decimal("30") * 1500
    # closed using the STORED option symbol (payload symbol is the underlying)
    assert pos.symbol.endswith("-CE")
    assert res.symbol == pos.symbol
    broker_spy.assert_not_called()


@pytest.mark.asyncio
async def test_exit_without_open_position_is_noop(db, flag_on):
    user, strat = await _seed(db, is_paper=True)
    sig = await _exit_signal(db, user, strat, action="EXIT", price=200.0)
    async with db() as s:
        res = await OE.execute_options_exit(
            s, signal=sig, strategy=strat, action_kind="exit")
    assert res.status == "no_open_position"


@pytest.mark.asyncio
async def test_exit_gates_mirror_entry_gates(db):
    """Flag OFF blocks exits too — the module is fully dormant by default."""
    user, strat = await _open_position_with_flag(db)
    sig = await _exit_signal(db, user, strat, action="EXIT", price=200.0)
    assert get_settings().options_execution_enabled is False
    async with db() as s:
        res = await OE.execute_options_exit(
            s, signal=sig, strategy=strat, action_kind="exit")
    assert res.status == "skipped_flag_off"


async def _open_position_with_flag(db):
    """Open a paper position while the flag is temporarily ON, then restore."""
    settings = get_settings()
    old = settings.options_execution_enabled
    settings.options_execution_enabled = True
    try:
        return await _open_position(db)
    finally:
        settings.options_execution_enabled = old
