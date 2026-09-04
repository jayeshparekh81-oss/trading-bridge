"""C7 — the MID-DAY JOIN RULE (Option A, founder-decided 2026-09-05).

A customer who connects mid-session does NOT join a position already open. They
participate only in signals emitted AFTER they connect. The mirror case — an exit
for a position they never entered — must be structurally impossible.
"""
from __future__ import annotations

import ast
import inspect
import os
import pathlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.brokers import customer_dhan as cd
from app.core.security import encrypt_credential
from app.db.models.customer_lane import CustomerBrokerLink, CustomerLinkStatus
from app.domains.customer_lane import participation as pr
from app.domains.customer_lane.status import MID_DAY_JOIN_RULE

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)

OPEN_TIME = datetime(2026, 9, 3, 3, 45, tzinfo=UTC)          # 09:15 IST, engine enters
LATE_CONNECT = datetime(2026, 9, 3, 5, 30, tzinfo=UTC)       # 11:00 IST, customer connects
NEXT_SIGNAL = datetime(2026, 9, 3, 7, 0, tzinfo=UTC)         # 12:30 IST, fresh signal
ENGINE_EXIT = datetime(2026, 9, 3, 6, 0, tzinfo=UTC)         # 11:30 IST, engine exits
ORDER = {"symbol": "BSE", "side": "BUY", "quantity": 1, "productType": "CNC"}


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DB_URL, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture(autouse=True)
def _armed(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_ORDER_ENABLED", "1")
    monkeypatch.delenv("CUSTOMER_LANE_KILL_ALL", raising=False)


async def _late_joiner(s) -> uuid.UUID:
    """A customer who connects at 11:00, well after the engine entered at 09:15."""
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c7-{cid}@test.local"})
    s.add(CustomerBrokerLink(
        customer_id=cid, status=CustomerLinkStatus.CONNECTED,
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=LATE_CONNECT + timedelta(hours=8),
        last_connected_at=LATE_CONNECT,
        proxy_url="http://proxy-c7:8080", assigned_static_ip="10.0.0.7"))
    await s.flush()
    return cid


# ── the rule itself ───────────────────────────────────────────────────────

async def test_the_rule_is_named_and_documented():
    assert pr.RULE_ID == "MID_DAY_JOIN_A"
    assert "Option A" in pr.RULE_TITLE
    assert "founder" in pr.RULE_DECIDED
    doc = pr.__doc__ or ""
    assert "does NOT join a position that is" in doc
    assert "OPENS a short" in doc, "the mirror case must be explained where the rule lives"


async def test_customer_copy_states_the_rule_plainly():
    assert MID_DAY_JOIN_RULE is pr.RULE_TEXT, "one source of wording, not two"
    for phrase in ("already running", "next fresh entry signal"):
        assert phrase in MID_DAY_JOIN_RULE


# ── ENTRY half ────────────────────────────────────────────────────────────

async def test_late_joiner_gets_NO_entry_for_the_already_open_position(session):
    """Engine holds a position opened at 09:15; customer connects at 11:00."""
    cid = await _late_joiner(session)
    lane = await cd.build_lane(session, cid, at=LATE_CONNECT + timedelta(minutes=1))
    with pytest.raises(cd.JoinRuleRefused) as exc:
        await lane.place_order(cid, ORDER, signal_emitted_at=OPEN_TIME)
    assert "connected_after_signal" in str(exc.value)


async def test_same_customer_DOES_take_the_next_fresh_signal(session):
    cid = await _late_joiner(session)
    lane = await cd.build_lane(session, cid, at=NEXT_SIGNAL)
    prepared = await lane.place_order(cid, ORDER, signal_emitted_at=NEXT_SIGNAL)
    assert prepared.customer_id == cid
    assert prepared.dry_run is True


async def test_entry_without_a_signal_time_is_refused_not_assumed(session):
    """The rule cannot be evaluated without the signal time, so it refuses."""
    cid = await _late_joiner(session)
    lane = await cd.build_lane(session, cid, at=NEXT_SIGNAL)
    with pytest.raises(cd.JoinRuleRefused) as exc:
        await lane.place_order(cid, ORDER)
    assert "signal_emitted_at" in str(exc.value)


# ── EXIT half: the mirror case ────────────────────────────────────────────

async def test_no_exit_order_for_a_position_the_customer_never_entered(session):
    """THE MIRROR CASE. The engine's position exits at 11:30 while this customer is
    connected but never entered. A 'sell to close' here would OPEN a short."""
    cid = await _late_joiner(session)
    lane = await cd.build_lane(session, cid, at=ENGINE_EXIT)
    with pytest.raises(cd.JoinRuleRefused) as exc:
        await lane.place_order(cid, {**ORDER, "side": "SELL"},
                               intent=pr.Intent.EXIT, closes_order_id=None)
    assert "never_entered" in str(exc.value)
    assert "OPEN a position" in str(exc.value) or "never_entered" in str(exc.value)


async def test_exit_IS_allowed_when_it_closes_the_customers_own_entry(session):
    cid = await _late_joiner(session)
    lane = await cd.build_lane(session, cid, at=ENGINE_EXIT)
    prepared = await lane.place_order(cid, {**ORDER, "side": "SELL"},
                                      intent=pr.Intent.EXIT,
                                      closes_order_id="cust-entry-123")
    assert prepared.customer_id == cid


async def test_structural_an_exit_cannot_be_built_without_naming_an_entry():
    """Not a behaviour test — a STRUCTURE test. The refusal is unconditional in the
    EXIT branch, so it cannot be reintroduced by a caller forgetting to check."""
    module = ast.parse(pathlib.Path("app/brokers/customer_dhan.py").read_text())
    place = next(n for n in ast.walk(module)
                 if isinstance(n, ast.AsyncFunctionDef) and n.name == "place_order")
    src = inspect.getsource(cd.CustomerOrderLane.place_order)
    calls = [n for n in ast.walk(place)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "may_exit"]
    assert calls, "place_order must consult may_exit for the EXIT intent"
    assert "closes_order_id" in src
    # and may_exit itself refuses on a falsy id, with no override parameter
    sig = inspect.signature(pr.may_exit)
    assert list(sig.parameters) == ["customer_entry_order_id"], \
        "may_exit must take nothing that could wave the rule through"
    assert pr.may_exit(customer_entry_order_id=None).participates is False
    assert pr.may_exit(customer_entry_order_id="").participates is False


# ── pure-rule unit checks ─────────────────────────────────────────────────

async def test_may_enter_boundary_is_inclusive_at_the_signal_instant():
    ok = pr.may_enter(connected_at=NEXT_SIGNAL, signal_emitted_at=NEXT_SIGNAL)
    assert ok.participates, "connected exactly at the signal instant still counts"
    late = pr.may_enter(connected_at=NEXT_SIGNAL + timedelta(seconds=1),
                        signal_emitted_at=NEXT_SIGNAL)
    assert not late.participates


async def test_never_connected_customer_takes_nothing():
    assert not pr.may_enter(connected_at=None, signal_emitted_at=NEXT_SIGNAL)
