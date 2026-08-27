"""Step 6 — the subscriber execution log, and the guard it goes AROUND.

Three things are held here:

1. ``GET /api/marketplace/subscriptions/{id}/executions`` returns only the
   CALLER's executions. Customer A asking for customer B's subscription gets a
   404 — not B's rows, and not a 403 that would confirm the id exists.

2. ``GET /api/strategies/executions`` is left completely untouched: it still
   filters ``subscription_id IS NULL``, so a subscriber's row can never leak
   into the OWNER's execution list. Asserted behaviourally (an owner queries it
   with a subscriber row present) as well as at the source, because the whole
   point of a new endpoint was to avoid relaxing that filter.

3. ``paper_mode`` is DERIVED per row and TRI-STATE. The writers disagree on the
   key name — the confirm path writes ``paper_mode``, both fan-out paths write
   ``paper`` — so a reader that knew only one of them would report the other's
   simulated fills as not-simulated. That is the failure this file exists to
   prevent.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-exec-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


def _client(maker, user: User) -> TestClient:
    app = FastAPI()
    app.include_router(marketplace_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: user
    return TestClient(app)


async def _user(maker) -> User:
    async with maker() as s:
        u = User(email=f"u-{uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _listing(maker, *, title="Nifty Momentum Pro") -> MarketplaceListing:
    async with maker() as s:
        lst = MarketplaceListing(
            strategy_id=uuid.uuid4(), creator_id=uuid.uuid4(),
            title=title, description="d", price_inr=Decimal("0"),
            tags=[], status="published", subscriber_count=0, rating_count=0,
        )
        s.add(lst)
        await s.commit()
        await s.refresh(lst)
        return lst


async def _sub(maker, *, subscriber_id, listing_id=None) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=listing_id or uuid.uuid4(), subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"), execution_mode="offline",
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def _exec(
    maker, *, sub_id, broker_response, symbol="BSE-AUG2026-FUT",
    placed_at=None, signal_id=None, side="buy", qty=1,
) -> uuid.UUID:
    async with maker() as s:
        row = StrategyExecution(
            signal_id=signal_id or uuid.uuid4(),
            broker_credential_id=uuid.uuid4(),
            subscription_id=sub_id,
            leg_number=1, leg_role="entry", symbol=symbol, side=side,
            quantity=qty, order_type="market", price=Decimal("742.5000"),
            broker_order_id="PAPER-1", broker_status="complete",
            broker_response=broker_response,
            placed_at=placed_at or datetime.now(UTC),
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row.id


def _get(maker, user, sub_id, **params):
    return _client(maker, user).get(
        f"/api/marketplace/subscriptions/{sub_id}/executions", params=params
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. SCOPING — A never sees B
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_returns_the_callers_own_executions(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _exec(db_maker, sub_id=sub_id, broker_response={"paper_mode": True})

    r = _get(db_maker, u, sub_id)

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["subscription_id"] == str(sub_id)
    assert body["executions"][0]["symbol"] == "BSE-AUG2026-FUT"


@pytest.mark.asyncio
async def test_customer_a_cannot_read_customer_b_executions(db_maker):
    """The one that matters. B has a subscription with real rows in it; A asks
    for it by id and must get NOTHING — not the rows, and not a 403 that would
    confirm the subscription exists."""
    a = await _user(db_maker)
    b = await _user(db_maker)
    b_sub = await _sub(db_maker, subscriber_id=b.id)
    await _exec(db_maker, sub_id=b_sub, broker_response={"paper_mode": True},
                symbol="SECRET-B-SYMBOL")

    r = _get(db_maker, a, b_sub)

    assert r.status_code == 404
    assert "SECRET-B-SYMBOL" not in r.text
    # and B still sees their own
    assert _get(db_maker, b, b_sub).json()["count"] == 1


@pytest.mark.asyncio
async def test_unknown_subscription_is_404(db_maker):
    u = await _user(db_maker)
    assert _get(db_maker, u, uuid.uuid4()).status_code == 404


@pytest.mark.asyncio
async def test_only_this_subscriptions_rows(db_maker):
    """Two subscriptions owned by the SAME user must not bleed into each other."""
    u = await _user(db_maker)
    s1 = await _sub(db_maker, subscriber_id=u.id)
    s2 = await _sub(db_maker, subscriber_id=u.id)
    await _exec(db_maker, sub_id=s1, broker_response={"paper": True}, symbol="ONE")
    await _exec(db_maker, sub_id=s2, broker_response={"paper": True}, symbol="TWO")

    body = _get(db_maker, u, s1).json()

    assert [e["symbol"] for e in body["executions"]] == ["ONE"]


@pytest.mark.asyncio
async def test_newest_first_and_limit(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    now = datetime.now(UTC)
    await _exec(db_maker, sub_id=sub_id, broker_response={"paper": True},
                symbol="OLD", placed_at=now - timedelta(hours=2))
    await _exec(db_maker, sub_id=sub_id, broker_response={"paper": True},
                symbol="NEW", placed_at=now)

    assert [e["symbol"] for e in _get(db_maker, u, sub_id).json()["executions"]] == [
        "NEW", "OLD",
    ]
    assert _get(db_maker, u, sub_id, limit=1).json()["count"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 2. THE UNTOUCHED GUARD on /api/strategies/executions
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_owner_execution_list_still_excludes_subscriber_rows(db_maker):
    """BEHAVIOURAL. The owner of the strategy queries their own execution list
    while a subscriber row hangs off the owner's signal. The subscriber's row
    must not appear — that filter is what makes a separate endpoint necessary,
    so it is pinned here rather than merely eyeballed."""
    from app.api.strategy_signals import router as signals_router

    owner = await _user(db_maker)
    subscriber = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=subscriber.id)

    async with db_maker() as s:
        sig = StrategySignal(
            user_id=owner.id, strategy_id=uuid.uuid4(), raw_payload={},
            symbol="BSE-AUG2026-FUT", action="ENTRY", status="received",
            received_at=datetime.now(UTC),
        )
        s.add(sig)
        await s.commit()
        await s.refresh(sig)
        sig_id = sig.id

    # the OWNER's own execution (subscription_id NULL)
    async with db_maker() as s:
        s.add(StrategyExecution(
            signal_id=sig_id, broker_credential_id=uuid.uuid4(),
            subscription_id=None, leg_number=1, leg_role="entry",
            symbol="OWNER-ROW", side="buy", quantity=1, order_type="market",
            placed_at=datetime.now(UTC),
        ))
        await s.commit()
    # the SUBSCRIBER's execution, on the SAME signal
    await _exec(db_maker, sub_id=sub_id, signal_id=sig_id,
                broker_response={"paper_mode": True}, symbol="SUBSCRIBER-ROW")

    app = FastAPI()
    app.include_router(signals_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: owner
    body = TestClient(app).get("/api/strategies/executions").json()

    symbols = [e["symbol"] for e in body["executions"]]
    assert "OWNER-ROW" in symbols
    assert "SUBSCRIBER-ROW" not in symbols


def test_owner_execution_filter_is_still_in_the_source():
    """SOURCE-level companion to the behavioural test above. If someone deletes
    the filter, the behavioural test catches it; if someone reworks the query so
    the filter moves, this points straight at the line to re-read."""
    from pathlib import Path

    src = Path("app/api/strategy_signals.py").read_text()
    assert "StrategyExecution.subscription_id.is_(None)" in src


# ═══════════════════════════════════════════════════════════════════════
# 3. paper_mode — DERIVED, TRI-STATE, and never a constant
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["paper_mode", "paper"])
async def test_simulated_is_detected_under_either_writers_key(db_maker, key):
    """The confirm path writes ``paper_mode``; both fan-out paths write
    ``paper``. Reading only one would present the other's simulated fills as
    not-simulated."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _exec(db_maker, sub_id=sub_id, broker_response={key: True})

    assert _get(db_maker, u, sub_id).json()["executions"][0]["paper_mode"] is True


