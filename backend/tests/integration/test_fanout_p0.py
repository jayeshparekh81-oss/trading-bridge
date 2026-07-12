"""FAN-OUT Module A (P0 rework) — mirror exit, position-check, real lot-math,
margin-safety shape. All inside the dormant marketplace_fanout module; paper
stub holds (broker NEVER called — asserted).

Test-FIRST per FANOUT_DESIGN (founder-locked):
  #1 mirror exit  — owner PARTIAL 50% on a sub holding 8 → sub closes 4;
                    EXIT/SL_HIT → full close at payload price, stored symbol.
  #3 position-check — exit with NO sub position → skipped_no_position (the
                    unwanted-short guard); entry with an already-open sub
                    position → skipped_already_in_position (summing removed).
  #5 lot-math     — lots_override validated (min 2, even-only, refuse odd);
                    qty = lots × REAL lot_size (injectable scrip-master);
                    CASH mode = SHARES min-2/even-only.
  #4 margin-safety — failed_insufficient_funds with a plain subscriber-facing
                    message (provider-mocked; no broker in paper).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.services.marketplace_fanout import (
    dispatch_subscriber_executions,
    fan_out_exit,
)

from tests.integration.test_marketplace_fanout_webhook import (
    _make_position,
    _seed_listing_and_subs,
    _run,
)


class _FakeScripMaster:
    """lookup/lot_size shaped like dhan._ScripMaster — injectable, no network."""

    def __init__(self, lot_sizes: dict[str, tuple[str, int]]):
        # symbol -> (security_id, lot_size)
        self._by_symbol = lot_sizes

    def lookup(self, symbol: str, segment: str) -> str | None:
        entry = self._by_symbol.get(symbol.upper())
        return entry[0] if entry else None

    def lot_size(self, security_id: str) -> int | None:
        for sid, ls in self._by_symbol.values():
            if sid == security_id:
                return ls
        return None


BSE_MASTER = _FakeScripMaster({"BSE-JUL2026-FUT": ("62395", 375)})


async def _mk_signal(maker, seed, *, action: str = "ENTRY",
                     symbol: str = "NIFTY", payload: dict | None = None):
    base: dict[str, Any] = {"action": action, "side": "long", "symbol": symbol,
                            "price": 100.0}
    if payload:
        base.update(payload)
    async with maker() as s:
        sig = StrategySignal(
            id=uuid.uuid4(), user_id=seed["user_id"],
            strategy_id=seed["strategy_id"], symbol=symbol, action=action,
            quantity=1, order_type="market", status="executed",
            raw_payload=base, received_at=datetime.now(UTC))
        s.add(sig)
        await s.commit()
        return sig


async def _strategy(maker, seed) -> Strategy:
    async with maker() as s:
        return await s.get(Strategy, seed["strategy_id"])


def _sub_rows(maker, strategy_id) -> list[StrategyPosition]:
    async def _load():
        async with maker() as s:
            return list((await s.execute(
                select(StrategyPosition).where(
                    StrategyPosition.strategy_id == strategy_id,
                    StrategyPosition.subscription_id.is_not(None)))).scalars())

    return _run(_load())


@pytest.fixture
def broker_spy(monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    return spy


# ═══════════════════════════════════════════════════════════════════════
# #1 MIRROR EXIT
# ═══════════════════════════════════════════════════════════════════════


def test_partial_mirrors_percentage_of_subscriber_qty(
    client, seed, db_session_maker, broker_spy
):
    """Owner 50% partial on a sub holding 8 lots → sub closes 4 (its OWN qty)."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    _run(_make_position(
        db_session_maker, user_id=refs[0].subscriber_id,
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=8, subscription_id=refs[0].subscription_id))

    sig = _run(_mk_signal(db_session_maker, seed, action="PARTIAL",
                          payload={"closePct": 50, "price": 110.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                action_kind="partial")

    results = _run(_go())
    assert [r.status for r in results] == ["filled"]
    assert results[0].quantity == 4

    row = _sub_rows(db_session_maker, seed["strategy_id"])[0]
    assert row.total_quantity == 8
    assert row.remaining_quantity == 4
    assert row.status == "partial"
    broker_spy.assert_not_called()


@pytest.mark.parametrize("kind", ["exit", "sl_hit"])
def test_exit_and_sl_close_fully_at_payload_price(
    client, seed, db_session_maker, broker_spy, kind
):
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    _run(_make_position(
        db_session_maker, user_id=refs[0].subscriber_id,
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=6, subscription_id=refs[0].subscription_id))
    # subscriber entry price is whatever the row carries; exit at 120
    sig = _run(_mk_signal(db_session_maker, seed, action=kind.upper(),
                          payload={"price": 120.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                action_kind=kind)

    results = _run(_go())
    assert [r.status for r in results] == ["filled"]
    assert results[0].quantity == 6

    row = _sub_rows(db_session_maker, seed["strategy_id"])[0]
    assert row.remaining_quantity == 0
    assert row.status == "closed"
    assert row.symbol == "NIFTY"          # STORED symbol — never re-resolved
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# #3 POSITION-CHECK
# ═══════════════════════════════════════════════════════════════════════


def test_exit_with_no_subscriber_position_skips(client, seed, db_session_maker):
    """The unwanted-short guard: no sub position → skipped_no_position, no row."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    sig = _run(_mk_signal(db_session_maker, seed, action="EXIT",
                          payload={"price": 120.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                action_kind="exit")

    results = _run(_go())
    assert [r.status for r in results] == ["skipped_no_position"]
    assert _sub_rows(db_session_maker, seed["strategy_id"]) == []


def test_entry_with_open_position_skips_not_sums(
    client, seed, db_session_maker, broker_spy
):
    """Summing is REMOVED: an already-open sub position skips the entry."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    _run(_make_position(
        db_session_maker, user_id=refs[0].subscriber_id,
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=refs[0].subscription_id))
    sig = _run(_mk_signal(db_session_maker, seed, action="ENTRY"))

    async def _go():
        async with db_session_maker() as s:
            return await dispatch_subscriber_executions(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                signal_hash=f"h-{uuid.uuid4().hex}")

    results = _run(_go())
    assert [r.status for r in results] == ["skipped_already_in_position"]
    row = _sub_rows(db_session_maker, seed["strategy_id"])[0]
    assert row.total_quantity == 2                 # UNCHANGED — not summed
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# #5 REAL LOT-MATH
# ═══════════════════════════════════════════════════════════════════════


def test_override_times_real_lot_size(client, seed, db_session_maker, broker_spy):
    """override 4 on BSE (lot 375) → 1500 qty."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0,
        lots_overrides=[4]))
    sig = _run(_mk_signal(db_session_maker, seed, symbol="BSE-JUL2026-FUT"))

    async def _go():
        async with db_session_maker() as s:
            return await dispatch_subscriber_executions(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                signal_hash=f"h-{uuid.uuid4().hex}", scrip_master=BSE_MASTER)

    results = _run(_go())
    assert [r.status for r in results] == ["filled"]
    assert results[0].quantity == 4 * 375
    row = _sub_rows(db_session_maker, seed["strategy_id"])[0]
    assert row.total_quantity == 1500
    broker_spy.assert_not_called()


@pytest.mark.parametrize("bad", [1, 3, 7])
def test_odd_or_below_min_override_refused(client, seed, db_session_maker, bad):
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0,
        lots_overrides=[bad]))
    sig = _run(_mk_signal(db_session_maker, seed))

    async def _go():
        async with db_session_maker() as s:
            return await dispatch_subscriber_executions(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                signal_hash=f"h-{uuid.uuid4().hex}")

    results = _run(_go())
    assert [r.status for r in results] == ["refused_size"]
    assert _sub_rows(db_session_maker, seed["strategy_id"]) == []


def test_cash_mode_shares_min2_even(client, seed, db_session_maker):
    """CASH strategy: shares semantics — default 2; odd override refused."""
    async def _to_cash():
        async with db_session_maker() as s:
            st = await s.get(Strategy, seed["strategy_id"])
            st.strategy_json = {"instrument_type": "cash", "entry_shares": 2}
            await s.commit()

    _run(_to_cash())
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=2, n_cancelled=0,
        lots_overrides=[None, 5]))     # None → entry_shares 2; 5 → odd, refused
    sig = _run(_mk_signal(db_session_maker, seed, symbol="RELIANCE"))

    async def _go():
        async with db_session_maker() as s:
            return await dispatch_subscriber_executions(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                signal_hash=f"h-{uuid.uuid4().hex}")

    results = _run(_go())
    by_sub = {r.subscription_id: r for r in results}
    assert by_sub[refs[0].subscription_id].status == "filled"
    assert by_sub[refs[0].subscription_id].quantity == 2       # SHARES
    assert by_sub[refs[1].subscription_id].status == "refused_size"
    rows = _sub_rows(db_session_maker, seed["strategy_id"])
    assert len(rows) == 1 and rows[0].total_quantity == 2


# ═══════════════════════════════════════════════════════════════════════
# #4 MARGIN-SAFETY shape
# ═══════════════════════════════════════════════════════════════════════


def test_margin_provider_clear_fail(client, seed, db_session_maker, broker_spy):
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    sig = _run(_mk_signal(db_session_maker, seed))

    async def _no_funds(*, subscriber, quantity, symbol):
        return False, ("Insufficient funds: your broker account needs "
                       "~₹2,20,000 free margin for this trade.")

    async def _go():
        async with db_session_maker() as s:
            return await dispatch_subscriber_executions(
                signal=sig, strategy=strat, subscribers=refs, db=s,
                signal_hash=f"h-{uuid.uuid4().hex}", margin_provider=_no_funds)

    results = _run(_go())
    assert [r.status for r in results] == ["failed_insufficient_funds"]
    assert "Insufficient funds" in (results[0].error or "")
    assert _sub_rows(db_session_maker, seed["strategy_id"]) == []
    broker_spy.assert_not_called()
