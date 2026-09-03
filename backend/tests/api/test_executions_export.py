"""GET /api/strategies/executions/export — the CSV of what /trades shows.

WHY THIS ENDPOINT EXISTS. ``/api/users/me/trades/export`` already streamed CSV
— of the legacy ``trades`` table, which the strategy engine never writes
(0 rows on prod against 107 ``strategy_executions``). The /trades page renders
``strategy_executions``. Wiring the pricing-table "CSV Export" feature to the
old endpoint would have shipped a button that downloads a header-only file.

THE CONTRACT THESE TESTS LOCK:
  1. The export uses the SAME owner-scoped query as the list — the file can
     never disagree with the page. Proven by the subscriber-isolation case,
     which is the exact bug the list endpoint was once fixed for.
  2. Columns are the ones the page shows plus the reconciliation ids, and
     NEVER ``broker_response`` (raw JSON) or ``broker_credential_id``.
  3. It is an attachment, no-store, and survives an empty account.
  4. It is paywall-gated identically to the list (see
     test_paywall_gated_endpoints.py, where it is in GATED).
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles as _compiles
from sqlalchemy.pool import StaticPool

import app.auth.entitlements as ent
from app.api.deps import get_current_active_user
from app.api.strategy_signals import _EXPORT_COLUMNS
from app.api.strategy_signals import router as signals_router
from app.db.base import Base
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session

EXPORT = "/api/strategies/executions/export"
LIST = "/api/strategies/executions"


@_compiles(_JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-export-{uuid.uuid4().hex}"
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


def _client(
    db_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    user: User,
) -> TestClient:
    monkeypatch.setattr(ent, "get_settings", lambda: SimpleNamespace(paywall_enforced=False))
    app = FastAPI()
    app.include_router(signals_router)

    async def _ovr_user() -> User:
        return user

    async def _ovr_session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    app.dependency_overrides[get_current_active_user] = _ovr_user
    app.dependency_overrides[get_session] = _ovr_session
    return TestClient(app)


def _user(uid: uuid.UUID) -> User:
    u = User(email=f"{uid}@x", password_hash="p", is_active=True)
    u.id = uid
    return u


def _execution(
    *,
    signal_id: uuid.UUID,
    subscription_id: uuid.UUID | None,
    symbol: str = "NIFTY",
    broker_order_id: str | None = None,
) -> StrategyExecution:
    return StrategyExecution(
        signal_id=signal_id,
        broker_credential_id=uuid.uuid4(),
        subscription_id=subscription_id,
        leg_number=1,
        leg_role="entry",
        symbol=symbol,
        side="BUY",
        quantity=1,
        order_type="market",
        broker_order_id=broker_order_id,
        broker_response={"secret": "never-in-csv"},
    )


async def _seed_signal(db_maker: async_sessionmaker[AsyncSession], uid: uuid.UUID) -> uuid.UUID:
    async with db_maker() as s:
        sig = StrategySignal(
            user_id=uid, strategy_id=uuid.uuid4(), raw_payload={}, symbol="NIFTY", action="BUY",
        )
        s.add(sig)
        await s.commit()
        return sig.id


def _rows(resp) -> list[dict[str, str]]:  # type: ignore[no-untyped-def]
    return list(csv.DictReader(io.StringIO(resp.text)))


# ═══════════════════════════════════════════════════════════════════════
# 1. Shape: attachment, columns, empty account
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_empty_account_gets_a_header_only_csv(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(db_maker, monkeypatch, _user(uuid.uuid4()))
    resp = client.get(EXPORT)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="tradetri-executions.csv"'
    assert resp.headers["cache-control"] == "no-store"
    lines = resp.text.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].split(",") == list(_EXPORT_COLUMNS)


def test_columns_are_what_the_page_shows_and_nothing_secret() -> None:
    """The /trades page renders these; a broker statement needs the ids."""
    for col in ("id", "signal_id", "leg_role", "symbol", "side", "quantity",
                "price", "broker_order_id", "broker_status", "error_code",
                "placed_at", "completed_at"):
        assert col in _EXPORT_COLUMNS
    # 🔴 raw broker JSON and an internal credential key never leave the server
    assert "broker_response" not in _EXPORT_COLUMNS
    assert "broker_credential_id" not in _EXPORT_COLUMNS


# ═══════════════════════════════════════════════════════════════════════
# 2. 🔴 Same query as the page — a subscriber's paper row never leaks
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_excludes_subscriber_rows_exactly_like_the_list(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subscriber executions link to the OWNER's signal with a non-NULL
    subscription_id. The list endpoint was once fixed for this leak; the
    export shares its query, and this proves it."""
    uid = uuid.uuid4()
    sig_id = await _seed_signal(db_maker, uid)
    async with db_maker() as s:
        owned = _execution(signal_id=sig_id, subscription_id=None, broker_order_id="OWN-1")
        s.add(owned)
        s.add(_execution(signal_id=sig_id, subscription_id=uuid.uuid4(), broker_order_id="SUB-1"))
        await s.commit()
        owned_id = str(owned.id)

    client = _client(db_maker, monkeypatch, _user(uid))
    rows = _rows(client.get(EXPORT))
    assert [r["id"] for r in rows] == [owned_id]
    assert [r["broker_order_id"] for r in rows] == ["OWN-1"]

    # ...and it is byte-for-byte the same set the page renders.
    listed = client.get(LIST).json()["executions"]
    assert [e["id"] for e in listed] == [r["id"] for r in rows]


@pytest.mark.asyncio
async def test_export_never_crosses_users(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    sig_a = await _seed_signal(db_maker, a)
    sig_b = await _seed_signal(db_maker, b)
    async with db_maker() as s:
        s.add(_execution(signal_id=sig_a, subscription_id=None, symbol="A-SYM"))
        s.add(_execution(signal_id=sig_b, subscription_id=None, symbol="B-SYM"))
        await s.commit()

    rows = _rows(_client(db_maker, monkeypatch, _user(a)).get(EXPORT))
    assert [r["symbol"] for r in rows] == ["A-SYM"]


@pytest.mark.asyncio
async def test_signal_id_filter_matches_the_list(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    uid = uuid.uuid4()
    s1 = await _seed_signal(db_maker, uid)
    s2 = await _seed_signal(db_maker, uid)
    async with db_maker() as s:
        s.add(_execution(signal_id=s1, subscription_id=None, symbol="ONE"))
        s.add(_execution(signal_id=s2, subscription_id=None, symbol="TWO"))
        await s.commit()

    client = _client(db_maker, monkeypatch, _user(uid))
    rows = _rows(client.get(f"{EXPORT}?signal_id={s1}"))
    assert [r["symbol"] for r in rows] == ["ONE"]


# ═══════════════════════════════════════════════════════════════════════
# 3. Values are what the page would show, not repr() noise
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cells_are_plain_values_and_nulls_are_empty(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    uid = uuid.uuid4()
    sig = await _seed_signal(db_maker, uid)
    async with db_maker() as s:
        s.add(_execution(signal_id=sig, subscription_id=None))  # price/broker_order_id None
        await s.commit()

    row = _rows(_client(db_maker, monkeypatch, _user(uid)).get(EXPORT))[0]
    assert row["symbol"] == "NIFTY"
    assert row["quantity"] == "1"
    assert row["leg_role"] == "entry"
    assert row["price"] == ""            # None -> empty cell, not "None"
    assert row["broker_order_id"] == ""
    assert row["completed_at"] == ""
    assert "T" in row["placed_at"]       # ISO-8601, not a Python repr
    # nothing from the raw broker payload made it into the file
    assert "never-in-csv" not in "".join(row.values())
