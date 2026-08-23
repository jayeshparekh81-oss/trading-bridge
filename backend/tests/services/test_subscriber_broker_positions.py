"""Real subscriber broker-position adapter — READ-ONLY, own-credential only.

The property everything else rests on: NO failure mode may produce an empty
list. ``[]`` means "the broker confirmed this account is flat", which authorises
an entry and permits a flip to MANUAL. Every failure must RAISE so the batch
layer turns it into POSITION_UNKNOWN.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.services.subscriber_broker_positions import (
    SubscriberPositionUnavailableError,
    make_subscriber_position_fetcher,
)


@dataclass
class FakePos:
    symbol: str
    quantity: int = 2


@dataclass
class FakeSub:
    subscription_id: uuid.UUID
    subscriber_id: uuid.UUID
    broker_credential_id: uuid.UUID | None = None


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-sbp-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


async def _seed_cred(maker, *, user_id, is_active=True) -> uuid.UUID:
    async with maker() as s:
        c = BrokerCredential(
            user_id=user_id, broker_name="dhan",
            client_id_enc="x", api_key_enc="x", api_secret_enc="x",
            is_active=is_active, created_at=datetime.now(UTC),
        )
        s.add(c)
        await s.commit()
        await s.refresh(c)
        return c.id


def _broker(positions=None, *, session_valid=True, positions_exc=None):
    b = MagicMock()
    b.is_session_valid = AsyncMock(return_value=session_valid)
    b.login = AsyncMock()
    b.place_order = AsyncMock()
    if positions_exc is not None:
        b.get_positions = AsyncMock(side_effect=positions_exc)
    else:
        b.get_positions = AsyncMock(return_value=positions or [])
    return b


def _builder(broker, *, seen=None):
    async def _b(cred):
        if seen is not None:
            seen.append(cred)
        return broker
    return _b


# ═══════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_returns_the_subscribers_live_positions(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)
    brk = _broker([FakePos("BSE26AUGFUT")])

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(brk), enforce_rate_limit=False)
        out = await fetch(sub.subscription_id)

    assert [p.symbol for p in out] == ["BSE26AUGFUT"]


@pytest.mark.asyncio
async def test_empty_list_only_when_the_broker_really_says_flat(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([])), enforce_rate_limit=False)
        assert await fetch(sub.subscription_id) == []


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ OWN-CREDENTIAL ISOLATION
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_subscriber_a_never_sees_subscriber_b_positions(db_maker):
    a_uid, b_uid = uuid.uuid4(), uuid.uuid4()
    a_cred = await _seed_cred(db_maker, user_id=a_uid)
    b_cred = await _seed_cred(db_maker, user_id=b_uid)
    a = FakeSub(uuid.uuid4(), a_uid)
    b = FakeSub(uuid.uuid4(), b_uid)

    seen: list = []
    per_cred = {a_cred: [FakePos("AAA26AUGFUT")], b_cred: [FakePos("BBB26AUGFUT")]}

    async def builder(cred):
        seen.append(cred.id)
        return _broker(per_cred[cred.id])

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [a, b], build_broker=builder, enforce_rate_limit=False)
        a_out = await fetch(a.subscription_id)
        b_out = await fetch(b.subscription_id)

    assert [p.symbol for p in a_out] == ["AAA26AUGFUT"]
    assert [p.symbol for p in b_out] == ["BBB26AUGFUT"]
    assert seen == [a_cred, b_cred]          # each used only their own


@pytest.mark.asyncio
async def test_explicit_credential_owned_by_someone_else_raises_before_decrypting(db_maker):
    """The severe case: a subscription pointing at another user's credential."""
    victim, attacker = uuid.uuid4(), uuid.uuid4()
    victim_cred = await _seed_cred(db_maker, user_id=victim)
    await _seed_cred(db_maker, user_id=attacker)

    sub = FakeSub(uuid.uuid4(), attacker, broker_credential_id=victim_cred)
    decrypted: list = []

    async def builder(cred):
        decrypted.append(cred.id)            # would mean secrets were decrypted
        return _broker([FakePos("VICTIM26AUGFUT")])

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=builder, enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError, match="does not belong"):
            await fetch(sub.subscription_id)

    assert decrypted == [], "NO decryption may happen on an ownership mismatch"


