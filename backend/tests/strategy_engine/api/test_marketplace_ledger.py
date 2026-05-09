"""``/api/marketplace/listings/{id}/ledger`` REST tests.

Mirrors the marketplace-Phase-1 fixture pattern. Mounts the
ledger router on a tiny FastAPI app, overrides the auth + DB
deps, drives the chain end-to-end via the manual trigger.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.auth.roles import (
    ROLE_ADMIN,
    ROLE_CREATOR,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    require_creator_or_above,
)
from app.db.base import Base
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace_ledger import (
    router as ledger_router,
)


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-ledger-api-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


async def _seed_user(
    maker: async_sessionmaker[AsyncSession],
    email: str,
    role: str = ROLE_USER,
) -> User:
    async with maker() as s:
        u = User(email=email, password_hash="x", is_active=True, role=role)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _seed_listing(
    maker: async_sessionmaker[AsyncSession],
    creator: User,
    *,
    listing_status: str = "published",
    published_offset_days: int = 5,
) -> MarketplaceListing:
    async with maker() as s:
        strategy = Strategy(user_id=creator.id, name="for-ledger")
        s.add(strategy)
        await s.flush()
        listing = MarketplaceListing(
            strategy_id=strategy.id,
            creator_id=creator.id,
            title="Verify",
            description="d",
            price_inr=Decimal("0"),
            tags=[],
            status=listing_status,
            published_at=(
                datetime.now(UTC) - timedelta(days=published_offset_days)
                if listing_status == "published"
                else None
            ),
        )
        s.add(listing)
        await s.commit()
        await s.refresh(listing)
        return listing


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User], TestClient]:
    def _build(user: User) -> TestClient:
        app = FastAPI()
        app.include_router(ledger_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        async def _override_user() -> User:
            return user

        async def _override_creator() -> User:
            allowed = {ROLE_CREATOR, ROLE_ADMIN, ROLE_SUPER_ADMIN}
            if user.role not in allowed:
                from fastapi import HTTPException
                from fastapi import status as http_status

                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="Yeh feature sirf creator_or_above ke liye hai.",
                )
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_current_active_user] = _override_user
        app.dependency_overrides[require_creator_or_above] = _override_creator
        return TestClient(app)

    return _build


# ─── Manual trigger ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_creator_can_manually_trigger_first_snapshot(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "trig-c@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        resp = client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["sequence_number"] == 1
    assert body["prior_hash"] is None
    assert body["chain_signature"]


@pytest.mark.asyncio
async def test_duplicate_trigger_same_day_returns_409(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "dup-c@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
        resp = client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_non_creator_cannot_trigger(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "owned-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "regular@x", role=ROLE_USER)
    listing = await _seed_listing(db_maker, creator)
    with make_client(user) as client:
        resp = client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
    # The require_creator_or_above gate fires first → 403.
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_other_creator_cannot_trigger_for_someone_elses_listing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator_a = await _seed_user(db_maker, "creator-a-led@x", role=ROLE_CREATOR)
    creator_b = await _seed_user(db_maker, "creator-b-led@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator_a)
    with make_client(creator_b) as client:
        resp = client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
    # 404 (not 403) so the endpoint isn't an enumeration oracle.
    assert resp.status_code == 404


# ─── Read paths ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_latest_returns_null_for_empty_chain(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "empty-c@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        resp = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger"
        )
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_latest_returns_most_recent_snapshot(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Trigger a single snapshot then assert ``GET /ledger`` returns it."""
    creator = await _seed_user(db_maker, "latest-c@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        triggered = client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        ).json()
        latest = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger"
        ).json()
    assert latest["id"] == triggered["id"]
    assert latest["chain_signature"] == triggered["chain_signature"]


@pytest.mark.asyncio
async def test_history_paginates_newest_first(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Manual trigger only fires once per UTC day; history with a
    single row is sufficient to pin the response shape + ordering
    contract."""
    creator = await _seed_user(db_maker, "hist-c@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
        resp = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger/history"
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["count"] == 1
    assert body["snapshots"][0]["sequence_number"] == 1


@pytest.mark.asyncio
async def test_get_snapshot_by_sequence_returns_match(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "seq-c@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
        resp = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/1"
        )
    assert resp.status_code == 200
    assert resp.json()["sequence_number"] == 1


@pytest.mark.asyncio
async def test_get_snapshot_by_unknown_sequence_404(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "404-seq@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
        resp = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/99"
        )
    assert resp.status_code == 404


# ─── Verification endpoint ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_clean_chain_returns_valid(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "verify-c@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        client.post(
            f"/api/marketplace/listings/{listing.id}/ledger/snapshot/now"
        )
        resp = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger/verify"
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["is_chain_valid"] is True
    assert body["snapshots_verified"] == 1


@pytest.mark.asyncio
async def test_verify_empty_chain_returns_zero_verified(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "verify-empty@x", role=ROLE_CREATOR)
    listing = await _seed_listing(db_maker, creator)
    with make_client(creator) as client:
        resp = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger/verify"
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["is_chain_valid"] is True
    assert body["snapshots_verified"] == 0


# ─── Visibility ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_draft_listing_ledger_hidden_from_non_owner(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Non-owner GET on a draft listing's ledger returns 404 — same
    visibility rule as the marketplace listing detail endpoint."""
    creator = await _seed_user(db_maker, "draft-c@x", role=ROLE_CREATOR)
    intruder = await _seed_user(db_maker, "draft-u@x", role=ROLE_USER)
    listing = await _seed_listing(
        db_maker, creator, listing_status="draft"
    )
    with make_client(intruder) as client:
        resp = client.get(
            f"/api/marketplace/listings/{listing.id}/ledger"
        )
    assert resp.status_code == 404


# ─── Auth ────────────────────────────────────────────────────────────


def test_unauthenticated_get_returns_401() -> None:
    app = FastAPI()
    app.include_router(ledger_router)
    fake_id = uuid.uuid4()
    with TestClient(app) as client:
        resp = client.get(f"/api/marketplace/listings/{fake_id}/ledger")
    assert resp.status_code == 401


def test_unauthenticated_trigger_returns_401() -> None:
    app = FastAPI()
    app.include_router(ledger_router)
    fake_id = uuid.uuid4()
    with TestClient(app) as client:
        resp = client.post(
            f"/api/marketplace/listings/{fake_id}/ledger/snapshot/now"
        )
    assert resp.status_code == 401
