"""Effective-status resolver tests.

The resolver is the only read path the rest of the system would
eventually call (compliance / pine importer wire-ups deferred to
v1.1). It MUST honour the registry default when no override
exists, and the latest in-window override otherwise.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.auth.roles import ROLE_ADMIN
from app.db.base import Base
from app.db.models.indicator_status_override import IndicatorStatusOverride
from app.db.models.user import User
from app.strategy_engine.indicator_admin.resolver import (
    resolve_effective_status,
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-resolver-{uuid.uuid4().hex}"
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


async def _seed_admin(s: AsyncSession) -> User:
    u = User(email=f"a{uuid.uuid4().hex[:8]}@x", password_hash="x",
             is_active=True, role=ROLE_ADMIN)
    s.add(u)
    await s.commit()
    await s.refresh(u)
    return u


# ─── No override: registry default wins ───────────────────────────────


@pytest.mark.asyncio
async def test_resolves_registry_default_when_no_override(
    session: AsyncSession,
) -> None:
    """An indicator with no override row resolves to its registry
    default. ``ema`` is ACTIVE in the registry."""
    eff = await resolve_effective_status(session, "ema")
    assert eff.status == "active"
    assert eff.source == "registry_default"
    assert eff.override_id is None


@pytest.mark.asyncio
async def test_resolves_coming_soon_default(
    session: AsyncSession,
) -> None:
    eff = await resolve_effective_status(session, "dpo")
    assert eff.status == "coming_soon"
    assert eff.source == "registry_default"


@pytest.mark.asyncio
async def test_unknown_id_returns_unknown(
    session: AsyncSession,
) -> None:
    """An id that's neither in the registry nor in any override
    surfaces as ``unknown`` — callers can branch on this to decide
    whether to render or 404."""
    eff = await resolve_effective_status(session, "totally_made_up_xyz")
    assert eff.status == "unknown"
    assert eff.source == "registry_default"


# ─── Override beats default ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_override_beats_registry_default(
    session: AsyncSession,
) -> None:
    """An override row promotes ``kama`` from coming_soon to active."""
    admin = await _seed_admin(session)
    now = datetime.now(UTC)
    session.add(
        IndicatorStatusOverride(
            indicator_id="kama",
            override_status="active",
            override_reason="Promoted after creator request 5",
            approved_by_user_id=admin.id,
            approved_at=now,
            effective_from=now - timedelta(hours=1),
            effective_until=None,
            prior_status="coming_soon",
            prior_status_source="registry_default",
        )
    )
    await session.commit()
    eff = await resolve_effective_status(session, "kama")
    assert eff.status == "active"
    assert eff.source == "override"
    assert eff.override_id is not None
    assert eff.override_reason is not None


@pytest.mark.asyncio
async def test_latest_override_wins_over_older(
    session: AsyncSession,
) -> None:
    """When two open-ended overrides exist, the one with the newer
    ``effective_from`` takes precedence."""
    admin = await _seed_admin(session)
    now = datetime.now(UTC)
    session.add(
        IndicatorStatusOverride(
            indicator_id="kama",
            override_status="experimental",
            override_reason="trial",
            approved_by_user_id=admin.id,
            approved_at=now - timedelta(days=2),
            effective_from=now - timedelta(days=2),
            prior_status="coming_soon",
            prior_status_source="registry_default",
        )
    )
    session.add(
        IndicatorStatusOverride(
            indicator_id="kama",
            override_status="active",
            override_reason="promoted",
            approved_by_user_id=admin.id,
            approved_at=now - timedelta(hours=1),
            effective_from=now - timedelta(hours=1),
            prior_status="experimental",
            prior_status_source="prior_override",
        )
    )
    await session.commit()
    eff = await resolve_effective_status(session, "kama")
    assert eff.status == "active"


@pytest.mark.asyncio
async def test_expired_override_falls_back_to_default(
    session: AsyncSession,
) -> None:
    """``effective_until`` in the past means the override no longer
    applies; resolver falls through to the registry default."""
    admin = await _seed_admin(session)
    now = datetime.now(UTC)
    session.add(
        IndicatorStatusOverride(
            indicator_id="dpo",
            override_status="active",
            override_reason="trial period",
            approved_by_user_id=admin.id,
            approved_at=now - timedelta(days=10),
            effective_from=now - timedelta(days=10),
            effective_until=now - timedelta(days=1),  # expired yesterday
            prior_status="coming_soon",
            prior_status_source="registry_default",
        )
    )
    await session.commit()
    eff = await resolve_effective_status(session, "dpo")
    assert eff.status == "coming_soon"
    assert eff.source == "registry_default"


@pytest.mark.asyncio
async def test_future_override_does_not_apply_yet(
    session: AsyncSession,
) -> None:
    """``effective_from`` in the future means the override doesn't
    apply *yet* — resolver falls through to the registry default
    until the activation moment."""
    admin = await _seed_admin(session)
    now = datetime.now(UTC)
    session.add(
        IndicatorStatusOverride(
            indicator_id="dpo",
            override_status="active",
            override_reason="schedule promotion",
            approved_by_user_id=admin.id,
            approved_at=now,
            effective_from=now + timedelta(days=7),
            prior_status="coming_soon",
            prior_status_source="registry_default",
        )
    )
    await session.commit()
    eff = await resolve_effective_status(session, "dpo")
    assert eff.status == "coming_soon"
    assert eff.source == "registry_default"

    # But asking with a future ``now`` should resolve to the override.
    eff_future = await resolve_effective_status(
        session, "dpo", now=now + timedelta(days=10)
    )
    assert eff_future.status == "active"
    assert eff_future.source == "override"
