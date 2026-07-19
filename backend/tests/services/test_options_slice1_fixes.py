"""OPTIONS BRICK #4 — SLICE ① fixes 1+3 (audit landmines), test-first.

FIX 1 — ``_find_open_option_position`` owner-scoping: the owner's options exit
must NEVER grab a marketplace subscriber's mirror row (``subscription_id IS
NULL`` guard — same class as the kill-switch credential-scoping fix) and must
never pick a stale FUTURES row (option-leg symbol filter: ``%-CE`` / ``%-PE``).

FIX 3 — side vocabulary: option positions store ``side='buy'`` (the OrderSide
spelling every shared lookup / kill-switch / fan-out path already speaks), so
``direct_exit.get_open_position`` and ``position_lookup`` find option rows with
no lookup edits. Futures rows ('buy') unaffected by construction.

Reuses the Brick #3 executor harness (fixtures imported from
``test_options_executor`` — same sqlite engine, same seed shapes).
"""

# ruff: noqa: F811 — imported pytest fixtures (db/flag_on/broker_spy) are
# intentionally shadowed by test parameters; that IS the fixture-reuse pattern.
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.strategy_position import StrategyPosition
from app.services.options_executor import (
    execute_options_entry,
    execute_options_exit,
)

# Harness reuse — fixtures resolve by name from this module's namespace.
from tests.services.test_options_executor import (  # noqa: F401
    _REF_DATE,
    _entry_signal,
    _exit_signal,
    _FakeScripMaster,
    _option_scrip,
    _positions,
    _seed,
    broker_spy,
    db,
    flag_on,
)


async def _open_owner_position(db):
    """Seed + paper-enter: one OWNER option position (subscription_id NULL)."""
    user, strat = await _seed(db, is_paper=True)
    entry = await _entry_signal(db, user, strat, price=180.0)
    async with db() as s:
        res = await execute_options_entry(
            s, signal=entry, strategy=strat,
            scrip_master=_FakeScripMaster(_option_scrip()),
            reference_date=_REF_DATE)
    assert res.status == "executed", res.message
    return user, strat


async def _insert_row(db, *, user, strat, symbol, side, qty, subscription_id,
                      opened_at):
    async with db() as s:
        row = StrategyPosition(
            user_id=user.id,
            strategy_id=strat.id,
            broker_credential_id=strat.broker_credential_id,
            symbol=symbol,
            side=side,
            total_quantity=qty,
            remaining_quantity=qty,
            avg_entry_price=100,
            status="open",
            subscription_id=subscription_id,
            opened_at=opened_at,
        )
        s.add(row)
        await s.commit()
        return row.id


def _later():
    return datetime.now(UTC) + timedelta(minutes=5)


async def _row(db, row_id):
    async with db() as s:
        return await s.get(StrategyPosition, row_id)


# ═══════════════════════════════════════════════════════════════════════
# FIX 1 — owner exit scoping
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_owner_exit_never_grabs_subscriber_mirror_row(db, flag_on, broker_spy):
    """A NEWER subscriber mirror row (non-NULL subscription_id) must be
    invisible to the owner's options exit — owner closes ONLY its own row."""
    user, strat = await _open_owner_position(db)
    leg = _option_scrip().symbol
    sub_row_id = await _insert_row(
        db, user=user, strat=strat, symbol=leg, side="buy", qty=750,
        subscription_id=uuid4(), opened_at=_later())   # NEWEST — the trap

    sig = await _exit_signal(db, user, strat, action="EXIT", price=210.0)
    async with db() as s:
        res = await execute_options_exit(
            s, signal=sig, strategy=strat, action_kind="exit")

    assert res.status == "executed", res.message
    sub_row = await _row(db, sub_row_id)
    assert sub_row.status == "open"                    # subscriber UNTOUCHED
    assert sub_row.remaining_quantity == 750
    owner_rows = [p for p in await _positions(db, strat)
                  if p.subscription_id is None]
    assert len(owner_rows) == 1
    assert owner_rows[0].status == "closed"            # owner's OWN row closed
    broker_spy.assert_not_called()


@pytest.mark.asyncio
async def test_owner_exit_skips_stale_futures_row(db, flag_on, broker_spy):
    """A NEWER stale FUTURES row must not be picked — the exit closes the
    OPTION leg (symbol filter %-CE / %-PE)."""
    user, strat = await _open_owner_position(db)
    fut_row_id = await _insert_row(
        db, user=user, strat=strat, symbol="BSE-JUL2026-FUT", side="buy",
        qty=375, subscription_id=None, opened_at=_later())   # NEWEST — the trap

    sig = await _exit_signal(db, user, strat, action="EXIT", price=210.0)
    async with db() as s:
        res = await execute_options_exit(
            s, signal=sig, strategy=strat, action_kind="exit")

    assert res.status == "executed", res.message
    assert res.symbol.endswith("-CE")                  # closed the OPTION leg
    fut_row = await _row(db, fut_row_id)
    assert fut_row.status == "open"                    # futures row UNTOUCHED
    assert fut_row.remaining_quantity == 375
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# FIX 3 — side vocabulary: stored 'buy', shared lookups find option rows
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_entry_stores_buy_side(db, flag_on, broker_spy):
    """Option positions store side='buy' — the OrderSide spelling the shared
    exit machinery filters on (the leg IS a BUY: long premium)."""
    _user, strat = await _open_owner_position(db)
    pos = (await _positions(db, strat))[0]
    assert pos.side == "buy"
    broker_spy.assert_not_called()


@pytest.mark.asyncio
async def test_shared_lookups_find_option_position(db, flag_on, broker_spy):
    """direct_exit.get_open_position + position_lookup find the option row —
    including via the Pine 'long' vocabulary (normalized to 'buy')."""
    from app.services.direct_exit import get_open_position
    from app.services.position_lookup import find_open_position_by_strategy

    _user, strat = await _open_owner_position(db)
    leg = _option_scrip().symbol

    async with db() as s:
        via_direct_exit = await get_open_position(
            s, strategy_id=strat.id, symbol=leg, side="long")   # Pine vocab
        via_pin = await find_open_position_by_strategy(
            s, strategy_id=strat.id, side="long")
    assert via_direct_exit is not None and via_direct_exit.symbol == leg
    assert via_pin is not None and via_pin.symbol == leg
    broker_spy.assert_not_called()


@pytest.mark.asyncio
async def test_shared_lookups_still_find_futures_position(db, flag_on):
    """Futures rows (side='buy') keep working — both vocabularies resolve."""
    from app.services.direct_exit import get_open_position

    user, strat = await _seed(db, is_paper=True)
    await _insert_row(
        db, user=user, strat=strat, symbol="BSE-JUL2026-FUT", side="buy",
        qty=375, subscription_id=None, opened_at=datetime.now(UTC))

    async with db() as s:
        via_buy = await get_open_position(
            s, strategy_id=strat.id, symbol="BSE-JUL2026-FUT", side="buy")
        via_long = await get_open_position(
            s, strategy_id=strat.id, symbol="BSE-JUL2026-FUT", side="long")
    assert via_buy is not None and via_buy.symbol == "BSE-JUL2026-FUT"
    assert via_long is not None                       # long→buy normalization