@pytest.mark.asyncio
async def test_ownership_mismatch_never_falls_back_to_another_credential(db_maker):
    """A bad explicit id must NOT silently resolve to the attacker's own cred."""
    victim, attacker = uuid.uuid4(), uuid.uuid4()
    victim_cred = await _seed_cred(db_maker, user_id=victim)
    await _seed_cred(db_maker, user_id=attacker)   # attacker HAS one

    sub = FakeSub(uuid.uuid4(), attacker, broker_credential_id=victim_cred)
    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([])), enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError):
            await fetch(sub.subscription_id)     # raises, not a fallback result


@pytest.mark.asyncio
async def test_reassert_at_decryption_boundary_blocks_a_tampered_row(db_maker):
    """Even if resolution were bypassed, the pre-decrypt check must stop it."""
    uid, other = uuid.uuid4(), uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    decrypted: list = []

    async def builder(cred):
        decrypted.append(cred.id)
        return _broker([])

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=builder, enforce_rate_limit=False)
        # Simulate the row coming back owned by someone else.
        import app.services.subscriber_broker_positions as mod

        async def _tampered(_db, *, subscriber_id, explicit_id):
            c = MagicMock()
            c.id = uuid.uuid4()
            c.user_id = other          # NOT the subscriber
            c.is_active = True
            return c

        orig = mod._resolve_own_credential
        mod._resolve_own_credential = _tampered
        try:
            with pytest.raises(SubscriberPositionUnavailableError, match="re-assertion"):
                await fetch(sub.subscription_id)
        finally:
            mod._resolve_own_credential = orig

    assert decrypted == []


@pytest.mark.asyncio
async def test_no_active_credential_raises(db_maker):
    sub = FakeSub(uuid.uuid4(), uuid.uuid4())
    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([])), enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError, match="no active broker"):
            await fetch(sub.subscription_id)


@pytest.mark.asyncio
async def test_inactive_credential_raises(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid, is_active=False)
    sub = FakeSub(uuid.uuid4(), uid)
    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([])), enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError):
            await fetch(sub.subscription_id)


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ EVERY failure raises — never []
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invalid_session_raises_and_login_is_never_called(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)
    brk = _broker([], session_valid=False)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(brk), enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError, match="session invalid"):
            await fetch(sub.subscription_id)

    brk.login.assert_not_awaited()        # option (b): no login storms
    brk.get_positions.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ConnectionError("broker down"),
        TimeoutError("no answer"),
        ValueError("garbled json"),
        RuntimeError("auth rejected"),
    ],
)
async def test_get_positions_failure_raises(db_maker, exc):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker(positions_exc=exc)),
            enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError):
            await fetch(sub.subscription_id)


@pytest.mark.asyncio
async def test_broker_rate_limit_error_raises(db_maker):
    from app.core.exceptions import BrokerRateLimitError

    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)
    exc = BrokerRateLimitError("429", "dhan")

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker(positions_exc=exc)),
            enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError):
            await fetch(sub.subscription_id)


@pytest.mark.asyncio
async def test_malformed_row_raises(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([object()])),
            enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError, match="malformed"):
            await fetch(sub.subscription_id)


@pytest.mark.asyncio
async def test_none_response_raises(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)
    brk = _broker()
    brk.get_positions = AsyncMock(return_value=None)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(brk), enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError):
            await fetch(sub.subscription_id)


@pytest.mark.asyncio
async def test_unknown_subscription_raises(db_maker):
    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [], build_broker=_builder(_broker([])), enforce_rate_limit=False)
        with pytest.raises(SubscriberPositionUnavailableError):
            await fetch(uuid.uuid4())


@pytest.mark.asyncio
async def test_rate_limit_exceeded_raises(db_maker, monkeypatch):
    import app.services.subscriber_broker_positions as mod

    async def denied(*_a, **_k):
        return False

    monkeypatch.setattr(mod, "rate_limit_check", denied)
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([])))
        with pytest.raises(SubscriberPositionUnavailableError, match="rate limit"):
            await fetch(sub.subscription_id)


@pytest.mark.asyncio
async def test_limiter_outage_raises_rather_than_proceeding(db_maker, monkeypatch):
    import app.services.subscriber_broker_positions as mod

    async def boom(*_a, **_k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(mod, "rate_limit_check", boom)
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([])))
        with pytest.raises(SubscriberPositionUnavailableError, match="rate-limit"):
            await fetch(sub.subscription_id)


def test_no_code_path_returns_empty_on_error():
    """Static guard: `return []` must not exist anywhere in the module."""
    import inspect

    from app.services import subscriber_broker_positions as mod

    src = inspect.getsource(mod)
    code = src.replace(mod.__doc__ or "", "", 1)
    assert "return []" not in code


