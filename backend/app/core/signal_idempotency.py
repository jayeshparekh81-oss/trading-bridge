"""Per-``signal_id`` idempotency claim — Bug #2 (Phase 2C) helper.

Additive utility, intentionally **not yet wired into the live webhook
handler**. The production hot path in
:mod:`app.api.strategy_webhook` keeps its proven content-hash idempotency
(:func:`app.core.redis_client.set_idempotency_key`, namespace ``idem:``,
60 s TTL), which dedupes a TradingView retry even when the alert carries
no explicit ``signal_id``. This helper exists for the case where a caller
*does* mint a stable ``signal_id`` and wants a longer (1 h) suppression
window keyed on that id alone.

The single Redis ``SET key 1 NX EX`` is atomic, so two concurrent first-
time callers cannot both observe "first": exactly one gets ``True``.

See ``WEBHOOK_ASYNC_NOTES.md`` (repo root) for the failure-mode matrix
and the rationale for keeping the live path on the content-hash claim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import redis.asyncio as aioredis

#: Default suppression window. Bug #2 spec: 3600 s (1 h) — long enough to
#: absorb a retried alert that arrives well after the original, distinct
#: from the 60 s TradingView fast-retry window the content-hash claim
#: already covers.
SIGNAL_IDEMPOTENCY_TTL_SECONDS = 3600

#: Key namespace. Deliberately distinct from :mod:`app.core.redis_client`'s
#: ``idem:`` content-hash namespace so the two schemes never collide.
_SIGNAL_IDEM_PREFIX = "signal:idempotency"


def signal_idempotency_key(signal_id: str | UUID) -> str:
    """Return the Redis key for a ``signal_id`` idempotency slot."""
    return f"{_SIGNAL_IDEM_PREFIX}:{signal_id}"


async def check_and_set_signal_idempotent(
    redis_client: aioredis.Redis,
    signal_id: str | UUID,
    *,
    ttl_seconds: int = SIGNAL_IDEMPOTENCY_TTL_SECONDS,
) -> bool:
    """Atomically claim the idempotency slot for ``signal_id``.

    Returns ``True`` the first time a given ``signal_id`` is seen within
    the TTL window (caller should proceed), or ``False`` if a prior call
    already claimed it (caller should treat the request as a duplicate).

    Args:
        redis_client: An ``async`` Redis client. Required (no implicit
            singleton) so the live caller and tests both pass an explicit
            connection — mirrors the convention in
            :mod:`app.core.redis_client`.
        signal_id: Stable identifier for the inbound signal.
        ttl_seconds: Suppression window. Must be positive.

    Raises:
        ValueError: ``ttl_seconds`` is not positive — a non-expiring
            idempotency key would silently wedge a signal forever.
    """
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive — non-expiring slot forbidden.")
    # ``nx=True`` → only set if absent. redis-py returns ``True`` on a
    # successful set and ``None`` on conflict; normalise to bool.
    acquired = await redis_client.set(
        signal_idempotency_key(signal_id), "1", nx=True, ex=ttl_seconds
    )
    return bool(acquired)


__all__ = [
    "SIGNAL_IDEMPOTENCY_TTL_SECONDS",
    "check_and_set_signal_idempotent",
    "signal_idempotency_key",
]
