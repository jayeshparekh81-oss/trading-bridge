"""C1 — connection status receipts.

Runs against the throwaway Postgres (docker-compose-test.yml, localhost:5433) on a
scratch database built by the REAL alembic chain. Every write is rolled back.
"""

from __future__ import annotations

import ast
import os
import pathlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import encrypt_credential
from app.db.models.customer_lane import CustomerBrokerLink, CustomerLinkStatus
from app.domains.customer_lane.connection import is_connected

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

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


async def _customer(s: AsyncSession) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text(
        "INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"
    ), {"i": cid, "e": f"c1-{cid}@test.local"})
    await s.flush()
    return cid


async def _link(s: AsyncSession, cid: uuid.UUID, **kw) -> CustomerBrokerLink:
    link = CustomerBrokerLink(customer_id=cid, **kw)
    s.add(link)
    await s.flush()
    return link


async def test_never_connected_is_false(session):
    cid = await _customer(session)
    await _link(session, cid, status=CustomerLinkStatus.NEVER_CONNECTED)
    r = await is_connected(session, cid)
    assert r.connected is False and r.reason == "never_connected"


async def test_valid_is_true(session):
    cid = await _customer(session)
    now = datetime.now(UTC)
    await _link(session, cid, status=CustomerLinkStatus.CONNECTED,
                access_token_enc=encrypt_credential("tok"),
                token_expires_at=now + timedelta(hours=6), last_connected_at=now)
    r = await is_connected(session, cid)
    assert r.connected is True and r.reason == "connected"


async def test_expired_is_false(session):
    cid = await _customer(session)
    now = datetime.now(UTC)
    await _link(session, cid, status=CustomerLinkStatus.CONNECTED,
                access_token_enc=encrypt_credential("tok"),
                token_expires_at=now - timedelta(minutes=1), last_connected_at=now)
    r = await is_connected(session, cid)
    assert r.connected is False and r.reason == "token_expired"


async def test_missing_expiry_is_false(session):
    cid = await _customer(session)
    await _link(session, cid, status=CustomerLinkStatus.CONNECTED,
                access_token_enc=encrypt_credential("tok"), token_expires_at=None)
    r = await is_connected(session, cid)
    assert r.connected is False and r.reason == "unknown_expiry"


async def test_undecryptable_token_is_false(session):
    cid = await _customer(session)
    now = datetime.now(UTC)
    await _link(session, cid, status=CustomerLinkStatus.CONNECTED,
                access_token_enc="not-a-fernet-token",
                token_expires_at=now + timedelta(hours=6), last_connected_at=now)
    r = await is_connected(session, cid)
    assert r.connected is False and r.reason == "token_undecryptable"


async def test_anti_caching_same_process_sees_mutation(session):
    """MANDATORY. Mutate stored state, call again in the SAME process/session,
    assert the answer changed. Guards against a precomputed list or a cached batch."""
    cid = await _customer(session)
    now = datetime.now(UTC)
    link = await _link(session, cid, status=CustomerLinkStatus.CONNECTED,
                       access_token_enc=encrypt_credential("tok"),
                       token_expires_at=now + timedelta(hours=6), last_connected_at=now)
    first = await is_connected(session, cid)
    assert first.connected is True

    link.status = CustomerLinkStatus.DISABLED
    await session.flush()

    second = await is_connected(session, cid)
    assert second.connected is False, "is_connected returned a STALE answer"
    assert second.reason == "link_disabled"
    assert first.connected != second.connected


def test_ast_is_connected_is_the_single_source():
    """No module outside connection.py may compute connectedness from raw fields."""
    root = pathlib.Path("app")
    raw = {"access_token_enc", "token_expires_at", "last_connected_at"}
    offenders = []
    for py in root.rglob("*.py"):
        if py.as_posix().endswith("domains/customer_lane/connection.py"):
            continue
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        hit = names & raw
        if hit and "customer_lane" in py.as_posix():
            offenders.append((py.as_posix(), sorted(hit)))
    assert offenders == [], f"connectedness computed outside is_connected(): {offenders}"