# ═══════════════════════════════════════════════════════════════════════
# Memoisation — one get_positions per credential per pass
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_one_get_positions_per_credential_even_for_many_subscriptions(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    subs = [FakeSub(uuid.uuid4(), uid) for _ in range(5)]
    brk = _broker([FakePos("BSE26AUGFUT")])

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, subs, build_broker=_builder(brk), enforce_rate_limit=False)
        for s in subs:
            await fetch(s.subscription_id)

    assert brk.get_positions.await_count == 1


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ READ-ONLY
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_never_places_an_order(db_maker):
    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)
    brk = _broker([FakePos("BSE26AUGFUT")])

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(brk), enforce_rate_limit=False)
        await fetch(sub.subscription_id)

    brk.place_order.assert_not_awaited()
    brk.login.assert_not_awaited()


def test_module_has_no_order_or_login_calls():
    import inspect

    from app.services import subscriber_broker_positions as mod

    src = inspect.getsource(mod)
    code = src.replace(mod.__doc__ or "", "", 1)
    for forbidden in ("place_order(", "square_off(", ".login("):
        assert forbidden not in code, f"adapter must not call {forbidden!r}"


def test_does_not_import_marketplace_fanout():
    import inspect

    from app.services import subscriber_broker_positions as mod

    src = inspect.getsource(mod)
    assert "from app.services.marketplace_fanout" not in src
    assert "import marketplace_fanout" not in src


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION — through the existing gate
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_integration_gate_uses_the_real_adapter(db_maker):
    """Real adapter + real BrokerBackedPositionProvider, fake broker only."""
    from app.services.broker_position_batch import POSITION_UNKNOWN
    from app.services.marketplace_fanout import BrokerBackedPositionProvider

    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(_broker([FakePos("BSE26AUGFUT")])),
            enforce_rate_limit=False)
        provider = BrokerBackedPositionProvider(fetch)
        await provider.prefetch([sub.subscription_id])

        # Stored canonical spelling must match the broker's compact one.
        stored = MagicMock()
        stored.symbol = "BSE-AUG2026-FUT"

        class _Res:
            def scalars(self):
                return self

            def first(self):
                return stored

        db_stub = MagicMock()

        async def _execute(*_a, **_k):
            return _Res()

        db_stub.execute = _execute

        out = await provider.find_open(
            db_stub, strategy_id=uuid.uuid4(), subscription_id=sub.subscription_id
        )

    assert out is stored
    assert out is not POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_integration_adapter_failure_becomes_position_unknown(db_maker):
    """The whole point: adapter raises -> gate sees UNKNOWN -> places nothing."""
    from app.services.broker_position_batch import POSITION_UNKNOWN
    from app.services.marketplace_fanout import BrokerBackedPositionProvider

    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub],
            build_broker=_builder(_broker([], session_valid=False)),
            enforce_rate_limit=False)
        provider = BrokerBackedPositionProvider(fetch)
        await provider.prefetch([sub.subscription_id])

        db_stub = MagicMock()

        async def _execute(*_a, **_k):
            raise AssertionError("should not reach the stored lookup path")

        db_stub.execute = AsyncMock(side_effect=Exception("unused"))
        try:
            out = await provider.find_open(
                db_stub, strategy_id=uuid.uuid4(),
                subscription_id=sub.subscription_id,
            )
        except Exception:
            out = POSITION_UNKNOWN     # stored lookup is irrelevant here

    assert out is POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_integration_slow_broker_hits_the_budget_as_unknown(db_maker):
    from app.services.broker_position_batch import POSITION_UNKNOWN
    from app.services.marketplace_fanout import BrokerBackedPositionProvider

    uid = uuid.uuid4()
    await _seed_cred(db_maker, user_id=uid)
    sub = FakeSub(uuid.uuid4(), uid)

    brk = _broker()

    async def slow():
        await asyncio.sleep(5)
        return []

    brk.get_positions = slow

    async with db_maker() as db:
        fetch = make_subscriber_position_fetcher(
            db, [sub], build_broker=_builder(brk), enforce_rate_limit=False)
        provider = BrokerBackedPositionProvider(fetch, per_call_timeout=0.05)
        await provider.prefetch([sub.subscription_id])
        assert provider._cache[sub.subscription_id] is POSITION_UNKNOWN
