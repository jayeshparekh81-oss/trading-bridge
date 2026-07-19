"""OPTIONS BRICK #4 — SLICE ② expiry sweep, test-first.

An expired option leg must not survive as an open paper position forever
(audit gap: no beat job; ``expiry_day_force_close`` declared but unconsumed).
``sweep_expired_options`` finds OPEN ``%-CE``/``%-PE`` positions whose expiry
has passed (15:30 IST expiry-day cutoff), derives expiry MASTER-FIRST
(``scrip_master.expiry_for`` — the same SEM_EXPIRY_DATE source the entry used)
with a SYMBOL-PARSE fallback (DDMONYYYY token — expired contracts drop out of
a refreshed master, the BSE-MAY delisting lesson), and paper-closes them with
``exit_reason='expired'`` and NO fabricated settlement premium (final_pnl is
left as accrued — real settlement lands with the premium-join slice).

Scoping: owner AND subscriber option rows both sweep (an expired option is
expired for everyone; each row closes independently). Futures/cash rows can
never match (SQL ``%-CE``/``%-PE`` filter). Flag OFF → dormant no-op.
Idempotent — closed rows never re-match.
"""

# ruff: noqa: F811 — imported pytest fixtures are shadowed by test params (the
# fixture-reuse pattern).
from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import uuid4

import pytest

from app.db.models.strategy_position import StrategyPosition
from app.services.options_expiry_sweep import (
    derive_option_expiry,
    sweep_expired_options,
)
from tests.services.test_options_executor import (  # noqa: F401
    _seed,
    db,
    flag_on,
)

# now = Sunday 2026-07-19 12:00 IST (06:30 UTC) unless a test overrides.
_NOW = datetime(2026, 7, 19, 6, 30, tzinfo=UTC)
_EXPIRED = "BSE-16JUL2026-2400-CE"          # expired Thu 16 Jul < now
_NOT_EXPIRED = "BSE-23JUL2026-2400-PE"      # next weekly, still alive
_UNPARSEABLE = "BSEWEIRD2400-CE"            # -CE row but no date token


class _MasterWithExpiry:
    """Fake scrip master exposing only what the sweep uses."""

    def __init__(self, mapping: dict[str, date] | None = None) -> None:
        self._m = mapping or {}

    def expiry_for(self, symbol: str, segment: str) -> date | None:
        return self._m.get(symbol.upper())


async def _insert(db, *, user, strat, symbol, subscription_id=None,
                  status="open", qty=1500):
    async with db() as s:
        row = StrategyPosition(
            user_id=user.id, strategy_id=strat.id,
            broker_credential_id=strat.broker_credential_id,
            symbol=symbol, side="buy",
            total_quantity=qty, remaining_quantity=qty,
            avg_entry_price=180, status=status,
            subscription_id=subscription_id,
            opened_at=datetime(2026, 7, 13, 5, 0, tzinfo=UTC),
        )
        s.add(row)
        await s.commit()
        return row.id


async def _get(db, row_id):
    async with db() as s:
        return await s.get(StrategyPosition, row_id)


async def _sweep(db, **kw):
    async with db() as s:
        return await sweep_expired_options(s, now=kw.pop("now", _NOW), **kw)


# ═══════════════════════════════════════════════════════════════════════
# Expiry derivation
# ═══════════════════════════════════════════════════════════════════════


def test_derive_master_first_then_parse_fallback():
    master = _MasterWithExpiry({_EXPIRED: date(2026, 7, 16)})
    # Master hit — authoritative SEM_EXPIRY_DATE.
    assert derive_option_expiry(_EXPIRED, scrip_master=master) == date(2026, 7, 16)
    # Master miss (delisted) → symbol-parse fallback.
    assert derive_option_expiry(_EXPIRED, scrip_master=None) == date(2026, 7, 16)
    assert derive_option_expiry(_NOT_EXPIRED, scrip_master=None) == date(2026, 7, 23)
    # Neither source → None (caller logs + skips).
    assert derive_option_expiry(_UNPARSEABLE, scrip_master=None) is None


# ═══════════════════════════════════════════════════════════════════════
# Sweep behaviour
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_expired_closed_not_expired_left(db, flag_on):
    user, strat = await _seed(db, is_paper=True)
    expired_id = await _insert(db, user=user, strat=strat, symbol=_EXPIRED)
    alive_id = await _insert(db, user=user, strat=strat, symbol=_NOT_EXPIRED)

    res = await _sweep(db)

    assert res["status"] == "swept"
    assert res["closed"] == 1 and res["skipped_not_expired"] == 1
    expired = await _get(db, expired_id)
    assert expired.status == "closed"
    assert expired.remaining_quantity == 0
    assert expired.exit_reason == "expired"
    # NO fabricated settlement premium — final_pnl untouched (premium-join slice).
    assert expired.action_history[-1]["action"] == "expiry_sweep"
    alive = await _get(db, alive_id)
    assert alive.status == "open" and alive.remaining_quantity == 1500


