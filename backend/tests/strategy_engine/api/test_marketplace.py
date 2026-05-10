"""``/api/marketplace`` CRUD + RBAC tests.

Mirrors the entry / exit / risk template test pattern: fresh
in-memory aiosqlite DB per test, FastAPI ``dependency_overrides``
for the auth + session deps. The marketplace API has three role
gates:

    * Creator-only mutations  — ``require_creator_or_above``
    * Any authenticated       — browse, subscribe, list-my-subs
    * Active subscriber only  — submit / update rating

Each gate gets at least one positive-case test and one rejection
test. Phase 1 deferrals (real payments, ledger snapshot, frontend)
are documented in the commit message; the API surface tested here
is the contract every later phase has to keep."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

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
    ROLE_CREATOR,
    ROLE_USER,
    require_creator_or_above,
)
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-marketplace-{uuid.uuid4().hex}"
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


async def _seed_strategy(
    maker: async_sessionmaker[AsyncSession], owner: User, name: str
) -> Strategy:
    async with maker() as s:
        st = Strategy(user_id=owner.id, name=name)
        s.add(st)
        await s.commit()
        await s.refresh(st)
        return st


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User], TestClient]:
    """Build a TestClient whose marketplace router has the auth +
    session deps overridden to ``user`` + the shared in-memory DB."""

    def _build(user: User) -> TestClient:
        app = FastAPI()
        app.include_router(marketplace_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_current_active_user] = _override_user
        # Also override require_creator_or_above so creator-only
        # endpoints accept the supplied user when their role is
        # creator (or above). The helper would normally do its own
        # role check; we mirror that here.
        async def _override_creator() -> User:
            from app.auth.roles import ROLE_ADMIN, ROLE_CREATOR, ROLE_SUPER_ADMIN

            allowed = {ROLE_CREATOR, ROLE_ADMIN, ROLE_SUPER_ADMIN}
            if user.role not in allowed:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Yeh feature sirf creator_or_above ke liye hai.",
                )
            return user

        app.dependency_overrides[require_creator_or_above] = _override_creator
        return TestClient(app)

    return _build


# ─── Sample payloads ──────────────────────────────────────────────────


def _listing_payload(strategy_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "strategy_id": str(strategy_id),
        "title": "RSI scalper — beginner-friendly",
        "description": "Bhai sahab kamaal ka strategy hai",
        "price_inr": 0.0,
        "tags": ["intraday", "rsi"],
    }
    body.update(overrides)
    return body


# ─── 1. Listing CRUD — happy path ─────────────────────────────────────


@pytest.mark.asyncio
async def test_creator_can_create_draft_listing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "creator@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "rsi-scalper")
    with make_client(creator) as client:
        resp = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["title"] == "RSI scalper — beginner-friendly"
    assert body["creator_id"] == str(creator.id)
    assert body["price_inr"] == 0.0
    assert body["subscriber_count"] == 0


@pytest.mark.asyncio
async def test_publish_flips_status_and_sets_published_at(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "publish@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "publish-me")
    with make_client(creator) as client:
        created = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        resp = client.post(
            f"/api/marketplace/listings/{created['id']}/publish"
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None


@pytest.mark.asyncio
async def test_archive_marks_listing_archived(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "archive@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "archive-me")
    with make_client(creator) as client:
        created = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{created['id']}/publish")
        resp = client.post(
            f"/api/marketplace/listings/{created['id']}/archive"
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_update_partial_fields_on_draft(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "update@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "update-me")
    with make_client(creator) as client:
        created = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="Old"),
        ).json()
        resp = client.put(
            f"/api/marketplace/listings/{created['id']}",
            json={"title": "New title", "price_inr": 999.5},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "New title"
    assert body["price_inr"] == 999.5
    # Untouched field preserved.
    assert body["description"] == "Bhai sahab kamaal ka strategy hai"


@pytest.mark.asyncio
async def test_list_my_listings_returns_all_statuses(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "list-me@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "alpha")
    with make_client(creator) as client:
        a = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="Alpha"),
        ).json()
        b = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="Beta"),
        ).json()
        client.post(f"/api/marketplace/listings/{a['id']}/publish")

        resp = client.get("/api/marketplace/listings/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    statuses = {row["status"] for row in body["listings"]}
    assert statuses == {"draft", "published"}
    titles = {row["title"] for row in body["listings"]}
    assert titles == {"Alpha", "Beta"}
    _ = b


# ─── 2. RBAC — creator-only gates ─────────────────────────────────────


@pytest.mark.asyncio
async def test_non_creator_cannot_create_listing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Plain users hit the ``require_creator_or_above`` gate first
    and never get past it (403 before the strategy lookup runs)."""
    user = await _seed_user(db_maker, "regular@x", role=ROLE_USER)
    with make_client(user) as client:
        resp = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(uuid.uuid4()),
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_listing_rejects_unowned_strategy(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Creator can't list someone else's strategy as their own."""
    other = await _seed_user(db_maker, "other-creator@x", role=ROLE_CREATOR)
    creator = await _seed_user(db_maker, "main-creator@x", role=ROLE_CREATOR)
    foreign_strategy = await _seed_strategy(db_maker, other, "foreign")
    with make_client(creator) as client:
        resp = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(foreign_strategy.id),
        )
    assert resp.status_code == 404
    assert "Strategy not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_creator_update_returns_404(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Creator B can't mutate creator A's listing — 404 (not 403)
    so the endpoint isn't an enumeration oracle."""
    a = await _seed_user(db_maker, "creator-a@x", role=ROLE_CREATOR)
    b = await _seed_user(db_maker, "creator-b@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, a, "private")
    with make_client(a) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()

    with make_client(b) as client:
        update = client.put(
            f"/api/marketplace/listings/{listing['id']}",
            json={"title": "hijack"},
        )
        publish = client.post(
            f"/api/marketplace/listings/{listing['id']}/publish"
        )
        archive = client.post(
            f"/api/marketplace/listings/{listing['id']}/archive"
        )
    assert update.status_code == 404
    assert publish.status_code == 404
    assert archive.status_code == 404


@pytest.mark.asyncio
async def test_publish_rejects_already_published(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "double-pub@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        created = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{created['id']}/publish")
        resp = client.post(
            f"/api/marketplace/listings/{created['id']}/publish"
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_blocked_on_archived_listing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "no-edit@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        created = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{created['id']}/publish")
        client.post(f"/api/marketplace/listings/{created['id']}/archive")
        resp = client.put(
            f"/api/marketplace/listings/{created['id']}",
            json={"title": "too late"},
        )
    assert resp.status_code == 409


# ─── 3. Browse + detail visibility ────────────────────────────────────


@pytest.mark.asyncio
async def test_browse_only_returns_published_listings(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "browse-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "browse-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        published = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="Published"),
        ).json()
        client.post(f"/api/marketplace/listings/{published['id']}/publish")
        client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="Drafty"),
        )

    with make_client(user) as client:
        resp = client.get("/api/marketplace/listings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["listings"][0]["title"] == "Published"


@pytest.mark.asyncio
async def test_browse_filters_by_max_price(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "price-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "price-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        cheap = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="Cheap", price_inr=99.0),
        ).json()
        expensive = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="Expensive", price_inr=2_500.0),
        ).json()
        client.post(f"/api/marketplace/listings/{cheap['id']}/publish")
        client.post(f"/api/marketplace/listings/{expensive['id']}/publish")

    with make_client(user) as client:
        resp = client.get("/api/marketplace/listings", params={"max_price": 500})
    titles = {row["title"] for row in resp.json()["listings"]}
    assert titles == {"Cheap"}


