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


def test_rung_times_are_the_founder_decided_defaults(monkeypatch):
    """Run G: the rungs were moved OFF the pre-market job grid.

    The 09:05 IST slot is the one that matters — scrip-master-warm-premarket runs
    there so the day's first F&O signal never pays a ~9s CSV download inside the
    order path. Nothing of ours may share its minute.
    """
    for k in ("CUSTOMER_LANE_R1", "CUSTOMER_LANE_R2", "CUSTOMER_LANE_CALL",
              "CUSTOMER_LANE_RED", "CUSTOMER_LANE_LINK_CUTOFF"):
        monkeypatch.delenv(k, raising=False)
    from app.domains.customer_lane import config as lane_config
    cfg = lane_config.load()
    assert (cfg.r1_at.hour, cfg.r1_at.minute) == (7, 45)
    assert (cfg.r2_at.hour, cfg.r2_at.minute) == (8, 32)
    assert (cfg.call_at.hour, cfg.call_at.minute) == (8, 57)
    assert (cfg.red_at.hour, cfg.red_at.minute) == (9, 7)


def test_rungs_are_ordered_and_all_land_before_the_open(monkeypatch):
    for k in ("CUSTOMER_LANE_R1", "CUSTOMER_LANE_R2", "CUSTOMER_LANE_CALL",
              "CUSTOMER_LANE_RED", "CUSTOMER_LANE_LINK_CUTOFF"):
        monkeypatch.delenv(k, raising=False)
    from app.domains.customer_lane import config as lane_config
    cfg = lane_config.load()
    assert cfg.r1_at < cfg.r2_at < cfg.call_at < cfg.red_at < cfg.link_cutoff_at
    assert (cfg.link_cutoff_at.hour, cfg.link_cutoff_at.minute) == (9, 15)


def test_no_rung_lands_on_an_occupied_pre_market_minute(monkeypatch):
    """The estate's pre-market grid, in IST. Every :00/:05/:10... slot is taken by
    subscriber-drift-pass alone, so a rung must never sit on a 5-minute boundary."""
    for k in ("CUSTOMER_LANE_R1", "CUSTOMER_LANE_R2", "CUSTOMER_LANE_CALL",
              "CUSTOMER_LANE_RED"):
        monkeypatch.delenv(k, raising=False)
    from app.domains.customer_lane import config as lane_config
    cfg = lane_config.load()
    occupied_ist = {
        (8, 0): "refresh_scrip_master",
        (8, 30): "auto_login + pnl-reconciler-intraday",
        (8, 35): "auto_login_fallback",
        (8, 50): "morning_state_brief + run_daily",
        (8, 55): "calendar_health",
        (9, 0): "order_feed_wrapper + refresh_scrip_master + daily-pnl-reset",
        (9, 5): "scrip-master-warm-premarket + preopen_forever",
        (9, 10): "morning_heartbeat",
        (9, 20): "bar_stability_probe_v3 + morning_watchdog_v2",
    }
    for name, t in (("R1", cfg.r1_at), ("R2", cfg.r2_at),
                    ("CALL", cfg.call_at), ("RED", cfg.red_at)):
        key = (t.hour, t.minute)
        assert key not in occupied_ist, (
            f"{name} at {t.strftime('%H:%M')} IST collides with {occupied_ist.get(key)}")
        # subscriber-drift-pass runs every 5 minutes but only from 08:30 IST
        # (UTC hours 3-10), so the 5-minute-grid rule applies from then on. R1 at
        # 07:45 is on a 5-minute boundary and is nonetheless clear.
        if (t.hour, t.minute) >= (8, 30):
            assert t.minute % 5 != 0, (
                f"{name} at {t.strftime('%H:%M')} sits on the 5-minute grid that "
                "subscriber-drift-pass occupies every slot of from 08:30 IST")