@pytest.mark.asyncio
async def test_expiry_day_cutoff_1530_ist(db, flag_on):
    """ON expiry day: before 15:30 IST → left; at/after 15:30 IST → closed."""
    user, strat = await _seed(db, is_paper=True)
    row_id = await _insert(db, user=user, strat=strat, symbol=_EXPIRED)
    expiry_day = date(2026, 7, 16)

    before = datetime.combine(expiry_day, time(9, 55), tzinfo=UTC)   # 15:25 IST
    res1 = await _sweep(db, now=before)
    assert res1["closed"] == 0
    assert (await _get(db, row_id)).status == "open"

    after = datetime.combine(expiry_day, time(10, 5), tzinfo=UTC)    # 15:35 IST
    res2 = await _sweep(db, now=after)
    assert res2["closed"] == 1
    assert (await _get(db, row_id)).status == "closed"


@pytest.mark.asyncio
async def test_futures_and_cash_rows_never_touched(db, flag_on):
    user, strat = await _seed(db, is_paper=True)
    fut_id = await _insert(db, user=user, strat=strat, symbol="BSE-JUL2026-FUT")
    cash_id = await _insert(db, user=user, strat=strat, symbol="NSE:BSE")

    res = await _sweep(db)

    assert res["closed"] == 0 and res["checked"] == 0   # CE/PE filter: not even seen
    assert (await _get(db, fut_id)).status == "open"
    assert (await _get(db, cash_id)).status == "open"


@pytest.mark.asyncio
async def test_unparseable_symbol_logged_skipped_sweep_continues(db, flag_on):
    user, strat = await _seed(db, is_paper=True)
    weird_id = await _insert(db, user=user, strat=strat, symbol=_UNPARSEABLE)
    expired_id = await _insert(db, user=user, strat=strat, symbol=_EXPIRED)

    res = await _sweep(db)

    assert res["skipped_unparseable"] == 1
    assert res["closed"] == 1                            # the parseable one closed
    assert (await _get(db, weird_id)).status == "open"   # skipped, not crashed
    assert (await _get(db, expired_id)).status == "closed"


@pytest.mark.asyncio
async def test_idempotent_second_run_closes_nothing(db, flag_on):
    user, strat = await _seed(db, is_paper=True)
    await _insert(db, user=user, strat=strat, symbol=_EXPIRED)

    first = await _sweep(db)
    second = await _sweep(db)

    assert first["closed"] == 1
    assert second["closed"] == 0 and second["checked"] == 0   # closed rows gone


@pytest.mark.asyncio
async def test_flag_off_dormant_noop(db):
    user, strat = await _seed(db, is_paper=True)
    row_id = await _insert(db, user=user, strat=strat, symbol=_EXPIRED)

    res = await _sweep(db)

    assert res["status"] == "dormant"
    assert (await _get(db, row_id)).status == "open"     # untouched


@pytest.mark.asyncio
async def test_subscriber_row_also_swept_scoping_explicit(db, flag_on):
    """Owner AND subscriber expired option rows BOTH close — an expired option
    is expired for everyone; each row closes independently."""
    user, strat = await _seed(db, is_paper=True)
    owner_id = await _insert(db, user=user, strat=strat, symbol=_EXPIRED)
    sub_id = await _insert(db, user=user, strat=strat, symbol=_EXPIRED,
                           subscription_id=uuid4())

    res = await _sweep(db)

    assert res["closed"] == 2
    assert (await _get(db, owner_id)).status == "closed"
    assert (await _get(db, sub_id)).status == "closed"


@pytest.mark.asyncio
async def test_live_strategy_row_defensively_skipped(db, flag_on):
    """A LIVE strategy's option row (impossible today — executor refuses live)
    must NOT be silently paper-closed: logged + skipped."""
    user, strat = await _seed(db, is_paper=False)        # LIVE strategy
    row_id = await _insert(db, user=user, strat=strat, symbol=_EXPIRED)

    res = await _sweep(db)

    assert res["skipped_live"] == 1 and res["closed"] == 0
    assert (await _get(db, row_id)).status == "open"


# ═══════════════════════════════════════════════════════════════════════
# Celery wiring
# ═══════════════════════════════════════════════════════════════════════


def test_beat_schedule_and_task_registered():
    from app.tasks.celery_app import celery_app

    entry = celery_app.conf.beat_schedule.get("options-expiry-sweep")
    assert entry is not None
    assert entry["task"] == "app.tasks.options_expiry_tasks.sweep_expired_option_positions"
    assert "app.tasks.options_expiry_tasks" in celery_app.conf.include
