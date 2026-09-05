"""C10 — the ladder delegates to the estate's notification service.

No second transport. The CALL rung has no voice transport anywhere in the estate
(H1), so it REFUSES rather than quietly becoming a message.
"""
from __future__ import annotations

import ast
import os
import pathlib
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.customer_lane import (CustomerBrokerLink, CustomerLinkStatus,
                                         CustomerNotificationLog, LadderStep)
from app.domains.customer_lane import channels as ch

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

TDAY = date(2026, 9, 3)
NOW = datetime(2026, 9, 3, 2, 15, tzinfo=UTC)
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
    monkeypatch.delenv("CUSTOMER_LANE_CHANNELS_LIVE", raising=False)


async def _customer(s) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c10-{cid}@test.local"})
    s.add(CustomerBrokerLink(customer_id=cid,
                             status=CustomerLinkStatus.NEVER_CONNECTED))
    await s.flush()
    return cid


class _FakeService:
    """Stands in for notification_service. Records; sends nothing."""

    def __init__(self, result=None):
        self.calls: list[tuple] = []
        self._result = result or {"email": "sent", "telegram": "skipped"}

    async def send(self, user_id, event_type, context, db):
        self.calls.append((user_id, event_type, context))
        return dict(self._result)


# ── routing ───────────────────────────────────────────────────────────────

async def test_each_rung_routes_to_its_intended_channel():
    assert ch.STEP_CHANNEL[LadderStep.R1] == "message"
    assert ch.STEP_CHANNEL[LadderStep.R2] == "message"
    assert ch.STEP_CHANNEL[LadderStep.CALL] == "voice"
    assert ch.STEP_CHANNEL[LadderStep.RED] == "message"
    assert ch.CHANNELS["message"].available() is True
    assert ch.CHANNELS["voice"].available() is False


async def test_message_rungs_delegate_to_the_existing_service(session, monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    fake = _FakeService()
    import app.services.notification_service as ns
    monkeypatch.setattr(ns, "notification_service", fake)

    cid = await _customer(session)
    res = await ch.send(session, cid, LadderStep.R1, "reconnect please",
                        trading_date=TDAY, sent_at=NOW)
    assert res.sent is True
    assert res.outcome.startswith("SENT:")
    assert len(fake.calls) == 1
    user_id, event, _ctx = fake.calls[0]
    assert user_id == cid
    assert event == "broker_session_expired", "R1 reuses the EXISTING event type"


async def test_RED_uses_its_own_event_type_not_the_reconnect_one(session, monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    fake = _FakeService()
    import app.services.notification_service as ns
    monkeypatch.setattr(ns, "notification_service", fake)

    cid = await _customer(session)
    await ch.send(session, cid, LadderStep.RED, "no trades today",
                  trading_date=TDAY, sent_at=NOW)
    _u, event, _c = fake.calls[0]
    assert event == "customer_lane_no_trades_today"
    assert ch.STEP_EVENT[LadderStep.RED] != ch.STEP_EVENT[LadderStep.R1]


async def test_RED_wording_states_plainly_that_nothing_will_be_traded():
    root = pathlib.Path("app/templates/notifications")
    html = (root / "email" / "customer_lane_no_trades_today.html").read_text()
    txt = (root / "telegram" / "customer_lane_no_trades_today.txt").read_text()
    for body in (html, txt):
        assert "no trades will be placed for you today" in body.lower()


# ── the CALL rung refuses ─────────────────────────────────────────────────

async def test_CALL_rung_REFUSES_and_never_falls_back_to_a_message(session, monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    fake = _FakeService()
    import app.services.notification_service as ns
    monkeypatch.setattr(ns, "notification_service", fake)

    cid = await _customer(session)
    res = await ch.send(session, cid, LadderStep.CALL, "calling you",
                        trading_date=TDAY, sent_at=NOW)
    assert res.sent is False
    assert res.outcome == "UNAVAILABLE"
    assert fake.calls == [], "a refused CALL must NOT become a message"

    row = (await session.execute(select(CustomerNotificationLog).where(
        CustomerNotificationLog.customer_id == cid,
        CustomerNotificationLog.step == LadderStep.CALL))).scalar_one()
    assert row.outcome == "UNAVAILABLE", "the gap is recorded, not silent"


async def test_the_refusal_explains_why_a_fallback_would_be_a_lie():
    with pytest.raises(ch.ChannelUnavailable) as exc:
        import asyncio
        asyncio.get_event_loop()
        raise ch.ChannelUnavailable(
            ch.VOICE_CHANNEL.why)  # the message the channel raises with
    assert "no voice/telephony transport exists" in str(exc.value)


async def test_unavailable_steps_names_exactly_the_CALL_rung():
    missing = ch.unavailable_steps()
    assert list(missing) == [LadderStep.CALL]
    assert missing[LadderStep.CALL] == "voice"


# ── nothing is sent while disarmed ────────────────────────────────────────

async def test_disarmed_channel_sends_nothing_and_does_not_even_call_the_service(
    session, monkeypatch
):
    fake = _FakeService()
    import app.services.notification_service as ns
    monkeypatch.setattr(ns, "notification_service", fake)

    cid = await _customer(session)
    res = await ch.send(session, cid, LadderStep.R1, "hello",
                        trading_date=TDAY, sent_at=NOW)
    assert res.outcome == "STUBBED"
    assert fake.calls == [], "disarmed must not reach the service at all"


async def test_channels_live_defaults_off(monkeypatch):
    monkeypatch.delenv("CUSTOMER_LANE_CHANNELS_LIVE", raising=False)
    from app.domains.customer_lane import config as c
    assert c.load().channels_live is False


# ── structure: no second transport ────────────────────────────────────────

def test_channels_module_contains_no_transport_of_its_own():
    """Structure, not substring. The module NAMES vendors in prose to explain they do
    not exist; what matters is that it IMPORTS none of them and calls none of them."""
    src = pathlib.Path("app/domains/customer_lane/channels.py").read_text()
    tree = ast.parse(src)

    transports = {"boto3", "httpx", "requests", "smtplib", "aiosmtplib", "urllib",
                  "urllib.request", "twilio", "telegram", "socket", "aiohttp"}
    all_imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            all_imports |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            all_imports.add(n.module.split(".")[0])
    leaked = all_imports & transports
    assert not leaked, f"channels.py imports a transport directly: {leaked}"

    # And no bare URL literal that could be a transport endpoint.
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            assert "://" not in n.value, f"channels.py embeds a URL: {n.value!r}"

    # MODULE-LEVEL imports only (tree.body, not ast.walk): the service IS imported,
    # but deliberately inside deliver(), so a disarmed lane never loads a transport.
    module_level = {n.module for n in tree.body
                    if isinstance(n, ast.ImportFrom) and n.module}
    assert "app.services.notification_service" not in module_level, (
        "the service must be imported INSIDE deliver(), not at module scope")

    nested = {n.module for n in ast.walk(tree)
              if isinstance(n, ast.ImportFrom) and n.module} - module_level
    assert "app.services.notification_service" in nested, (
        "deliver() must delegate to the existing service")
