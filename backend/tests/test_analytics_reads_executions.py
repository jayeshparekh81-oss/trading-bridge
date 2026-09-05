"""C10-A — /analytics reads strategy_executions + priced positions, not the
dead ``trades`` table.

``/api/users/me/trades`` (the analytics list) and ``/api/users/me/trades/export``
go through the SAME owner-scoped query as ``/api/strategies/executions/export``
(app.services.owner_executions), so a customer can never download two files
that disagree. ``/api/users/me/trades/stats`` counts closed round trips and
takes money ONLY from positions with a PRICED attribution tag — the founder's
exit rule: a human-interfered round trip is counted, never priced, and a
literal zero under that tag is never summed.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles as _compiles
from sqlalchemy.pool import StaticPool

import app.auth.entitlements as ent
from app.api.deps import get_current_active_user
from app.api.strategy_signals import router as signals_router
from app.api.users import router as users_router
from app.db.base import Base
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.services.owner_executions import EXPORT_COLUMNS


@_compiles(_JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


_T0 = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-analytics-{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true",
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
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, uid: uuid.UUID
) -> TestClient:
    monkeypatch.setattr(
        ent, "get_settings", lambda: SimpleNamespace(paywall_enforced=False, paywall_grace_days=0)
    )
    app = FastAPI()
    app.include_router(users_router)
    app.include_router(signals_router)
    user = User(email="u@x", password_hash="p", is_active=True, plan_status="active")
    user.id = uid

    async def _ovr_user() -> User:
        return user

    async def _ovr_session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    app.dependency_overrides[get_current_active_user] = _ovr_user
    app.dependency_overrides[get_session] = _ovr_session
    return TestClient(app)


def _execution(
    *,
    signal_id: uuid.UUID,
    subscription_id: uuid.UUID | None,
    symbol: str = "BSE",
    placed_at: datetime,
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
        placed_at=placed_at,
    )


def _position(
    *,
    user_id: uuid.UUID,
    status: str = "closed",
    final_pnl: Decimal | None,
    tag: str | None,
    closed_at: datetime | None,
    subscription_id: uuid.UUID | None = None,
) -> StrategyPosition:
    return StrategyPosition(
        user_id=user_id,
        strategy_id=uuid.uuid4(),
        broker_credential_id=uuid.uuid4(),
        subscription_id=subscription_id,
        symbol="BSE",
        side="BUY",
        total_quantity=1,
        remaining_quantity=0 if status == "closed" else 1,
        status=status,
        closed_at=closed_at,
        final_pnl=final_pnl,
        pnl_attribution=tag,
    )


async def _seed_signal(s: AsyncSession, uid: uuid.UUID) -> StrategySignal:
    sig = StrategySignal(
        user_id=uid, strategy_id=uuid.uuid4(), raw_payload={}, symbol="BSE", action="BUY"
    )
    s.add(sig)
    await s.flush()
    return sig


@pytest.mark.asyncio
async def test_me_trades_lists_owner_executions_only(db_maker, monkeypatch) -> None:
    uid, other = uuid.uuid4(), uuid.uuid4()
    async with db_maker() as s:
        sig = await _seed_signal(s, uid)
        s.add(_execution(signal_id=sig.id, subscription_id=None, placed_at=_T0))
        s.add(
            _execution(
                signal_id=sig.id,
                subscription_id=None,
                symbol="CDSL",
                placed_at=_T0 + timedelta(minutes=1),
            )
        )
        s.add(
            _execution(signal_id=sig.id, subscription_id=uuid.uuid4(), placed_at=_T0)
        )  # a subscriber's copy
        other_sig = await _seed_signal(s, other)
        s.add(
            _execution(signal_id=other_sig.id, subscription_id=None, placed_at=_T0)
        )  # someone else's
        await s.commit()

    client = _client(db_maker, monkeypatch, uid)
    body = client.get("/api/users/me/trades").json()
    assert body["basis"] == "strategy_executions"
    assert body["total"] == 2
    assert [r["symbol"] for r in body["trades"]] == ["CDSL", "BSE"]  # newest first
    assert set(body["trades"][0]) >= {
        "id",
        "signal_id",
        "leg_role",
        "side",
        "quantity",
        "price",
        "broker_status",
        "placed_at",
    }

    filtered = client.get("/api/users/me/trades?symbol=CDSL").json()
    assert filtered["total"] == 1 and filtered["trades"][0]["symbol"] == "CDSL"

    paged = client.get("/api/users/me/trades?skip=1&limit=1").json()
    assert (
        paged["total"] == 2 and len(paged["trades"]) == 1 and paged["trades"][0]["symbol"] == "BSE"
    )


@pytest.mark.asyncio
async def test_two_csv_exports_are_the_same_file(db_maker, monkeypatch) -> None:
    uid = uuid.uuid4()
    async with db_maker() as s:
        sig = await _seed_signal(s, uid)
        s.add(_execution(signal_id=sig.id, subscription_id=None, placed_at=_T0))
        s.add(_execution(signal_id=sig.id, subscription_id=uuid.uuid4(), placed_at=_T0))
        await s.commit()

    client = _client(db_maker, monkeypatch, uid)
    a = client.get("/api/users/me/trades/export")
    b = client.get("/api/strategies/executions/export")
    assert a.status_code == 200 and b.status_code == 200
    assert a.text == b.text
    assert a.text.splitlines()[0] == ",".join(EXPORT_COLUMNS)
    assert len(a.text.splitlines()) == 2  # header + the one owner row


@pytest.mark.asyncio
async def test_stats_take_money_only_from_priced_positions(db_maker, monkeypatch) -> None:
    uid = uuid.uuid4()
    async with db_maker() as s:
        sig = await _seed_signal(s, uid)
        s.add(_execution(signal_id=sig.id, subscription_id=None, placed_at=_T0))
        s.add(
            _execution(signal_id=sig.id, subscription_id=None, placed_at=_T0 + timedelta(minutes=1))
        )
        s.add(
            _position(
                user_id=uid,
                final_pnl=Decimal("100"),
                tag="bot_only",
                closed_at=_T0 + timedelta(days=1),
            )
        )
        s.add(
            _position(
                user_id=uid,
                final_pnl=Decimal("-40"),
                tag="account_flat",
                closed_at=_T0 + timedelta(days=2),
            )
        )
        # human-interfered: NULL — counted as a trade, never as a number
        s.add(
            _position(
                user_id=uid,
                final_pnl=None,
                tag="human_interfered",
                closed_at=_T0 + timedelta(days=3),
            )
        )
        # a literal zero under a non-priced tag must not be summed either
        s.add(
            _position(
                user_id=uid,
                final_pnl=Decimal("0"),
                tag="human_interfered",
                closed_at=_T0 + timedelta(days=4),
            )
        )
        # still open → not a closed round trip
        s.add(_position(user_id=uid, status="open", final_pnl=None, tag=None, closed_at=None))
        # a subscriber's fan-out position and another user's — not this owner's view
        s.add(
            _position(
                user_id=uid,
                final_pnl=Decimal("999"),
                tag="bot_only",
                closed_at=_T0,
                subscription_id=uuid.uuid4(),
            )
        )
        s.add(
            _position(user_id=uuid.uuid4(), final_pnl=Decimal("999"), tag="bot_only", closed_at=_T0)
        )
        await s.commit()

    client = _client(db_maker, monkeypatch, uid)
    body = client.get("/api/users/me/trades/stats").json()
    assert body["total_trades"] == 4
    assert body["priced_trades"] == 2
    assert body["unpriced_trades"] == 2
    assert body["executions_total"] == 2
    assert Decimal(body["total_pnl"]) == Decimal("60")
    assert body["win_rate"] == 50.0
    assert Decimal(body["avg_pnl_per_trade"]) == Decimal("30")
    assert Decimal(body["best_trade_pnl"]) == Decimal("100")
    assert Decimal(body["worst_trade_pnl"]) == Decimal("-40")
    assert body["pnl_basis"] == "net_of_estimated_costs"
    assert [(Decimal(p["pnl"]), p["attribution"]) for p in body["curve"]] == [
        (Decimal("100"), "bot_only"),
        (Decimal("-40"), "account_flat"),
    ]


@pytest.mark.asyncio
async def test_stats_on_an_empty_account_are_zero_not_an_error(db_maker, monkeypatch) -> None:
    client = _client(db_maker, monkeypatch, uuid.uuid4())
    body = client.get("/api/users/me/trades/stats").json()
    assert body["total_trades"] == 0 and body["priced_trades"] == 0
    assert body["total_pnl"] == "0" and body["win_rate"] == 0.0 and body["curve"] == []