@pytest.mark.asyncio
async def test_browse_filters_by_tag(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "tag-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "tag-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        intraday = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="ID", tags=["intraday"]),
        ).json()
        swing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, title="SW", tags=["swing"]),
        ).json()
        client.post(f"/api/marketplace/listings/{intraday['id']}/publish")
        client.post(f"/api/marketplace/listings/{swing['id']}/publish")

    with make_client(user) as client:
        resp = client.get("/api/marketplace/listings", params={"tag": "swing"})
    titles = {row["title"] for row in resp.json()["listings"]}
    assert titles == {"SW"}


@pytest.mark.asyncio
async def test_get_listing_hides_drafts_from_non_owners(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "draft-c@x", role=ROLE_CREATOR)
    intruder = await _seed_user(db_maker, "draft-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        # Owner sees their own draft.
        own = client.get(f"/api/marketplace/listings/{listing['id']}")
    assert own.status_code == 200

    with make_client(intruder) as client:
        resp = client.get(f"/api/marketplace/listings/{listing['id']}")
    # Non-owner gets 404 — not 403 — to avoid leaking the listing's
    # existence.
    assert resp.status_code == 404


# ─── 4. Subscriptions ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_can_subscribe_to_published_listing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "sub-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "sub-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id, price_inr=499.0),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    with make_client(user) as client:
        resp = client.post(
            f"/api/marketplace/listings/{listing['id']}/subscribe"
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "active"
    # Stub payment — amount_paid_inr mirrors listing.price_inr.
    assert body["amount_paid_inr"] == 499.0

    # subscriber_count incremented on the listing.
    with make_client(creator) as client:
        detail = client.get(f"/api/marketplace/listings/{listing['id']}")
    assert detail.json()["subscriber_count"] == 1


@pytest.mark.asyncio
async def test_subscribe_is_idempotent_for_existing_active_sub(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """Re-calling subscribe on an active sub returns the same row
    (rather than 409 or duplicate insert)."""
    creator = await _seed_user(db_maker, "idem-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "idem-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    with make_client(user) as client:
        first = client.post(
            f"/api/marketplace/listings/{listing['id']}/subscribe"
        ).json()
        second = client.post(
            f"/api/marketplace/listings/{listing['id']}/subscribe"
        ).json()
    assert first["id"] == second["id"]


@pytest.mark.asyncio
async def test_creator_cannot_subscribe_to_own_listing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "self-sub@x", role=ROLE_CREATOR)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")
        resp = client.post(
            f"/api/marketplace/listings/{listing['id']}/subscribe"
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_subscribe_rejected_for_draft_listing(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "draft-sub-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "draft-sub-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
    with make_client(user) as client:
        resp = client.post(
            f"/api/marketplace/listings/{listing['id']}/subscribe"
        )
    # Subscribe enforces "must be published" via 409 — the state
    # transition is what's wrong, not the visibility. (Browse + GET
    # use 404 to hide drafts from non-owners; subscribe lives on the
    # *action* layer where 409 is the right shape.)
    assert resp.status_code == 409
    assert "draft" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unsubscribe_marks_active_sub_cancelled(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "unsub-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "unsub-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    with make_client(user) as client:
        client.post(f"/api/marketplace/listings/{listing['id']}/subscribe")
        resp = client.delete(
            f"/api/marketplace/listings/{listing['id']}/subscribe"
        )
        # Subsequent unsubscribe → 404 (no active sub).
        repeat = client.delete(
            f"/api/marketplace/listings/{listing['id']}/subscribe"
        )
        my_subs = client.get("/api/marketplace/subscriptions/me").json()
    assert resp.status_code == 204
    assert repeat.status_code == 404
    assert my_subs["count"] == 1
    assert my_subs["subscriptions"][0]["status"] == "cancelled"


# ─── 5. Ratings ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscriber_can_submit_rating(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "rate-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "rate-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    with make_client(user) as client:
        client.post(f"/api/marketplace/listings/{listing['id']}/subscribe")
        resp = client.post(
            f"/api/marketplace/listings/{listing['id']}/ratings",
            json={"rating": 5, "review": "kamaal!"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["rating"] == 5
    assert body["review"] == "kamaal!"

    # Listing's denormalised counters refreshed.
    with make_client(creator) as client:
        detail = client.get(f"/api/marketplace/listings/{listing['id']}").json()
    assert detail["rating_count"] == 1
    assert detail["rating_avg"] == 5.0


@pytest.mark.asyncio
async def test_non_subscriber_cannot_rate(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "rate-non-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "rate-non-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    with make_client(user) as client:
        resp = client.post(
            f"/api/marketplace/listings/{listing['id']}/ratings",
            json={"rating": 3},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_rating_returns_409(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """``POST /ratings`` is one-shot — re-call returns 409 with the
    instruction to PUT instead."""
    creator = await _seed_user(db_maker, "dup-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "dup-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    with make_client(user) as client:
        client.post(f"/api/marketplace/listings/{listing['id']}/subscribe")
        client.post(
            f"/api/marketplace/listings/{listing['id']}/ratings",
            json={"rating": 4},
        )
        resp = client.post(
            f"/api/marketplace/listings/{listing['id']}/ratings",
            json={"rating": 5},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_rating_refreshes_listing_avg(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "upd-rate-c@x", role=ROLE_CREATOR)
    user = await _seed_user(db_maker, "upd-rate-u@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    with make_client(user) as client:
        client.post(f"/api/marketplace/listings/{listing['id']}/subscribe")
        rating = client.post(
            f"/api/marketplace/listings/{listing['id']}/ratings",
            json={"rating": 5},
        ).json()
        resp = client.put(
            f"/api/marketplace/listings/{listing['id']}/ratings/{rating['id']}",
            json={"rating": 2, "review": "actually mid"},
        )
    assert resp.status_code == 200
    assert resp.json()["rating"] == 2

    with make_client(creator) as client:
        detail = client.get(f"/api/marketplace/listings/{listing['id']}").json()
    assert detail["rating_count"] == 1
    assert detail["rating_avg"] == 2.0


@pytest.mark.asyncio
async def test_list_ratings_returns_paginated(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    creator = await _seed_user(db_maker, "ls-rate-c@x", role=ROLE_CREATOR)
    user_a = await _seed_user(db_maker, "ls-rate-a@x", role=ROLE_USER)
    user_b = await _seed_user(db_maker, "ls-rate-b@x", role=ROLE_USER)
    strategy = await _seed_strategy(db_maker, creator, "s")
    with make_client(creator) as client:
        listing = client.post(
            "/api/marketplace/listings",
            json=_listing_payload(strategy.id),
        ).json()
        client.post(f"/api/marketplace/listings/{listing['id']}/publish")

    for who in (user_a, user_b):
        with make_client(who) as client:
            client.post(f"/api/marketplace/listings/{listing['id']}/subscribe")
            client.post(
                f"/api/marketplace/listings/{listing['id']}/ratings",
                json={"rating": 4 if who is user_a else 2},
            )

    with make_client(user_a) as client:
        resp = client.get(
            f"/api/marketplace/listings/{listing['id']}/ratings",
            params={"limit": 10, "offset": 0},
        )
    body = resp.json()
    assert body["count"] == 2
    ratings = {r["rating"] for r in body["ratings"]}
    assert ratings == {2, 4}


# ─── 6. Auth required ────────────────────────────────────────────────


def test_unauthenticated_listing_browse_returns_401() -> None:
    """Without an auth dep override → 401."""
    app = FastAPI()
    app.include_router(marketplace_router)
    with TestClient(app) as client:
        resp = client.get("/api/marketplace/listings")
    assert resp.status_code == 401


def test_unauthenticated_listing_create_returns_401() -> None:
    app = FastAPI()
    app.include_router(marketplace_router)
    with TestClient(app) as client:
        resp = client.post(
            "/api/marketplace/listings",
            json={
                "strategy_id": str(uuid.uuid4()),
                "title": "x",
                "description": "y",
                "price_inr": 0.0,
                "tags": [],
            },
        )
    assert resp.status_code == 401
