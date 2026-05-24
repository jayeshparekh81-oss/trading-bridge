"""Per-``signal_id`` idempotency claim — Bug #2 (Phase 2C) helper, wired in
2026-05-24 for the broker-order at-least-once guard.

The webhook hot path keeps its proven content-hash idempotency
(:func:`app.core.redis_client.set_idempotency_key`, namespace ``idem:``,
60 s TTL) which dedupes a TradingView retry. This helper guards a *different*
layer: a Celery **worker** retry of an already-attempted broker order. The
key is ``signal:idempotency:{signal_id}:{action_kind}`` and is claimed
immediately before the broker ``place_order`` call (after the symbol/funds
pre-checks), so:

* a pre-send failure (bad symbol, insufficient funds) happens *before* the
  claim — no slot is taken, and a retry re-executes cleanly;
* once the broker call is initiated, the slot is held, so a retry after an
  *ambiguous* failure (Dhan accepted the order but the response was lost)
  cannot place a duplicate live order.

The single Redis ``SET key 1 NX EX`` is atomic, so two concurrent first-time
callers cannot both observe "first": exactly one gets ``True``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import redis.asyncio as aioredis

#: Suppression window. 3600 s (1 h) — long enough to absorb the full Celery
#: retry budget (``max_retries=3`` x backoff) plus operator latency, distinct
#: from the 60 s TradingView fast-retry window the content-hash claim covers.
SIGNAL_IDEMPOTENCY_TTL_SECONDS = 3600

#: Key namespace. Deliberately distinct from :mod:`app.core.redis_client`'s
#: ``idem:`` content-hash namespace so the two schemes never collide.
_SIGNAL_IDEM_PREFIX = "signal:idempotency"


def signal_idempotency_key(signal_id: str | UUID, action_kind: str) -> str:
    """Return the Redis key for a ``(signal_id, action_kind)`` slot.

    ``action_kind`` is part of the key so an ENTRY and a later EXIT for the
    same ``signal_id`` claim independent slots.
    """
    return f"{_SIGNAL_IDEM_PREFIX}:{signal_id}:{action_kind}"


async def check_and_set_signal_idempotent(
    redis_client: aioredis.Redis[Any],
    signal_id: str | UUID,
    action_kind: str,
    *,
    ttl_seconds: int = SIGNAL_IDEMPOTENCY_TTL_SECONDS,
) -> bool:
    """Atomically claim the idempotency slot for ``(signal_id, action_kind)``.

    Returns ``True`` the first time the slot is seen within the TTL window
    (caller should proceed to the broker call), or ``False`` if a prior call
    already claimed it (caller must NOT place a duplicate order).

    Args:
        redis_client: An ``async`` Redis client (explicit so tests inject a
            fake; mirrors :mod:`app.core.redis_client`).
        signal_id: Stable identifier for the inbound signal.
        action_kind: ``entry`` / ``partial`` / ``exit`` / ``sl_hit``.
        ttl_seconds: Suppression window. Must be positive.

    Raises:
        ValueError: ``ttl_seconds`` is not positive — a non-expiring slot
            would silently wedge a signal forever.
    """
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive — non-expiring slot forbidden.")
    acquired = await redis_client.set(
        signal_idempotency_key(signal_id, action_kind),
        "1",
        nx=True,
        ex=ttl_seconds,
    )
    return bool(acquired)


async def release_signal_idempotent(
    redis_client: aioredis.Redis[Any],
    signal_id: str | UUID,
    action_kind: str,
) -> None:
    """Release a previously-claimed slot.

    Used only when the caller can prove the broker order was **never sent**
    (so a retry must be allowed). The standard wiring places the claim AFTER
    the pre-send checks precisely so this rarely needs calling — but it
    exists for callers that claim earlier and must roll back on a
    confirmed-not-sent failure.
    """
    await redis_client.delete(signal_idempotency_key(signal_id, action_kind))


__all__ = [
    "SIGNAL_IDEMPOTENCY_TTL_SECONDS",
    "check_and_set_signal_idempotent",
    "release_signal_idempotent",
    "signal_idempotency_key",
]
