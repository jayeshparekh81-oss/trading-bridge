"""Bounded, budgeted batch of broker position checks.

WHY THIS EXISTS
---------------
The subscriber position gate runs on a WEBHOOK-reachable path. A naive
implementation asks each subscriber's broker in sequence, so latency grows with
subscriber count (3s x N) and one slow broker can stall the whole webhook. That
is unacceptable: TradingView will time out, and a stalled webhook is a missed
signal for the OWNER as well.

THE CONTRACT
------------
1. **Bounded concurrency** — at most :data:`MAX_CONCURRENCY` broker calls are in
   flight at once, so we neither serialise nor stampede.
2. **Per-call timeout** — no single broker can exceed
   :data:`PER_CALL_TIMEOUT_SECONDS`.
3. **Total budget** — the whole batch is capped at
   :data:`TOTAL_BUDGET_SECONDS`. When it expires, everything still in flight is
   cancelled. Webhook latency is therefore bounded by the budget, NOT by N.

FAIL-SAFE BY CONSTRUCTION
-------------------------
Every key starts as :data:`POSITION_UNKNOWN` and is only ever overwritten by a
*definite* answer. So a timeout, an exception, a cancellation, a budget
exhaustion, or a subscriber we never even got to all yield UNKNOWN — the state
that makes the caller place NOTHING. There is no code path that turns a failure
into "flat", because "flat" would authorise an order.

    Absence of evidence is never evidence of absence.

WORST-CASE ARITHMETIC (see the constants below)
-----------------------------------------------
    per-call timeout T = 2.0s, concurrency C = 16, total budget B = 6.0s

    * webhook latency ceiling  = B + scheduling overhead  ~= 6s, for ANY N.
    * subscribers fully checked within budget = floor(B / T) * C = 3 * 16 = 48.
    * beyond that, the remainder resolve UNKNOWN -> nothing is placed for them
      (safe, and logged loudly as ``budget_exhausted``).

That last line is a deliberate trade: past ~48 subscribers we prefer a bounded
webhook and no order over an unbounded webhook and a possibly-wrong order.
Raising C raises throughput within the same latency ceiling.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

#: Ceiling on ONE broker position call.
PER_CALL_TIMEOUT_SECONDS = 2.0

#: Maximum broker calls in flight at once across the batch. Each subscriber has
#: their OWN credential/account, so this is concurrency across accounts rather
#: than hammering a single one.
MAX_CONCURRENCY = 16

#: Ceiling on the WHOLE batch. This is what bounds webhook latency.
TOTAL_BUDGET_SECONDS = 6.0


class _PositionUnknown:
    """Sentinel: the broker could not be asked, or did not answer in time.

    Deliberately NOT ``None``: ``None`` means the broker positively reported
    FLAT (evidence), whereas this means we have NO evidence either way. Callers
    must treat it as "do not act".
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "POSITION_UNKNOWN"

    def __bool__(self) -> bool:
        # Falsy would invite `if not pos:` to conflate UNKNOWN with flat.
        # Raise instead so that mistake is loud at the first attempt.
        raise TypeError(
            "POSITION_UNKNOWN has no truth value — compare with `is "
            "POSITION_UNKNOWN` explicitly (it is NOT the same as flat/None)."
        )


POSITION_UNKNOWN = _PositionUnknown()

K = TypeVar("K")


async def gather_broker_positions(
    keys: Sequence[K],
    fetch: Callable[[K], Awaitable[Any]],
    *,
    per_call_timeout: float = PER_CALL_TIMEOUT_SECONDS,
    concurrency: int = MAX_CONCURRENCY,
    total_budget: float = TOTAL_BUDGET_SECONDS,
) -> dict[K, Any]:
    """Resolve a position for every key, bounded by concurrency and budget.

    Returns ``{key: result}`` where result is whatever ``fetch`` returned (which
    may legitimately be ``None`` = broker says flat) or :data:`POSITION_UNKNOWN`
    when no definite answer was obtained for any reason.

    The returned dict ALWAYS contains every key — callers can index it without
    a membership check, and an unfinished key is already fail-safe.
    """
    # Pre-seed every key UNKNOWN. This is the fail-safe: any key we do not
    # positively resolve keeps this value.
    out: dict[K, Any] = dict.fromkeys(keys, POSITION_UNKNOWN)
    if not keys:
        return out

    sem = asyncio.Semaphore(max(1, concurrency))
    timed_out = 0
    failed = 0

    async def _one(key: K) -> None:
        nonlocal timed_out, failed
        async with sem:
            try:
                out[key] = await asyncio.wait_for(fetch(key), timeout=per_call_timeout)
            except TimeoutError:
                timed_out += 1
                logger.warning(
                    "broker_position.call_timeout",
                    key=str(key),
                    timeout_s=per_call_timeout,
                )
            except asyncio.CancelledError:
                # Budget expired while this call was in flight. Leave it
                # UNKNOWN and let the cancellation propagate.
                raise
            except Exception as exc:
                failed += 1
                logger.warning(
                    "broker_position.call_failed",
                    key=str(key),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

    tasks = [asyncio.create_task(_one(k)) for k in keys]
    done, pending = await asyncio.wait(tasks, timeout=total_budget)

    if pending:
        for task in pending:
            task.cancel()
        # Reap the cancellations so the loop does not warn about pending tasks.
        await asyncio.gather(*pending, return_exceptions=True)
        logger.error(
            "broker_position.budget_exhausted",
            total_budget_s=total_budget,
            requested=len(keys),
            completed=len(done),
            unresolved=len(pending),
            note="unresolved subscribers are POSITION_UNKNOWN — nothing placed",
        )

    unknown = sum(1 for v in out.values() if v is POSITION_UNKNOWN)
    logger.info(
        "broker_position.batch_done",
        requested=len(keys),
        unknown=unknown,
        timed_out=timed_out,
        failed=failed,
        budget_exhausted=bool(pending),
    )
    return out


__all__ = [
    "MAX_CONCURRENCY",
    "PER_CALL_TIMEOUT_SECONDS",
    "POSITION_UNKNOWN",
    "TOTAL_BUDGET_SECONDS",
    "gather_broker_positions",
]
