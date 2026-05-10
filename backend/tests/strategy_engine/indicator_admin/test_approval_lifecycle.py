"""Approval queue + override service-layer lifecycle tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.auth.roles import ROLE_ADMIN, ROLE_CREATOR
from app.db.base import Base
from app.db.models.user import User
from app.strategy_engine.indicator_admin.approval import (
    QueueConflictError,
    QueueStateError,
    decide_request,
    enqueue_request,
    list_my_requests,
    list_pending_queue,
    withdraw_request,
)
from app.strategy_engine.indicator_admin.overrides import (
    create_direct_override,
    get_indicator_history,
    list_active_overrides,
)
from app.strategy_engine.indicator_admin.resolver import (
    resolve_effective_status,
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-approval-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with maker() as s:
        yield s
    await engine.dispose()


async def _seed(s: AsyncSession, *, role: str) -> User:
    u = User(
        email=f"u{uuid.uuid4().hex[:8]}@x",
        password_hash="x",
        is_active=True,
        role=role,
    )
    s.add(u)
    await s.commit()
    await s.refresh(u)
    return u


# ─── enqueue_request ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enqueue_creates_pending_row(session: AsyncSession) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    row = await enqueue_request(
        session,
        indicator_id="kama",
        requested_status="active",
        reason="50+ strategies use this — production ready",
        requester_id=creator.id,
    )
    assert row.status == "pending"
    assert row.indicator_id == "kama"
    assert row.requested_status == "active"


@pytest.mark.asyncio
async def test_enqueue_rejects_duplicate_pending(
    session: AsyncSession,
) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    await enqueue_request(
        session,
        indicator_id="kama",
        requested_status="active",
        reason="first request",
        requester_id=creator.id,
    )
    await session.commit()
    with pytest.raises(QueueConflictError):
        await enqueue_request(
            session,
            indicator_id="kama",
            requested_status="active",
            reason="second request",
            requester_id=creator.id,
        )


@pytest.mark.asyncio
async def test_enqueue_rejects_invalid_requested_status(
    session: AsyncSession,
) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    with pytest.raises(ValueError):
        await enqueue_request(
            session,
            indicator_id="kama",
            requested_status="experimental",  # not allowed via queue
            reason="x",
            requester_id=creator.id,
        )


# ─── decide_request ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_creates_override_and_links_back(
    session: AsyncSession,
) -> None:
    """Approving a request flips the queue row to 'approved' AND
    creates an override row that the queue row points back to."""
    creator = await _seed(session, role=ROLE_CREATOR)
    admin = await _seed(session, role=ROLE_ADMIN)
    queued = await enqueue_request(
        session,
        indicator_id="kama",
        requested_status="active",
        reason="ready",
        requester_id=creator.id,
    )
    await session.commit()

    decided = await decide_request(
        session,
        queue_id=queued.id,
        decision="approve",
        decision_by_user_id=admin.id,
        notes="LGTM — usage stats look solid",
    )
    await session.commit()
    assert decided.status == "approved"
    assert decided.resulting_override_id is not None

    # Resolver now picks up the override.
    eff = await resolve_effective_status(session, "kama")
    assert eff.status == "active"
    assert eff.source == "override"


@pytest.mark.asyncio
async def test_reject_does_not_create_override(
    session: AsyncSession,
) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    admin = await _seed(session, role=ROLE_ADMIN)
    queued = await enqueue_request(
        session,
        indicator_id="kama",
        requested_status="active",
        reason="ready",
        requester_id=creator.id,
    )
    await session.commit()

    decided = await decide_request(
        session,
        queue_id=queued.id,
        decision="reject",
        decision_by_user_id=admin.id,
        notes="Need more usage data first",
    )
    await session.commit()
    assert decided.status == "rejected"
    assert decided.resulting_override_id is None

    eff = await resolve_effective_status(session, "kama")
    assert eff.status == "coming_soon"
    assert eff.source == "registry_default"


@pytest.mark.asyncio
async def test_decide_already_decided_raises(
    session: AsyncSession,
) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    admin = await _seed(session, role=ROLE_ADMIN)
    queued = await enqueue_request(
        session,
        indicator_id="kama",
        requested_status="active",
        reason="x",
        requester_id=creator.id,
    )
    await session.commit()
    await decide_request(
        session,
        queue_id=queued.id,
        decision="approve",
        decision_by_user_id=admin.id,
        notes="ok",
    )
    await session.commit()
    with pytest.raises(QueueStateError):
        await decide_request(
            session,
            queue_id=queued.id,
            decision="reject",
            decision_by_user_id=admin.id,
            notes="changed mind",
        )


# ─── withdraw_request ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_withdraw_by_requester(session: AsyncSession) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    queued = await enqueue_request(
        session,
        indicator_id="kama",
        requested_status="active",
        reason="x",
        requester_id=creator.id,
    )
    await session.commit()
    withdrawn = await withdraw_request(
        session, queue_id=queued.id, requester_id=creator.id
    )
    await session.commit()
    assert withdrawn.status == "withdrawn"


@pytest.mark.asyncio
async def test_withdraw_by_other_user_raises(
    session: AsyncSession,
) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    other = await _seed(session, role=ROLE_CREATOR)
    queued = await enqueue_request(
        session,
        indicator_id="kama",
        requested_status="active",
        reason="x",
        requester_id=creator.id,
    )
    await session.commit()
    with pytest.raises(QueueStateError):
        await withdraw_request(
            session, queue_id=queued.id, requester_id=other.id
        )


# ─── direct override + history ──────────────────────────────────────


@pytest.mark.asyncio
async def test_direct_override_records_prior_status(
    session: AsyncSession,
) -> None:
    """The first override on ``ema`` (which is ``active`` in
    registry) records prior_status='active' from registry_default."""
    admin = await _seed(session, role=ROLE_ADMIN)
    row = await create_direct_override(
        session,
        indicator_id="ema",
        new_status="deprecated",
        reason="security issue found in calculation",
        approved_by_user_id=admin.id,
    )
    await session.commit()
    assert row.prior_status == "active"
    assert row.prior_status_source == "registry_default"


@pytest.mark.asyncio
async def test_chained_overrides_record_prior_override(
    session: AsyncSession,
) -> None:
    admin = await _seed(session, role=ROLE_ADMIN)
    await create_direct_override(
        session,
        indicator_id="ema",
        new_status="deprecated",
        reason="first",
        approved_by_user_id=admin.id,
    )
    await session.commit()
    second = await create_direct_override(
        session,
        indicator_id="ema",
        new_status="active",
        reason="rolled back",
        approved_by_user_id=admin.id,
    )
    await session.commit()
    assert second.prior_status == "deprecated"
    assert second.prior_status_source == "override"


@pytest.mark.asyncio
async def test_direct_override_rejects_invalid_status(
    session: AsyncSession,
) -> None:
    admin = await _seed(session, role=ROLE_ADMIN)
    with pytest.raises(ValueError):
        await create_direct_override(
            session,
            indicator_id="ema",
            new_status="garbage",
            reason="x",
            approved_by_user_id=admin.id,
        )


@pytest.mark.asyncio
async def test_history_returns_newest_first(
    session: AsyncSession,
) -> None:
    admin = await _seed(session, role=ROLE_ADMIN)
    await create_direct_override(
        session, indicator_id="ema", new_status="deprecated",
        reason="r1", approved_by_user_id=admin.id,
    )
    await session.commit()
    await create_direct_override(
        session, indicator_id="ema", new_status="active",
        reason="r2", approved_by_user_id=admin.id,
    )
    await session.commit()
    rows = await get_indicator_history(session, "ema")
    assert len(rows) == 2
    assert rows[0].override_reason == "r2"  # newer first
    assert rows[1].override_reason == "r1"


@pytest.mark.asyncio
async def test_list_active_overrides_dedupes_per_indicator(
    session: AsyncSession,
) -> None:
    """Two overrides on the same indicator → only the latest
    appears in active_overrides."""
    admin = await _seed(session, role=ROLE_ADMIN)
    await create_direct_override(
        session, indicator_id="ema", new_status="deprecated",
        reason="r1", approved_by_user_id=admin.id,
    )
    await session.commit()
    await create_direct_override(
        session, indicator_id="ema", new_status="active",
        reason="r2", approved_by_user_id=admin.id,
    )
    await session.commit()
    rows = await list_active_overrides(session)
    ema_rows = [r for r in rows if r.indicator_id == "ema"]
    assert len(ema_rows) == 1
    assert ema_rows[0].override_status == "active"


# ─── list_pending_queue + list_my_requests ──────────────────────────


@pytest.mark.asyncio
async def test_list_pending_excludes_decided(
    session: AsyncSession,
) -> None:
    creator = await _seed(session, role=ROLE_CREATOR)
    admin = await _seed(session, role=ROLE_ADMIN)
    pending = await enqueue_request(
        session, indicator_id="kama", requested_status="active",
        reason="x", requester_id=creator.id,
    )
    await session.commit()
    decided = await enqueue_request(
        session, indicator_id="supertrend", requested_status="active",
        reason="y", requester_id=creator.id,
    )
    await session.commit()
    await decide_request(
        session, queue_id=decided.id, decision="reject",
        decision_by_user_id=admin.id, notes="no",
    )
    await session.commit()
    rows = await list_pending_queue(session)
    ids = {str(r.id) for r in rows}
    assert str(pending.id) in ids
    assert str(decided.id) not in ids


@pytest.mark.asyncio
async def test_list_my_requests_isolates_per_user(
    session: AsyncSession,
) -> None:
    creator_a = await _seed(session, role=ROLE_CREATOR)
    creator_b = await _seed(session, role=ROLE_CREATOR)
    await enqueue_request(
        session, indicator_id="kama", requested_status="active",
        reason="A", requester_id=creator_a.id,
    )
    await enqueue_request(
        session, indicator_id="supertrend", requested_status="active",
        reason="B", requester_id=creator_b.id,
    )
    await session.commit()

    a_rows = await list_my_requests(session, requester_id=creator_a.id)
    b_rows = await list_my_requests(session, requester_id=creator_b.id)
    assert {r.indicator_id for r in a_rows} == {"kama"}
    assert {r.indicator_id for r in b_rows} == {"supertrend"}
