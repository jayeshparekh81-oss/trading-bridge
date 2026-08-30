"""The drift pass on an account that is ALSO traded by hand.

THE HAZARD, stated plainly. The drift design reads "broker holds less than we
stored" as "the customer closed it themselves". On the founder's Dhan account
that inference is routinely FALSE: he trades the same account manually
alongside the bot — extra futures lots, and option legs the bot never touches.
An over-eager drift pass would keep flipping his subscription to MANUAL on the
strength of trades that have nothing to do with the bot's position.

So this file proves the two shapes that must NEVER flip:

  1. broker holds MORE than stored  (he added lots by hand)
  2. broker holds UNRELATED legs    (his option legs; the bot trades futures)

plus the safety invariants that make the whole thing tolerable at all: an
unreachable broker is not drift, an ambiguous symbol is not drift, and nothing
in this path can place an order.

These are behavioural tests through the real pass — not unit tests of the
comparison — because the hazard lives in the composition: what the broker
returns, how the symbol matcher reads it, and what the flip rule then decides.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_position import StrategyPosition
from app.workers.subscriber_drift_pass import run_subscriber_drift_pass

STORED = "BSE-AUG2026-FUT"


@dataclass
class FakeBrokerPos:
    symbol: str
    quantity: int


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-hazard-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    # Create ONLY the tables these tests touch. Base.metadata.create_all fails
    # on SQLite once any JSONB-bearing model is registered (strategy_templates
    # .config_json), which happens as soon as another test in the same session
    # imports the marketplace router.
    tables = [
        Base.metadata.tables[t]
        for t in (
            "users",
            "marketplace_subscriptions",
            "strategy_positions",
            "audit_logs",
        )
        if t in Base.metadata.tables
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest.fixture
def drift_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "subscriber_drift_enabled", True)


async def _seed(maker, *, qty=400, symbol=STORED) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(), subscriber_id=uuid.uuid4(),
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"),
            execution_mode="auto", is_paper=False,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        s.add(StrategyPosition(
            strategy_id=uuid.uuid4(), subscription_id=sub.id,
            user_id=sub.subscriber_id, symbol=symbol,
            side="buy", total_quantity=qty, remaining_quantity=qty,
            status="open", opened_at=datetime.now(UTC),
            broker_credential_id=uuid.uuid4(),
        ))
        await s.commit()
        return sub.id


async def _mode(maker, sub_id) -> str:
    async with maker() as s:
        return (await s.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.id == sub_id))).scalar_one().execution_mode


def _fetch(positions):
    async def _f(_sid):
        return positions
    return _f


# ═══════════════════════════════════════════════════════════════════════
# HAZARD 1 — he holds MORE than the bot recorded
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize("broker_qty", [401, 600, 800, 4000])
async def test_broker_holds_more_never_flips(db_maker, drift_on, broker_qty):
    """He bought extra lots by hand. That is his own trade, not the bot's
    position disappearing. Flipping here would punish him for trading his own
    account."""
    sub_id = await _seed(db_maker, qty=400)

    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_fetch([FakeBrokerPos(STORED, broker_qty)]),
    )

    assert report.flipped == 0
    assert [d.reason for d in report.decisions] == ["no_drift"]
    assert await _mode(db_maker, sub_id) == "auto"


@pytest.mark.asyncio
async def test_broker_holds_exactly_stored_never_flips(db_maker, drift_on):
    sub_id = await _seed(db_maker, qty=400)
    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_fetch([FakeBrokerPos(STORED, 400)]),
    )
    assert report.flipped == 0
    assert await _mode(db_maker, sub_id) == "auto"


@pytest.mark.asyncio
async def test_a_short_leg_of_the_same_size_is_not_drift(db_maker, drift_on):
    """Dhan reports a short as a negative netQty. The comparison is on
    ABSOLUTE size — a -400 short is 400 held, not 0."""
    sub_id = await _seed(db_maker, qty=400)
    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_fetch([FakeBrokerPos(STORED, -400)]),
    )
    assert report.flipped == 0
    assert await _mode(db_maker, sub_id) == "auto"


# ═══════════════════════════════════════════════════════════════════════
# HAZARD 2 — his manual OPTION legs, which the bot never trades
# ═══════════════════════════════════════════════════════════════════════

#: Real shapes seen on his account alongside the bot's futures.
MANUAL_LEGS = [
    FakeBrokerPos("BSE-Aug2026-3200-CE", -400),
    FakeBrokerPos("BSE-Aug2026-3300-CE", -200),
    FakeBrokerPos("BSE-Sep2026-3400-PE", 200),
]


@pytest.mark.asyncio
async def test_unrelated_option_legs_alongside_the_bot_position_never_flip(
    db_maker, drift_on
):
    """The exact live shape: his option legs AND the bot's futures, together.
    The matcher must find the futures and ignore the options."""
    sub_id = await _seed(db_maker, qty=400)

    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_fetch(
            [*MANUAL_LEGS, FakeBrokerPos(STORED, 400)]
        ),
    )

    assert report.flipped == 0
    assert [d.reason for d in report.decisions] == ["no_drift"]
    assert await _mode(db_maker, sub_id) == "auto"


def test_option_legs_never_masquerade_as_the_futures_position():
    """An option must never SATISFY a futures position. If it did, a closed
    futures leg would look open and the customer would keep auto-trading
    something they no longer hold — the inverse failure, and the worse one."""
    from app.services.symbol_match import symbols_match

    for leg in MANUAL_LEGS:
        assert symbols_match(STORED, leg.symbol) is not True


@pytest.mark.asyncio
async def test_options_only_yields_unknown_on_his_account_not_a_flip(
    db_maker, drift_on
):
    """OPERATIONAL FINDING, documented deliberately.

    His real option spellings - BSE-Aug2026-3200-CE - do NOT parse:
    normalize_symbol returns None for them. So when the bot's futures is
    genuinely closed and only his manual option legs remain, the pass reports
    UNKNOWN rather than detecting the close.

    That is the SAFE direction (unknown is never drift, so he is never falsely
    flipped), but it is a real reduction in detection sensitivity on HIS
    account specifically, and it should be known rather than discovered later.
    Teaching the matcher his option format would restore sensitivity; nothing
    here depends on it, and it is not required for a fail-safe deploy.
    """
    sub_id = await _seed(db_maker, qty=400)

    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_fetch(MANUAL_LEGS),
    )

    assert report.flipped == 0
    assert report.unknown == 1
    assert report.decisions[0].reason == "broker_unavailable"
    assert await _mode(db_maker, sub_id) == "auto"


def test_the_bot_position_is_still_found_among_unparseable_legs():
    """The load-bearing half: an unparseable sibling must not hide a futures
    leg that IS present. find_matching_position returns on the first confident
    match, so his option legs cannot mask the bot's position."""
    from app.services.symbol_match import find_matching_position

    match, certain = find_matching_position(
        STORED, [*MANUAL_LEGS, FakeBrokerPos(STORED, 400)]
    )
    assert certain is True
    assert match is not None and match.quantity == 400