@pytest.mark.asyncio
async def test_a_real_row_reports_false_not_true(db_maker):
    """The label must not rot into a constant: an explicitly real row reports
    False, so the UI has something to render differently."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _exec(db_maker, sub_id=sub_id, broker_response={"paper_mode": False})

    assert _get(db_maker, u, sub_id).json()["executions"][0]["paper_mode"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {},                       # no flag at all
        {"source": "x"},          # other keys, no flag
        None,                     # column null
        {"paper_mode": "true"},   # a STRING, not a bool — must not read as True
        {"paper_mode": 1},        # truthy int — must not read as True
    ],
)
async def test_unknown_stays_unknown_never_guessed(db_maker, response):
    """Tri-state. A row that does not say gets ``None`` — collapsing that into
    False would let a simulated fill be presented as a broker fill."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _exec(db_maker, sub_id=sub_id, broker_response=response)

    assert _get(db_maker, u, sub_id).json()["executions"][0]["paper_mode"] is None


def test_every_writer_key_is_covered_by_the_reader():
    """Pins the reader's key tuple to what the writers ACTUALLY write. A new
    writer inventing a third key name fails here instead of silently shipping a
    mislabelled row."""
    import re
    from pathlib import Path

    from app.strategy_engine.api.marketplace import _PAPER_FLAG_KEYS

    # Collect EVERY boolean-literal key the writers set — not just ones whose
    # name happens to start with "paper". A writer marking simulation as
    # "simulated" or "is_mock" would slip straight past a name-based scan, and
    # its rows would then be reported as not-simulated.
    written: set[str] = set()
    sites = 0
    for path in (
        "app/services/marketplace_fanout.py",
        "app/strategy_engine/api/marketplace.py",
    ):
        src = Path(path).read_text()
        blocks = re.findall(r"broker_response=\{(.*?)\n\s*\},", src, re.S)
        sites += len(blocks)
        for block in blocks:
            written.update(re.findall(r'"(\w+)":\s*(?:True|False)', block))

    assert sites == 3, (
        f"expected 3 broker_response writers, found {sites}. A writer was "
        "added or removed — re-check that _execution_paper_mode knows how the "
        "new one marks a simulated fill."
    )
    unknown = written - set(_PAPER_FLAG_KEYS)
    assert not unknown, (
        f"writer sets boolean key(s) the reader does not know: {unknown}. If "
        "any of these marks a simulated fill, add it to _PAPER_FLAG_KEYS; the "
        "reader currently reports such rows as NOT simulated."
    )


