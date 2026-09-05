"""C11 — the CALL rung is unwired BY DECISION, and nothing promises a phone call.

Founder decision (run J): no voice transport will be built now. The ladder runs
three rungs — R1, R2, RED. CALL refuses and the refusal stays visible.
"""
from __future__ import annotations

import os
import pathlib
import re
import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.customer_lane import (CustomerBrokerLink, CustomerLinkStatus,
                                         CustomerNotificationLog, LadderStep)
from app.domains.customer_lane import channels as ch
from app.domains.customer_lane import config as lane_config
from app.domains.customer_lane import preflight as pf
from app.domains.customer_lane.ladder import MESSAGES

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

TDAY = date(2026, 9, 3)
NOW = datetime(2026, 9, 3, 3, 27, tzinfo=UTC)
DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DB_URL, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CUSTOMER_LANE_UNWIRED_RUNGS", "CUSTOMER_LANE_CHANNELS_LIVE"):
        monkeypatch.delenv(k, raising=False)


# ── unwired BY DECISION, not by accident ──────────────────────────────────

async def test_CALL_is_accepted_as_unwired_BY_DEFAULT():
    """The documented default state, so preflight does not need a special env var
    set by hand on go-live day."""
    assert lane_config.load().unwired_rungs == frozenset({"CALL"})


async def test_preflight_is_ready_with_CALL_unwired_and_nothing_else_missing():
    r = pf.check(date(2026, 9, 5))
    assert r.ready is True, r.detail


async def test_a_DIFFERENT_rung_losing_its_transport_still_REFUSES(monkeypatch):
    """The distinction that matters: CALL was decided about; R2 would not have been."""
    monkeypatch.setitem(ch.CHANNELS, "message",
                        ch.UnavailableChannel("message", "provider removed in a refactor"))
    try:
        r = pf.check(date(2026, 9, 5))
        assert r.ready is False
        assert r.reason == "rung_transport_missing"
        assert "R1->message" in r.detail
        assert "nobody decided about them" in r.detail
        assert "CALL" not in r.detail.split("nobody decided about them")[1].split(".")[0]
    finally:
        monkeypatch.setitem(ch.CHANNELS, "message", ch.MESSAGE_CHANNEL)


async def test_a_blanket_accept_is_not_possible(monkeypatch):
    """Acceptance is per-rung. There is no 'accept anything missing' switch."""
    monkeypatch.setenv("CUSTOMER_LANE_UNWIRED_RUNGS", "CALL")
    monkeypatch.setitem(ch.CHANNELS, "message",
                        ch.UnavailableChannel("message", "gone"))
    try:
        assert pf.check(date(2026, 9, 5)).ready is False
    finally:
        monkeypatch.setitem(ch.CHANNELS, "message", ch.MESSAGE_CHANNEL)


# ── the refusal stays visible ─────────────────────────────────────────────

async def test_CALL_still_records_UNAVAILABLE_rather_than_vanishing(session, monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    cid = uuid.uuid4()
    await session.execute(
        text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
        {"i": cid, "e": f"c11-{cid}@test.local"})
    session.add(CustomerBrokerLink(customer_id=cid,
                                   status=CustomerLinkStatus.NEVER_CONNECTED))
    await session.flush()

    res = await ch.send(session, cid, LadderStep.CALL, MESSAGES[LadderStep.CALL],
                        trading_date=TDAY, sent_at=NOW)
    assert res.sent is False and res.outcome == "UNAVAILABLE"
    row = (await session.execute(select(CustomerNotificationLog).where(
        CustomerNotificationLog.customer_id == cid))).scalar_one()
    assert row.outcome == "UNAVAILABLE", "the gap must stay in the log"


async def test_CALL_still_cannot_degrade_into_a_message():
    assert ch.STEP_CHANNEL[LadderStep.CALL] == "voice"
    assert ch.CHANNELS["voice"].available() is False
    assert isinstance(ch.CHANNELS["voice"], ch.UnavailableChannel)


# ── NOTHING promises a phone call ─────────────────────────────────────────

CALL_PROMISE = re.compile(
    r"calling you|we(?:'ll| will) call|give you a call|expect a call|"
    r"a call is coming|phone call from us|we(?:'ll| will) (?:phone|ring) you",
    re.I)


async def test_no_ladder_message_promises_a_phone_call():
    for step, text_ in MESSAGES.items():
        assert not CALL_PROMISE.search(text_), f"{step.value} promises a call: {text_!r}"


async def test_no_customer_facing_string_in_the_repo_promises_a_phone_call():
    """Whole-repo sweep, kept as a test so it cannot regress. Engineering prose that
    EXPLAINS the absence of a call is fine; a promise TO A CUSTOMER is not."""
    root = pathlib.Path("..")
    surfaces = [
        *(root / "backend/app/templates/notifications").rglob("*"),
        *(root / "backend/app/domains/customer_lane").glob("*.py"),
        *(root / "frontend/src/lib/email/templates").glob("*.ts"),
    ]
    offenders = []
    for f in surfaces:
        if not f.is_file():
            continue
        for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if CALL_PROMISE.search(line):
                stripped = line.strip()
                # explanatory prose in a comment/docstring is not a promise
                if stripped.startswith(("#", "*", "//")) or "would be told" in line:
                    continue
                offenders.append(f"{f}:{i}: {stripped[:90]}")
    assert offenders == [], "customer-facing promise of a call:\n" + "\n".join(offenders)
