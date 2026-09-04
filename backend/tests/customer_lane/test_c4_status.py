"""C4 — the status surface, and the mid-day join rule."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import encrypt_credential
from app.db.models.customer_lane import (CustomerBrokerLink, CustomerLinkStatus,
                                         LadderStep)
from app.domains.customer_lane.channels import send
from app.domains.customer_lane.status import (CUSTOMER_COPY, JoinEligibility,
                                              MID_DAY_JOIN_RULE, board_summary,
                                              customer_line, founder_board,
                                              join_eligibility)

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

TDAY = date(2026, 9, 3)
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


async def _customer(s, *, connected_at=None) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c4-{cid}@test.local"})
    link = CustomerBrokerLink(customer_id=cid, status=CustomerLinkStatus.NEVER_CONNECTED)
    if connected_at is not None:
        link.status = CustomerLinkStatus.CONNECTED
        link.access_token_enc = encrypt_credential("tok")
        link.token_expires_at = connected_at + timedelta(hours=8)
        link.last_connected_at = connected_at
    s.add(link)
    await s.flush()
    return cid


BEFORE_OPEN = datetime(2026, 9, 3, 2, 30, tzinfo=UTC)   # 08:00 IST
AFTER_OPEN = datetime(2026, 9, 3, 5, 30, tzinfo=UTC)    # 11:00 IST
MIDDAY = datetime(2026, 9, 3, 6, 0, tzinfo=UTC)         # 11:30 IST


async def test_connected_before_open_is_full_day(session):
    cid = await _customer(session, connected_at=BEFORE_OPEN)
    line = await customer_line(session, cid, trading_date=TDAY, now=MIDDAY)
    assert line.eligibility is JoinEligibility.FULL_DAY
    assert line.connected is True


async def test_connected_after_open_is_next_signal_only(session):
    """THE MONEY RULE: a late joiner is never dropped into a running position."""
    cid = await _customer(session, connected_at=AFTER_OPEN)
    line = await customer_line(session, cid, trading_date=TDAY, now=MIDDAY)
    assert line.eligibility is JoinEligibility.NEXT_SIGNAL_ONLY
    assert line.connected is True
    assert MID_DAY_JOIN_RULE in line.message


async def test_not_connected_is_not_today(session):
    cid = await _customer(session)
    line = await customer_line(session, cid, trading_date=TDAY, now=MIDDAY)
    assert line.eligibility is JoinEligibility.NOT_TODAY
    assert "NOT connected" in line.message


async def test_unknown_join_time_falls_to_the_safe_side():
    from app.domains.customer_lane.connection import ConnectionStatus
    st = ConnectionStatus(True, "connected", None, MIDDAY, uuid.uuid4(), None, None)
    assert join_eligibility(st, TDAY) is JoinEligibility.NEXT_SIGNAL_ONLY


async def test_customer_copy_never_promises_trades_to_the_disconnected(session):
    msg = CUSTOMER_COPY[JoinEligibility.NOT_TODAY]
    assert "No trades will be placed" in msg
    for e in JoinEligibility:
        assert CUSTOMER_COPY[e].strip() != ""


async def test_board_puts_broken_customers_first(session):
    good = await _customer(session, connected_at=BEFORE_OPEN)
    late = await _customer(session, connected_at=AFTER_OPEN)
    bad = await _customer(session)
    board = await founder_board(session, [good, late, bad],
                                trading_date=TDAY, now=MIDDAY)
    assert [l.eligibility for l in board] == [JoinEligibility.NOT_TODAY,
                                              JoinEligibility.NEXT_SIGNAL_ONLY,
                                              JoinEligibility.FULL_DAY]
    assert board[0].customer_id == bad
    assert board_summary(board) == {"NOT_TODAY": 1, "NEXT_SIGNAL_ONLY": 1,
                                    "FULL_DAY": 1, "total": 3}


async def test_board_shows_which_reminders_went_out(session):
    cid = await _customer(session)
    await send(session, cid, LadderStep.R1, "r1", trading_date=TDAY)
    await send(session, cid, LadderStep.R2, "r2", trading_date=TDAY)
    line = await customer_line(session, cid, trading_date=TDAY, now=MIDDAY)
    assert line.reminders_sent == ["R1", "R2"]


async def test_status_surface_writes_nothing(session):
    """A read model must not mutate. Prove the session is clean after a board read."""
    cid = await _customer(session, connected_at=BEFORE_OPEN)
    await session.commit()
    await founder_board(session, [cid], trading_date=TDAY, now=MIDDAY)
    assert not session.new and not session.dirty and not session.deleted
