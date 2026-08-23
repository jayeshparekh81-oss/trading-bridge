"""Bounded + budgeted broker position batch.

The property that matters on a webhook path: latency is bounded by the BUDGET,
not by the subscriber count, and anything unresolved is POSITION_UNKNOWN so the
caller places nothing.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.broker_position_batch import (
    POSITION_UNKNOWN,
    gather_broker_positions,
)

# ═══════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_all_fast_calls_resolve():
    async def fetch(k):
        return f"pos-{k}"

    out = await gather_broker_positions([1, 2, 3], fetch)
    assert out == {1: "pos-1", 2: "pos-2", 3: "pos-3"}


@pytest.mark.asyncio
async def test_none_is_preserved_as_flat_not_unknown():
    """None = broker says FLAT (evidence). Must NOT become UNKNOWN."""

    async def fetch(k):
        return None

    out = await gather_broker_positions(["a"], fetch)
    assert out["a"] is None
    assert out["a"] is not POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_empty_input():
    async def fetch(k):  # pragma: no cover
        raise AssertionError("should not be called")

    assert await gather_broker_positions([], fetch) == {}


# ═══════════════════════════════════════════════════════════════════════
# Fail-safe: every failure mode → UNKNOWN
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_slow_call_times_out_to_unknown():
    async def fetch(k):
        await asyncio.sleep(5)
        return "never"

    out = await gather_broker_positions(["slow"], fetch, per_call_timeout=0.05)
    assert out["slow"] is POSITION_UNKNOWN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc", [ConnectionError("down"), ValueError("garbage"), RuntimeError("boom")]
)
async def test_raising_call_is_unknown(exc):
    async def fetch(k):
        raise exc

    out = await gather_broker_positions(["x"], fetch)
    assert out["x"] is POSITION_UNKNOWN


@pytest.mark.asyncio
async def test_one_slow_broker_does_not_poison_the_others():
    async def fetch(k):
        if k == "slow":
            await asyncio.sleep(5)
        return f"pos-{k}"

    out = await gather_broker_positions(
        ["a", "slow", "b"], fetch, per_call_timeout=0.05
    )
    assert out["a"] == "pos-a"
    assert out["b"] == "pos-b"
    assert out["slow"] is POSITION_UNKNOWN


# ═══════════════════════════════════════════════════════════════════════
# THE WEBHOOK PROPERTY — latency bounded by budget, not by N
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_large_subscriber_list_with_slow_brokers_respects_budget():
    """200 subscribers, every broker slow → still returns within the budget."""
    n = 200

    async def fetch(k):
        await asyncio.sleep(10)          # every broker hangs
        return "never"

    started = time.monotonic()
    out = await gather_broker_positions(
        range(n), fetch,
        per_call_timeout=2.0, concurrency=16, total_budget=0.4,
    )
    elapsed = time.monotonic() - started

    # Bounded by the BUDGET, not by n * per_call_timeout (which would be 400s).
    assert elapsed < 2.0, f"took {elapsed:.2f}s — budget was not enforced"
    assert len(out) == n                       # every key present
    assert all(v is POSITION_UNKNOWN for v in out.values())


@pytest.mark.asyncio
async def test_budget_exhaustion_leaves_unreached_keys_unknown():
    """Keys never even started must still be present and UNKNOWN."""
    n = 100
    seen: list[int] = []

    async def fetch(k):
        seen.append(k)
        await asyncio.sleep(10)
        return "never"

    out = await gather_broker_positions(
        range(n), fetch, per_call_timeout=5.0, concurrency=4, total_budget=0.2
    )

    assert len(seen) < n                       # we never got to them all
    assert len(out) == n                       # …but all keys are accounted for
    assert all(v is POSITION_UNKNOWN for v in out.values())


@pytest.mark.asyncio
async def test_concurrency_limit_is_respected():
    in_flight = 0
    peak = 0

    async def fetch(k):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return k

    await gather_broker_positions(range(50), fetch, concurrency=5, total_budget=10)
    assert peak <= 5, f"peak concurrency {peak} exceeded the limit"


@pytest.mark.asyncio
async def test_partial_results_survive_budget_expiry():
    """Fast ones keep their real answers; slow ones go UNKNOWN."""

    async def fetch(k):
        if k % 2 == 0:
            return f"pos-{k}"
        await asyncio.sleep(10)
        return "never"

    out = await gather_broker_positions(
        range(10), fetch, per_call_timeout=5.0, concurrency=10, total_budget=0.3
    )
    assert out[0] == "pos-0"
    assert out[2] == "pos-2"
    assert out[1] is POSITION_UNKNOWN
    assert out[3] is POSITION_UNKNOWN


# ═══════════════════════════════════════════════════════════════════════
# The sentinel must be impossible to confuse with "flat"
# ═══════════════════════════════════════════════════════════════════════


def test_unknown_sentinel_refuses_truthiness():
    """`if not pos:` would silently conflate UNKNOWN with flat — make it loud."""
    with pytest.raises(TypeError, match="no truth value"):
        bool(POSITION_UNKNOWN)


def test_unknown_is_not_none():
    assert POSITION_UNKNOWN is not None