@pytest.mark.asyncio
async def test_an_unparseable_manual_leg_makes_it_unknown_not_flat(
    db_maker, drift_on
):
    """A leg we cannot parse is absence of evidence. It must produce UNKNOWN —
    never 'flat' — or one odd symbol on his account could flip a customer."""
    sub_id = await _seed(db_maker, qty=400)

    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_fetch([FakeBrokerPos("SOME-WEIRD-MANUAL-LEG", 100)]),
    )

    assert report.flipped == 0
    assert report.unknown == 1
    assert report.decisions[0].reason == "broker_unavailable"
    assert await _mode(db_maker, sub_id) == "auto"


# ═══════════════════════════════════════════════════════════════════════
# SAFETY INVARIANTS
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_broker_failure_is_never_drift(db_maker, drift_on):
    sub_id = await _seed(db_maker, qty=400)

    async def _boom(_sid):
        raise RuntimeError("dhan 500")

    report = await run_subscriber_drift_pass(
        (await _session(db_maker)), fetch_broker_positions=_boom
    )

    assert report.flipped == 0
    assert report.unknown == 1
    assert await _mode(db_maker, sub_id) == "auto"


@pytest.mark.asyncio
async def test_broker_timeout_is_never_drift(db_maker, drift_on):
    import asyncio

    sub_id = await _seed(db_maker, qty=400)

    async def _hang(_sid):
        await asyncio.sleep(30)

    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_hang,
        per_call_timeout=0.05,
        total_budget=0.5,
    )

    assert report.flipped == 0
    assert report.unknown == 1
    assert await _mode(db_maker, sub_id) == "auto"


