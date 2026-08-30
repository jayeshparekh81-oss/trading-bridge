"""The reconciliation loop must resolve credentials the SAME WAY the executor does.

THE BUG THIS CLOSES. ``auto_login.py`` rotates the Dhan token nightly by
DEACTIVATING the old ``broker_credentials`` row and INSERTING a new one, without
updating ``strategies.broker_credential_id``. Since 2026-05-03 the executor has
handled that by falling back to the active credential for the same
``(user_id, broker_name)``. The reconciliation loop never learned the same
lesson: its ``is_active`` filter matched nothing the morning after any rotation,
so it woke every 60 seconds, found zero credentials, logged at DEBUG, and
returned.

The consequence was invisible from outside: TRADING kept working, because the
executor falls back. Only RECONCILIATION stopped. DB-vs-broker drift went
unwatched with nothing in the logs saying so. Found 2026-08-30 on the live
account with the FK pointing at a deactivated row.

That ASYMMETRY is the whole bug, so the last test in this file asserts the two
resolve identically. If one of them learns something the other does not, it
fails.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.workers.reconciliation_loop import (
    _list_credentials_backing_live_strategies,
)


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-recon-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    tables = [
        Base.metadata.tables[t]
        for t in ("users", "broker_credentials", "strategies")
        if t in Base.metadata.tables
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


async def _user(maker) -> User:
    async with maker() as s:
        u = User(email=f"u-{uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _cred(maker, *, user_id, active: bool, days_ago: int = 0, broker="dhan"):
    async with maker() as s:
        c = BrokerCredential(
            user_id=user_id, broker_name=broker, is_active=active,
            created_at=datetime.now(UTC) - timedelta(days=days_ago),
            client_id_enc="x", api_key_enc="x", api_secret_enc="x",
        )
        s.add(c)
        await s.commit()
        await s.refresh(c)
        return c


async def _strategy(maker, *, user_id, cred_id, is_paper=False, is_active=True):
    async with maker() as s:
        st = Strategy(
            user_id=user_id, name="BSE LTD Futures", is_active=is_active,
            is_paper=is_paper, broker_credential_id=cred_id,
            max_position_size=1000, allowed_symbols=[], entry_lots=4,
        )
        s.add(st)
        await s.commit()
        await s.refresh(st)
        return st


# ═══════════════════════════════════════════════════════════════════════
# 1. 🔴 THE ROTATION CASE — the one that was silently broken
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_rotated_credential_is_still_found(db_maker):
    """The exact live shape: the strategy's FK points at yesterday's
    DEACTIVATED row, and today's active row is a different id. Before the
    fallback this returned [] and the loop did nothing, forever."""
    u = await _user(db_maker)
    old = await _cred(db_maker, user_id=u.id, active=False, days_ago=1)
    new = await _cred(db_maker, user_id=u.id, active=True, days_ago=0)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id)  # stale FK

    async with db_maker() as s:
        found = await _list_credentials_backing_live_strategies(s)

    assert [c.id for c in found] == [new.id], "the rotated credential was not found"


@pytest.mark.asyncio
async def test_the_newest_active_credential_wins(db_maker):
    """Several rotations deep. The executor orders by created_at DESC and takes
    one; so must this, or the two would disagree about which is current."""
    u = await _user(db_maker)
    old = await _cred(db_maker, user_id=u.id, active=False, days_ago=5)
    await _cred(db_maker, user_id=u.id, active=True, days_ago=3)
    newest = await _cred(db_maker, user_id=u.id, active=True, days_ago=0)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id)

    async with db_maker() as s:
        found = await _list_credentials_backing_live_strategies(s)

    assert [c.id for c in found] == [newest.id]


@pytest.mark.asyncio
async def test_the_direct_path_still_works(db_maker):
    """An FK that still points at an active credential must not regress."""
    u = await _user(db_maker)
    live = await _cred(db_maker, user_id=u.id, active=True)
    await _strategy(db_maker, user_id=u.id, cred_id=live.id)

    async with db_maker() as s:
        found = await _list_credentials_backing_live_strategies(s)

    assert [c.id for c in found] == [live.id]


@pytest.mark.asyncio
async def test_no_duplicate_when_two_strategies_share_a_credential(db_maker):
    """Two live strategies, one rotated credential. It must appear ONCE, or the
    loop would reconcile the same broker account twice per tick."""
    u = await _user(db_maker)
    old = await _cred(db_maker, user_id=u.id, active=False, days_ago=1)
    new = await _cred(db_maker, user_id=u.id, active=True)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id)

    async with db_maker() as s:
        found = await _list_credentials_backing_live_strategies(s)

    assert [c.id for c in found] == [new.id]
    assert len(found) == 1


# ═══════════════════════════════════════════════════════════════════════
# 2. It must not over-reach
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paper_strategies_are_still_excluded(db_maker):
    """Paper has no broker side to reconcile against. The fallback must not
    smuggle a credential in through the back door."""
    u = await _user(db_maker)
    old = await _cred(db_maker, user_id=u.id, active=False, days_ago=1)
    await _cred(db_maker, user_id=u.id, active=True)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id, is_paper=True)

    async with db_maker() as s:
        assert await _list_credentials_backing_live_strategies(s) == []


@pytest.mark.asyncio
async def test_inactive_strategies_are_still_excluded(db_maker):
    u = await _user(db_maker)
    old = await _cred(db_maker, user_id=u.id, active=False, days_ago=1)
    await _cred(db_maker, user_id=u.id, active=True)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id, is_active=False)

    async with db_maker() as s:
        assert await _list_credentials_backing_live_strategies(s) == []


@pytest.mark.asyncio
async def test_another_users_active_credential_is_never_borrowed(db_maker):
    """🔴 The fallback is scoped to (user_id, broker_name). Reconciling one
    customer's DB against another's broker account would be the severe
    failure."""
    mine = await _user(db_maker)
    theirs = await _user(db_maker)
    my_old = await _cred(db_maker, user_id=mine.id, active=False, days_ago=1)
    await _cred(db_maker, user_id=theirs.id, active=True)  # NOT mine
    await _strategy(db_maker, user_id=mine.id, cred_id=my_old.id)

    async with db_maker() as s:
        assert await _list_credentials_backing_live_strategies(s) == []


@pytest.mark.asyncio
async def test_a_different_broker_is_never_substituted(db_maker):
    """A live Fyers credential must not stand in for a dead Dhan one."""
    u = await _user(db_maker)
    dead_dhan = await _cred(db_maker, user_id=u.id, active=False, days_ago=1, broker="dhan")
    await _cred(db_maker, user_id=u.id, active=True, broker="fyers")
    await _strategy(db_maker, user_id=u.id, cred_id=dead_dhan.id)

    async with db_maker() as s:
        assert await _list_credentials_backing_live_strategies(s) == []


@pytest.mark.asyncio
async def test_no_active_credential_at_all_yields_nothing(db_maker):
    """auto-login genuinely failed. Nothing to reconcile against — and the loop
    logs it loudly rather than pretending."""
    u = await _user(db_maker)
    old = await _cred(db_maker, user_id=u.id, active=False, days_ago=1)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id)

    async with db_maker() as s:
        assert await _list_credentials_backing_live_strategies(s) == []


# ═══════════════════════════════════════════════════════════════════════
# 3. 🔴 THE SYMMETRY TEST — this asymmetry is the whole bug
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_loop_and_executor_resolve_the_same_credential(db_maker):
    """Given identical state, both must pick the identical credential.

    This is the test that stops the bug reopening. For five years the executor
    knew about rotation and the loop did not, and nothing detected the gap
    because trading kept working. Now they are compared directly."""
    from app.services.strategy_executor import _load_credential

    u = await _user(db_maker)
    old = await _cred(db_maker, user_id=u.id, active=False, days_ago=2)
    await _cred(db_maker, user_id=u.id, active=True, days_ago=1)
    newest = await _cred(db_maker, user_id=u.id, active=True, days_ago=0)
    await _strategy(db_maker, user_id=u.id, cred_id=old.id)

    async with db_maker() as s:
        loop_creds = await _list_credentials_backing_live_strategies(s)
        executor_cred = await _load_credential(s, credential_id=old.id, user_id=u.id)

    assert len(loop_creds) == 1
    assert loop_creds[0].id == executor_cred.id == newest.id, (
        "the loop and the executor disagree about which credential is current — "
        "that asymmetry IS the 2026-08-30 bug"
    )


def test_both_use_the_same_fallback_shape():
    """Source-level: the same (user_id, broker_name, is_active) + newest-first
    resolution in both places, and the same WARNING event name so one grep
    finds both."""
    import inspect

    from app.services import strategy_executor as ex
    from app.workers import reconciliation_loop as rl

    loop_src = inspect.getsource(rl._list_credentials_backing_live_strategies)
    exec_src = inspect.getsource(ex._load_credential)

    for needle in ("user_id", "broker_name", "is_active", "created_at"):
        assert needle in loop_src, f"loop fallback missing {needle}"
        assert needle in exec_src, f"executor fallback missing {needle}"

    # the shared event name — the operator greps ONE string to find every
    # place a rotated FK is being worked around
    assert "credential_rotated" in loop_src
    assert "credential_rotated" in exec_src


def test_the_loop_does_not_repoint_the_fk():
    """The fix is code-only. Repointing strategies.broker_credential_id would be
    a data change good for exactly one night, until the next rotation."""
    import inspect

    from app.workers import reconciliation_loop as rl

    src = inspect.getsource(rl._list_credentials_backing_live_strategies)
    for forbidden in ("update(", "session.add", ".commit(", "broker_credential_id ="):
        assert forbidden not in src, f"the loop must not write: found {forbidden}"