# ═══════════════════════════════════════════════════════════════════════
# 4. Feed additions — listing_title + widened open_position
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_feed_carries_the_listing_title_not_a_uuid_stub(db_maker):
    u = await _user(db_maker)
    lst = await _listing(db_maker, title="Nifty Momentum Pro")
    await _sub(db_maker, subscriber_id=u.id, listing_id=lst.id)

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()

    assert body["subscriptions"][0]["listing_title"] == "Nifty Momentum Pro"


@pytest.mark.asyncio
async def test_feed_title_is_none_when_the_listing_is_gone(db_maker):
    """Optional, so a dangling listing_id still serialises rather than 500ing."""
    u = await _user(db_maker)
    await _sub(db_maker, subscriber_id=u.id, listing_id=uuid.uuid4())

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()

    assert body["subscriptions"][0]["listing_title"] is None


@pytest.mark.asyncio
async def test_open_position_carries_the_widened_detail(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    opened = datetime.now(UTC) - timedelta(hours=3)
    async with db_maker() as s:
        s.add(StrategyPosition(
            user_id=u.id, strategy_id=uuid.uuid4(),
            broker_credential_id=uuid.uuid4(), subscription_id=sub_id,
            symbol="BSE-AUG2026-FUT", side="long",
            total_quantity=10, remaining_quantity=4,
            avg_entry_price=Decimal("742.5000"),
            stop_loss_price=Decimal("730.0000"),
            target_price=Decimal("770.0000"),
            status="partial", opened_at=opened,
        ))
        await s.commit()

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    pos = body["subscriptions"][0]["open_position"]

    assert pos["side"] == "long"
    assert pos["remaining_quantity"] == 4
    # exact text, not a re-rounded float
    assert pos["avg_entry_price"] == "742.5000"
    assert pos["stop_loss_price"] == "730.0000"
    assert pos["target_price"] == "770.0000"
    assert pos["opened_at"]
    # the pre-existing alias the shipped Close button reads is UNCHANGED
    assert pos["quantity"] == 4


@pytest.mark.asyncio
async def test_widened_fields_are_optional_not_required(db_maker):
    """A position with nothing but symbol + qty must still serialise — the
    fields are additive, so a sparse row cannot 500 the whole feed."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    async with db_maker() as s:
        s.add(StrategyPosition(
            user_id=u.id, strategy_id=uuid.uuid4(),
            broker_credential_id=uuid.uuid4(), subscription_id=sub_id,
            symbol="X", side="long", total_quantity=1, remaining_quantity=1,
            status="open", opened_at=datetime.now(UTC),
        ))
        await s.commit()

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()
    pos = body["subscriptions"][0]["open_position"]

    assert pos["avg_entry_price"] is None
    assert pos["stop_loss_price"] is None
    assert pos["quantity"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 5. The position card's OWN label (adversarial-review finding #1)
# ═══════════════════════════════════════════════════════════════════════
#
# The position card is the ALWAYS-VISIBLE surface — the execution log sits
# behind an expand, this does not. Symbol + side + entry + stop + target is
# exactly what a live broker position looks like, so it needs the same derived
# flag the log rows carry.


async def _position(maker, *, user_id, sub_id, signal_id=None, symbol="X"):
    async with maker() as s:
        pos = StrategyPosition(
            user_id=user_id, strategy_id=uuid.uuid4(),
            broker_credential_id=uuid.uuid4(), subscription_id=sub_id,
            signal_id=signal_id, symbol=symbol, side="long",
            total_quantity=1, remaining_quantity=1,
            status="open", opened_at=datetime.now(UTC),
        )
        s.add(pos)
        await s.commit()


def _pos_of(body, sub_id):
    for row in body["subscriptions"]:
        if row["id"] == str(sub_id):
            return row["open_position"]
    return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"paper_mode": True}, True),
        ({"paper": True}, True),
        ({"paper_mode": False}, False),
        ({}, None),
    ],
)
async def test_position_paper_mode_is_derived_from_its_opening_execution(
    db_maker, response, expected
):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    sig_id = uuid.uuid4()
    await _position(db_maker, user_id=u.id, sub_id=sub_id, signal_id=sig_id)
    await _exec(db_maker, sub_id=sub_id, signal_id=sig_id,
                broker_response=response)

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()

    assert _pos_of(body, sub_id)["paper_mode"] is expected


@pytest.mark.asyncio
async def test_position_with_no_locatable_execution_stays_unknown(db_maker):
    """Unknown, never guessed — the UI then claims neither."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _position(db_maker, user_id=u.id, sub_id=sub_id, signal_id=uuid.uuid4())

    body = _client(db_maker, u).get("/api/marketplace/subscriptions/me").json()

    assert _pos_of(body, sub_id)["paper_mode"] is None


@pytest.mark.asyncio
async def test_position_flag_never_comes_from_another_subscription(db_maker):
    """SCOPING. B's execution shares A's signal id (same underlying strategy
    signal, which is the normal case). A's position must NOT pick up B's row."""
    a = await _user(db_maker)
    b = await _user(db_maker)
    a_sub = await _sub(db_maker, subscriber_id=a.id)
    b_sub = await _sub(db_maker, subscriber_id=b.id)
    sig_id = uuid.uuid4()

    await _position(db_maker, user_id=a.id, sub_id=a_sub, signal_id=sig_id)
    # only B has an execution for that signal, and it says REAL
    await _exec(db_maker, sub_id=b_sub, signal_id=sig_id,
                broker_response={"paper_mode": False})

    body = _client(db_maker, a).get("/api/marketplace/subscriptions/me").json()

    # A's position must stay unknown, NOT inherit B's False
    assert _pos_of(body, a_sub)["paper_mode"] is None


# ═══════════════════════════════════════════════════════════════════════
# 6. Truncation is never silent (adversarial-review finding)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_truncated_is_flagged_when_there_is_more_history(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    now = datetime.now(UTC)
    for i in range(3):
        await _exec(db_maker, sub_id=sub_id, broker_response={"paper": True},
                    placed_at=now - timedelta(minutes=i))

    body = _get(db_maker, u, sub_id, limit=2).json()

    assert body["count"] == 2
    assert body["truncated"] is True


@pytest.mark.asyncio
async def test_not_truncated_when_the_log_fits(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    await _exec(db_maker, sub_id=sub_id, broker_response={"paper": True})

    body = _get(db_maker, u, sub_id, limit=2).json()

    assert body["count"] == 1
    assert body["truncated"] is False


@pytest.mark.asyncio
async def test_exactly_at_the_limit_is_not_reported_as_truncated(db_maker):
    """Off-by-one: N rows with limit=N is COMPLETE, not cut short."""
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id)
    now = datetime.now(UTC)
    for i in range(2):
        await _exec(db_maker, sub_id=sub_id, broker_response={"paper": True},
                    placed_at=now - timedelta(minutes=i))

    body = _get(db_maker, u, sub_id, limit=2).json()

    assert body["count"] == 2
    assert body["truncated"] is False


def test_the_manual_close_gap_is_documented_not_hidden():
    """The Close button's primitive writes no execution row. That file is on
    the protected kill-switch path, so the gap is not silently fixable here —
    it must at least be STATED, in the endpoint and in the UI."""
    from pathlib import Path

    api = Path("app/strategy_engine/api/marketplace.py").read_text()
    assert "kill_subscriber" in api and "WHAT THIS LOG DOES NOT CONTAIN" in api
    # and the primitive genuinely still writes none, so the note stays true
    ks = Path("app/services/kill_switch_service.py").read_text()
    assert "StrategyExecution" not in ks, (
        "kill_switch_service now writes executions — the UI note claiming "
        "manual closes are absent from the log is no longer true."
    )
