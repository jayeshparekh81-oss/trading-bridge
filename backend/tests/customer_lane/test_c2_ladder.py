"""C2 — reminder ladder receipts. One test per numbered rule in the spec."""

from __future__ import annotations

import importlib
import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import encrypt_credential
from app.db.models.customer_lane import (
    CustomerBrokerLink,
    CustomerLinkStatus,
    CustomerNotificationLog,
    LadderStep,
)

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)
TDAY = date(2026, 9, 3)          # a Thursday — a trading day
SAT = date(2026, 9, 5)           # a Saturday


@pytest.fixture(autouse=True)
def _arm_ladder(monkeypatch):
    """The flag defaults OFF; tests arm it explicitly. test_flag_defaults_off proves
    the default separately."""
    monkeypatch.setenv("CUSTOMER_LANE_LADDER_ENABLED", "1")


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DB_URL, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


async def _customer(s: AsyncSession, connected: bool = False,
                    at: datetime | None = None) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c2-{cid}@test.local"})
    now = at or datetime.now(UTC)
    if connected:
        link = CustomerBrokerLink(
            customer_id=cid, status=CustomerLinkStatus.CONNECTED,
            access_token_enc=encrypt_credential("tok"),
            token_expires_at=now + timedelta(hours=8), last_connected_at=now)
    else:
        link = CustomerBrokerLink(customer_id=cid,
                                  status=CustomerLinkStatus.NEVER_CONNECTED)
    s.add(link)
    await s.flush()
    return cid


async def _connect(s: AsyncSession, cid: uuid.UUID, at: datetime) -> None:
    link = (await s.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == cid))).scalar_one()
    link.status = CustomerLinkStatus.CONNECTED
    link.access_token_enc = encrypt_credential("tok")
    link.token_expires_at = at + timedelta(hours=8)
    link.last_connected_at = at
    await s.flush()


async def _rows(s: AsyncSession, cid: uuid.UUID) -> list[str]:
    return [r.step.value for r in (await s.execute(
        select(CustomerNotificationLog)
        .where(CustomerNotificationLog.customer_id == cid)
        .order_by(CustomerNotificationLog.sent_at))).scalars()]


# ---------------------------------------------------------------- rule 1
async def test_rule1_fresh_check_per_customer_at_execution_time(session):
    """A customer who becomes connected BETWEEN job start and their turn is skipped."""
    from app.domains.customer_lane import ladder
    ladder = importlib.reload(ladder)
    base = datetime(2026, 9, 3, 2, 15, tzinfo=UTC)
    a = await _customer(session, connected=False)
    b = await _customer(session, connected=False)

    # b connects AFTER the job would have built any up-front list
    await _connect(session, b, base)
    outs = await ladder.run_step(session, LadderStep.R1, trading_date=TDAY, now=base)
    by = {o.customer_id: o for o in outs}
    assert by[a].sent is True
    assert by[b].sent is False and by[b].reason == "cancelled_connected"


# ---------------------------------------------------------------- rule 2
@pytest.mark.parametrize("connect_at_step,expect", [
    (None, ["R1", "R2", "CALL", "RED"]),      # never connects
    ("before_R1", []),                         # connected before 07:45
    ("after_R1", ["R1"]),                      # connected 07:50
    ("after_R2", ["R1", "R2"]),                # connected 08:52
    ("after_CALL", ["R1", "R2", "CALL"]),      # connected 09:02
])
async def test_rule2_cancel_rule_all_entry_points(session, connect_at_step, expect):
    from app.domains.customer_lane import ladder
    ladder = importlib.reload(ladder)
    t = {"R1": datetime(2026, 9, 3, 2, 15, tzinfo=UTC),
         "R2": datetime(2026, 9, 3, 3, 0, tzinfo=UTC),
         "CALL": datetime(2026, 9, 3, 3, 25, tzinfo=UTC),
         "RED": datetime(2026, 9, 3, 3, 35, tzinfo=UTC)}
    cid = await _customer(session, connected=(connect_at_step == "before_R1"),
                          at=t["R1"] - timedelta(minutes=30))
    order = ["R1", "R2", "CALL", "RED"]
    for step_name in order:
        if connect_at_step == "after_R1" and step_name == "R2":
            await _connect(session, cid, t["R1"] + timedelta(minutes=5))
        if connect_at_step == "after_R2" and step_name == "CALL":
            await _connect(session, cid, t["R2"] + timedelta(minutes=22))
        if connect_at_step == "after_CALL" and step_name == "RED":
            await _connect(session, cid, t["CALL"] + timedelta(minutes=7))
        await ladder.run_step(session, LadderStep[step_name],
                              trading_date=TDAY, now=t[step_name])
    assert await _rows(session, cid) == expect


