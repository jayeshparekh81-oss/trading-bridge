"""REAL broker-position adapter for subscribers — READ-ONLY.

Supplies the ``fetch_broker_positions`` callable that the fan-out gate
(:class:`app.services.marketplace_fanout.BrokerBackedPositionProvider`) and the
drift worker (:mod:`app.workers.subscriber_drift_pass`) were already built
against, so neither of them changes.

    async (subscription_id) -> list[Position]

THE ONE RULE THAT MATTERS
-------------------------
**Every failure RAISES.** Invalid session, auth error, rate limit, timeout,
missing/unusable credential, ownership mismatch, malformed row — all raise
:class:`SubscriberPositionUnavailableError`. The batch layer converts a raise into
``POSITION_UNKNOWN`` and the drift service treats it as absence of evidence.

There is deliberately NO code path that returns ``[]`` on an error, because an
empty list means "the broker confirmed this account is FLAT" — a statement that
authorises an entry and permits a flip to MANUAL. Returning it when we simply
could not ask would be a lie with money attached.

CREDENTIAL ISOLATION
--------------------
A subscriber is only ever read through THEIR OWN credential. Ownership is
enforced twice: the resolution SELECT is scoped by ``user_id``, and the check is
re-asserted **immediately before decryption**, which is the point where a leak
would become real. A mismatch raises and NEVER falls back to another credential.

READ-ONLY, AND NO LOGIN
-----------------------
Only ``is_session_valid`` and ``get_positions`` are called. If the session is
invalid we RAISE rather than calling ``login()``: token refresh belongs to the
existing host cron, and logging in from a webhook-reachable path would mean a
login storm across N subscriber accounts. No order method is ever reachable.

RATE LIMITS
-----------
Dhan's per-account limits are per client-id, and every subscriber uses their own
account, so concurrency across accounts is not the risk — repeatedly hitting ONE
account is. Two guards: ``get_positions()`` runs at most ONCE per credential per
pass (memoised, never per position), and a per-user 5/sec pre-flight reuses the
same Redis helper as ``dhan_historical``. A 429 / DH-906 surfaces as
:class:`BrokerRateLimitError` and is re-raised as unavailable — never flat.

IMPORT DISCIPLINE
-----------------
Must NOT import ``app.services.marketplace_fanout`` (an invariant test pins it
to two sanctioned importers). Its ``resolve_subscriber_credential`` is therefore
not importable here, so the ownership-scoped resolution is reimplemented below
with identical semantics (explicit -> fallback -> none). Duplicating a security
check AT the security boundary is deliberate, not accidental.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import rate_limit_check
from app.db.models.broker_credential import BrokerCredential

logger = structlog.get_logger(__name__)

#: Per-user pre-flight, mirroring dhan_historical's proven 5/sec window.
RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 1


class SubscriberPositionUnavailableError(RuntimeError):
    """We could not obtain this subscriber's live positions.

    Raised for EVERY failure mode. The caller converts it to
    ``POSITION_UNKNOWN``; it must never be downgraded to an empty list.
    """


async def _build_broker(cred: BrokerCredential):
    """Decrypt a credential row and construct its broker.

    Mirrors ``reconciliation_loop._build_broker`` (lazy imports keep this module
    importable when the broker layer is monkeypatched in tests).
    """
    from app.brokers.registry import get_broker_class
    from app.core.security import decrypt_credential
    from app.schemas.broker import BrokerCredentials

    creds = BrokerCredentials(
        broker=cred.broker_name,
        user_id=str(cred.user_id),
        client_id=decrypt_credential(cred.client_id_enc),
        api_key=decrypt_credential(cred.api_key_enc),
        api_secret=decrypt_credential(cred.api_secret_enc),
        access_token=(
            decrypt_credential(cred.access_token_enc)
            if cred.access_token_enc
            else None
        ),
        refresh_token=(
            decrypt_credential(cred.refresh_token_enc)
            if cred.refresh_token_enc
            else None
        ),
        token_expires_at=cred.token_expires_at,
    )
    return get_broker_class(creds.broker)(creds)


async def _resolve_own_credential(
    db: AsyncSession, *, subscriber_id: uuid.UUID, explicit_id: uuid.UUID | None
) -> BrokerCredential:
    """The subscriber's OWN active credential. Ownership-scoped both ways.

    Raises :class:`SubscriberPositionUnavailableError` when there is none — never
    returns someone else's credential, and never returns None.
    """
    if explicit_id is not None:
        row = await db.get(BrokerCredential, explicit_id)
        if row is not None and row.user_id == subscriber_id and row.is_active:
            return row
        # An explicit id that is not theirs (or inactive) does NOT silently fall
        # back — that is exactly how a cross-account leak would start.
        if row is not None and row.user_id != subscriber_id:
            logger.error(
                "subscriber_positions.credential_ownership_mismatch",
                subscriber_id=str(subscriber_id),
                credential_id=str(explicit_id),
            )
            raise SubscriberPositionUnavailableError(
                "credential does not belong to this subscriber"
            )

    stmt = (
        select(BrokerCredential)
        .where(
            BrokerCredential.user_id == subscriber_id,
            BrokerCredential.is_active.is_(True),
        )
        .order_by(BrokerCredential.created_at.desc())
        .limit(1)
    )
    fallback = (await db.execute(stmt)).scalar_one_or_none()
    if fallback is None:
        raise SubscriberPositionUnavailableError(
            "subscriber has no active broker credential"
        )
    return fallback


def make_subscriber_position_fetcher(
    db: AsyncSession,
    subscribers,
    *,
    build_broker=None,
    enforce_rate_limit: bool = True,
):
    """Build the ``async (subscription_id) -> list[Position]`` fetcher.

    ``subscribers`` is any iterable of objects carrying ``subscription_id``,
    ``subscriber_id`` and (optionally) ``broker_credential_id`` — duck-typed so
    this module needs no import from the fan-out.

    The returned callable memoises per CREDENTIAL, so a pass touches each
    broker account at most once no matter how many positions or subscriptions
    map to it.
    """
    builder = build_broker or _build_broker
    by_subscription: dict[uuid.UUID, Any] = {
        s.subscription_id: s for s in (subscribers or [])
    }
    # credential_id -> list[Position] (populated at most once per pass)
    memo: dict[uuid.UUID, list[Any]] = {}

    async def fetch(subscription_id: uuid.UUID):
        sub = by_subscription.get(subscription_id)
        if sub is None:
            raise SubscriberPositionUnavailableError(
                f"unknown subscription {subscription_id}"
            )

        cred = await _resolve_own_credential(
            db,
            subscriber_id=sub.subscriber_id,
            explicit_id=getattr(sub, "broker_credential_id", None),
        )

        if cred.id in memo:
            return memo[cred.id]

        # ── OWNERSHIP RE-ASSERTED AT THE DECRYPTION BOUNDARY ──────────────
        # This is the last line before secrets are decrypted and a broker is
        # built. If it ever disagrees with the resolution above, we stop —
        # decrypting someone else's credential is the severe failure.
        if cred.user_id != sub.subscriber_id:
            logger.error(
                "subscriber_positions.ownership_reassert_failed",
                subscriber_id=str(sub.subscriber_id),
                credential_user_id=str(cred.user_id),
                credential_id=str(cred.id),
            )
            raise SubscriberPositionUnavailableError(
                "credential ownership re-assertion failed — refusing to decrypt"
            )
        if not cred.is_active:
            raise SubscriberPositionUnavailableError("credential is inactive")

        # ── Per-user pre-flight (their account, their budget) ─────────────
        if enforce_rate_limit:
            try:
                allowed = await rate_limit_check(
                    f"subscriber_positions:{cred.user_id}",
                    max_requests=RATE_LIMIT_MAX_REQUESTS,
                    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
                )
            except Exception as exc:  # limiter unavailable => unknown, not flat
                raise SubscriberPositionUnavailableError(
                    f"rate-limit check failed: {exc}"
                ) from exc
            if not allowed:
                raise SubscriberPositionUnavailableError(
                    "per-user rate limit exceeded"
                )

        try:
            broker = await builder(cred)
        except Exception as exc:
            raise SubscriberPositionUnavailableError(
                f"could not build broker: {exc}"
            ) from exc

        # READ-ONLY. An invalid session RAISES — we never call login() here:
        # token refresh is the host cron's job, and logging in from a
        # webhook-reachable path would storm N subscriber accounts.
        try:
            valid = await broker.is_session_valid()
        except Exception as exc:
            raise SubscriberPositionUnavailableError(
                f"session check failed: {exc}"
            ) from exc
        if not valid:
            raise SubscriberPositionUnavailableError(
                "broker session invalid (refresh is the cron's job; not "
                "logging in from this path)"
            )

        try:
            positions = await broker.get_positions()
        except Exception as exc:
            # Includes BrokerRateLimitError (429 / DH-906), auth and connection
            # errors. All of them mean UNKNOWN — never "flat".
            raise SubscriberPositionUnavailableError(
                f"get_positions failed: {type(exc).__name__}: {exc}"
            ) from exc

        if positions is None:
            raise SubscriberPositionUnavailableError("broker returned no position data")

        rows = list(positions)
        for p in rows:
            # A malformed row means we do not actually understand this account's
            # state, so the whole answer is untrustworthy.
            if not hasattr(p, "symbol") or not hasattr(p, "quantity"):
                raise SubscriberPositionUnavailableError(
                    "malformed position row from broker"
                )

        memo[cred.id] = rows
        logger.info(
            "subscriber_positions.fetched",
            subscription_id=str(subscription_id),
            credential_id=str(cred.id),
            positions=len(rows),
        )
        return rows

    return fetch


__all__ = [
    "RATE_LIMIT_MAX_REQUESTS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "SubscriberPositionUnavailableError",
    "make_subscriber_position_fetcher",
]