@pytest.mark.asyncio
async def test_the_flip_is_one_way(db_maker, drift_on):
    """Once MANUAL, a later pass that sees the position back must NOT restore
    AUTO. Re-enabling is the customer's decision, deliberately."""
    sub_id = await _seed(db_maker, qty=400)

    # flip it
    await run_subscriber_drift_pass(
        (await _session(db_maker)), fetch_broker_positions=_fetch([])
    )
    assert await _mode(db_maker, sub_id) == "offline"

    # position "returns" — must stay manual
    report = await run_subscriber_drift_pass(
        (await _session(db_maker)),
        fetch_broker_positions=_fetch([FakeBrokerPos(STORED, 400)]),
    )

    assert report.flipped == 0
    assert await _mode(db_maker, sub_id) == "offline"


@pytest.mark.asyncio
async def test_the_pass_is_dormant_while_the_flag_is_off(db_maker):
    """No fixture: the flag is False by default, which is how it ships."""
    sub_id = await _seed(db_maker, qty=400)

    report = await run_subscriber_drift_pass(
        (await _session(db_maker)), fetch_broker_positions=_fetch([])
    )

    assert report.dormant is True
    assert report.checked == 0
    assert await _mode(db_maker, sub_id) == "auto"


async def _session(maker) -> AsyncSession:
    """A live session for the pass. Separate helper so each test reads cleanly."""
    return maker()


# ═══════════════════════════════════════════════════════════════════════
# 🔴 IT CANNOT PLACE AN ORDER
# ═══════════════════════════════════════════════════════════════════════


def _code_only(path) -> str:
    """Source with docstrings AND comments stripped.

    These modules describe the rules they obey - subscriber_notifier's own
    docstring explains why it must not call telegram_alerts, and the drift
    worker's says place_order is never called. Prose about a rule is not a
    violation of it, so the scans below read executable code only.
    """
    import re

    src = path.read_text(encoding="utf-8")
    src = re.sub(r"\x22{3}[\s\S]*?\x22{3}", "", src)
    src = re.sub(r"\x27{3}[\s\S]*?\x27{3}", "", src)
    return re.sub(r"#.*$", "", src, flags=re.M)


def test_no_order_placement_anywhere_in_the_drift_import_graph():
    """Static, over the whole path: worker + service + fetcher + task. If any
    of them could reach a broker WRITE, the 'reads and withholds' claim is
    false."""
    from pathlib import Path

    app = Path(__file__).resolve().parents[2] / "app"
    files = [
        app / "workers" / "subscriber_drift_pass.py",
        app / "services" / "subscriber_drift_service.py",
        app / "services" / "subscriber_broker_positions.py",
        app / "services" / "broker_position_batch.py",
        app / "tasks" / "subscriber_drift_tasks.py",
    ]
    forbidden = [
        "place_order", "place_strategy_orders", "cancel_order", "modify_order",
        "square_off", "exit_position", "order_router",
    ]
    for f in files:
        assert f.exists(), f"missing from the drift path: {f.name}"
        hits = [tok for tok in forbidden if tok in _code_only(f)]
        assert hits == [], f"{f.name} can reach order placement: {hits}"


def test_the_fetcher_never_calls_login():
    """Token refresh is the auth path's job. A drift read must not mutate
    session state as a side effect."""
    from pathlib import Path

    code = _code_only(
        Path(__file__).resolve().parents[2]
        / "app" / "services" / "subscriber_broker_positions.py"
    )
    assert ".login(" not in code


def test_subscriber_notifications_never_touch_the_operator_telegram():
    """The operator's global alert channel is for the OPERATOR. A subscriber
    event must never page it."""
    from pathlib import Path

    code = _code_only(
        Path(__file__).resolve().parents[2]
        / "app" / "services" / "subscriber_notifier.py"
    )
    assert "telegram_alerts" not in code
    assert "send_alert(" not in code