# ---------------------------------------------------------------- rule 3
async def test_rule3_idempotent_same_step_twice_is_one_row(session):
    from app.domains.customer_lane import ladder
    ladder = importlib.reload(ladder)
    now = datetime(2026, 9, 3, 2, 15, tzinfo=UTC)
    cid = await _customer(session, connected=False)
    await ladder.run_step(session, LadderStep.R1, trading_date=TDAY, now=now)
    second = await ladder.run_step(session, LadderStep.R1, trading_date=TDAY, now=now)
    assert await _rows(session, cid) == ["R1"]
    assert [o for o in second if o.customer_id == cid][0].sent is False


# ---------------------------------------------------------------- rule 4
async def test_rule4_trading_day_guard_silent_on_weekend(session):
    from app.domains.customer_lane import ladder
    ladder = importlib.reload(ladder)
    cid = await _customer(session, connected=False)
    outs = await ladder.run_step(session, LadderStep.R1, trading_date=SAT,
                                 now=datetime(2026, 9, 5, 2, 15, tzinfo=UTC))
    assert outs == []
    assert await _rows(session, cid) == []


# ---------------------------------------------------------------- rule 5
async def test_rule5_confirm_on_connect_is_idempotent(session):
    from app.domains.customer_lane import ladder
    ladder = importlib.reload(ladder)
    now = datetime(2026, 9, 3, 3, 0, tzinfo=UTC)
    cid = await _customer(session, connected=True, at=now)
    a = await ladder.confirm_connection(session, cid, trading_date=TDAY)
    b = await ladder.confirm_connection(session, cid, trading_date=TDAY)
    assert a.sent is True and b.sent is False
    assert await _rows(session, cid) == ["CONFIRM"]


# ---------------------------------------------------------------- rule 6
async def test_rule6_red_is_loud_and_names_the_consequence(session):
    from app.domains.customer_lane.ladder import MESSAGES
    red = MESSAGES[LadderStep.RED]
    assert "NOT CONNECTED" in red.upper()
    assert "NO TRADES WILL BE PLACED" in red.upper()
    assert len(red) > 80, "RED must be explicit, not a terse code"


# ---------------------------------------------------------------- flag default
def test_flag_defaults_off(monkeypatch):
    for k in ("CUSTOMER_LANE_LADDER_ENABLED", "CUSTOMER_LANE_ORDER_ENABLED",
              "CUSTOMER_LANE_EGRESS_VERIFY_ENABLED", "CUSTOMER_LANE_BEAT_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    from app.domains.customer_lane import config as c
    cfg = c.load()
    assert cfg.ladder_enabled is False
    assert cfg.order_lane_enabled is False
    assert cfg.egress_verify_enabled is False
    assert cfg.beat_enabled is False


def test_beat_entries_registered_but_disarmed(monkeypatch):
    """Schedules must EXIST in code and install NOTHING while the flag is off."""
    from celery import Celery
    from app.tasks import customer_lane_tasks as clt

    monkeypatch.delenv("CUSTOMER_LANE_BEAT_ENABLED", raising=False)
    app = Celery("probe")
    app.conf.beat_schedule = {}
    installed = clt.register_beat_entries(app)
    assert installed == {}, "beat must install nothing while disarmed"
    assert app.conf.beat_schedule == {}
    assert set(clt.LADDER_BEAT) == {"customer-lane-r1", "customer-lane-r2",
                                    "customer-lane-call", "customer-lane-red"}

    monkeypatch.setenv("CUSTOMER_LANE_BEAT_ENABLED", "1")
    app2 = Celery("probe2")
    app2.conf.beat_schedule = {}
    armed = clt.register_beat_entries(app2)
    assert set(armed) == set(clt.LADDER_BEAT), "arming must install all four rungs"
