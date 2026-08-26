"""Broker-position gate on the subscriber fan-out (DIFF A).

The rule under test, in one line: an UNVERIFIED broker state must never
authorise an order. Entry and exit both place NOTHING on POSITION_UNKNOWN, and
every failure mode (timeout, exception, budget exhaustion, ambiguous symbol)
converges on that state.

Also pinned here: the DEFAULT paper path makes zero broker calls, so paper
subscribers keep byte-identical behaviour.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from app.services.broker_position_batch import POSITION_UNKNOWN
from app.services.marketplace_fanout import (
    BrokerBackedPositionProvider,
    PaperPositionProvider,
    _prefetch_if_broker_backed,
)


@dataclass
class FakeBrokerPos:
    symbol: str
    quantity: int = 2


@dataclass
class FakeStored:
    symbol: str
    remaining_quantity: int = 2
    status: str = "open"
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class FakeSub:
    subscription_id: uuid.UUID


def _provider(fetch, **kw):
    return BrokerBackedPositionProvider(fetch, **kw)


def _db_with(stored):
    """AsyncSession stub whose PaperPositionProvider lookup returns `stored`."""
    db = MagicMock()

    class _Res:
        def scalars(self):
            return self

        def first(self):
            return stored

    async def _execute(*_a, **_k):
        return _Res()

    db.execute = _execute
    return db


# ═══════════════════════════════════════════════════════════════════════
# Fail-safe: every failure mode → POSITION_UNKNOWN
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_broker_exception_yields_unknown():
    async def fetch(_sid):
        raise ConnectionError("broker down")

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(FakeStored("BSE-AUG2026-FUT")),
        strategy_id=uuid.uuid4(), subscription_id=sid,
    )
    assert out is POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_broker_timeout_yields_unknown():
    async def fetch(_sid):
        await asyncio.sleep(5)

    sid = uuid.uuid4()
    p = _provider(fetch, per_call_timeout=0.05)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(FakeStored("BSE-AUG2026-FUT")),
        strategy_id=uuid.uuid4(), subscription_id=sid,
    )
    assert out is POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_budget_exhaustion_yields_unknown_for_everyone():
    async def fetch(_sid):
        await asyncio.sleep(10)

    sids = [uuid.uuid4() for _ in range(50)]
    p = _provider(fetch, per_call_timeout=5.0, concurrency=4, total_budget=0.2)
    await p.prefetch(sids)
    db = _db_with(FakeStored("BSE-AUG2026-FUT"))
    for sid in sids:
        assert await p.find_open(
            db, strategy_id=uuid.uuid4(), subscription_id=sid
        ) is POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_missing_prefetch_is_unknown_not_stored_truth():
    """Forgetting prefetch must fail safe, not silently trust the stored row."""

    async def fetch(_sid):
        return []

    p = _provider(fetch)          # NO prefetch() call
    out = await p.find_open(
        _db_with(FakeStored("BSE-AUG2026-FUT")),
        strategy_id=uuid.uuid4(), subscription_id=uuid.uuid4(),
    )
    assert out is POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_ambiguous_symbol_is_unknown_never_flat():
    """A garbled broker symbol must not read as 'broker is flat'."""

    async def fetch(_sid):
        return [FakeBrokerPos("GARBAGE-!!!")]

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(FakeStored("BSE-AUG2026-FUT")),
        strategy_id=uuid.uuid4(), subscription_id=sid,
    )
    assert out is POSITION_UNKNOWN
    assert out is not None          # explicitly NOT "flat"


# ═══════════════════════════════════════════════════════════════════════
# Definite answers
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_broker_confirms_position_across_spellings():
    """Stored canonical vs broker compact must match, not read as flat."""

    async def fetch(_sid):
        return [FakeBrokerPos("BSE26AUGFUT")]

    sid = uuid.uuid4()
    stored = FakeStored("BSE-AUG2026-FUT")
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(stored), strategy_id=uuid.uuid4(), subscription_id=sid
    )
    assert out is stored             # confirmed → the stored row is returned


@pytest.mark.asyncio
async def test_broker_flat_while_stored_open_returns_none():
    """Customer closed on Dhan → broker confidently flat → caller closes nothing."""

    async def fetch(_sid):
        return []                    # broker holds nothing

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(FakeStored("BSE-AUG2026-FUT")),
        strategy_id=uuid.uuid4(), subscription_id=sid,
    )
    assert out is None               # → exit path emits skipped_no_position
    assert out is not POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_different_contract_is_flat_not_a_match():
    async def fetch(_sid):
        return [FakeBrokerPos("CDSL26AUGFUT")]

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(FakeStored("BSE-AUG2026-FUT")),
        strategy_id=uuid.uuid4(), subscription_id=sid,
    )
    assert out is None


@pytest.mark.asyncio
async def test_entry_blocked_when_broker_holds_it_but_we_have_no_stored_row():
    """THE re-entry bug: broker holds the contract, we have no record of it.

    Returning None here would let the entry through and DOUBLE the customer's
    exposure. The gate must report a position so the entry is skipped.
    """

    async def fetch(_sid):
        return [FakeBrokerPos("BSE26AUGFUT")]

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(None),                      # no stored row
        strategy_id=uuid.uuid4(),
        subscription_id=sid,
        symbol="BSE-AUG2026-FUT",            # entry passes the signal symbol
    )
    assert out is not None, "entry would have been allowed — re-entry bug"
    assert out is not POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_entry_allowed_when_broker_is_confidently_flat():
    async def fetch(_sid):
        return []

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(None), strategy_id=uuid.uuid4(),
        subscription_id=sid, symbol="BSE-AUG2026-FUT",
    )
    assert out is None                       # → entry proceeds


@pytest.mark.asyncio
async def test_exit_claims_nothing_when_we_have_no_stored_row():
    """Broker holds something we never recorded — do NOT try to close it."""

    async def fetch(_sid):
        return [FakeBrokerPos("BSE26AUGFUT")]

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    out = await p.find_open(
        _db_with(None), strategy_id=uuid.uuid4(),
        subscription_id=sid,                 # exit passes no symbol
    )
    assert out is None                       # → skipped_no_position


# ═══════════════════════════════════════════════════════════════════════
# Concurrency: one batch, not per-subscriber serial awaits
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_prefetch_is_one_bounded_batch_not_serial():
    in_flight = 0
    peak = 0

    async def fetch(_sid):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return []

    sids = [uuid.uuid4() for _ in range(20)]
    p = _provider(fetch, concurrency=5, total_budget=10)
    await p.prefetch(sids)
    assert peak > 1, "calls ran serially — the batch is not concurrent"
    assert peak <= 5, f"peak {peak} exceeded the concurrency limit"


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ The paper default must make ZERO broker calls
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paper_provider_is_not_broker_backed():
    assert PaperPositionProvider.BROKER_BACKED is False


@pytest.mark.asyncio
async def test_prefetch_is_a_noop_for_the_paper_provider():
    """No prefetch, no network — the paper path stays byte-identical."""
    paper = PaperPositionProvider()
    subs = [FakeSub(uuid.uuid4()) for _ in range(3)]
    await _prefetch_if_broker_backed(paper, subs)   # must not raise
    assert not hasattr(paper, "_cache")


@pytest.mark.asyncio
async def test_paper_provider_accepts_symbol_and_ignores_it():
    """Interface parity without behaviour change."""
    stored = FakeStored("BSE-AUG2026-FUT")
    out = await PaperPositionProvider().find_open(
        _db_with(stored), strategy_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(), symbol="ANYTHING-AT-ALL",
    )
    assert out is stored


@pytest.mark.asyncio
async def test_broker_provider_never_places_an_order(monkeypatch):
    """The gate only WITHHOLDS action — it must never place anything."""
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    async def fetch(_sid):
        return [FakeBrokerPos("BSE26AUGFUT")]

    sid = uuid.uuid4()
    p = _provider(fetch)
    await p.prefetch([sid])
    await p.find_open(
        _db_with(FakeStored("BSE-AUG2026-FUT")),
        strategy_id=uuid.uuid4(), subscription_id=sid,
    )
    spy.assert_not_called()
