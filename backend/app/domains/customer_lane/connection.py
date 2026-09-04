"""``is_connected()`` — the single source of truth for "is this customer connected
right now?".

Load-bearing rules:
  * evaluated AT CALL TIME from current DB state; never from a precomputed list,
    a cached batch, or a snapshot taken earlier in the process
  * unknown is NEVER "connected"
  * no network call here; the broker-side probe seam is named and left unimplemented
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_credential
from app.db.models.customer_lane import CustomerBrokerLink, CustomerLinkStatus
from app.domains.customer_lane import config as lane_config


@dataclass(frozen=True)
class ConnectionStatus:
    connected: bool
    reason: str
    expires_at: datetime | None
    checked_at: datetime
    customer_id: uuid.UUID
    broker_client_id: str | None = None
    #: when the customer last completed a connect; status.py needs this to
    #: decide join eligibility WITHOUT reading raw link fields itself.
    connected_at: datetime | None = None


def probe_broker_side(customer_id: uuid.UUID) -> None:  # pragma: no cover - seam
    """SEAM ONLY — a future broker-side liveness probe. Deliberately unimplemented in
    this run; is_connected() reads stored state and makes no network call."""
    raise NotImplementedError("broker-side probe is a later stage; not implemented")


async def is_connected(session: AsyncSession, customer_id: uuid.UUID, *,
                       at: datetime | None = None) -> ConnectionStatus:
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cfg = lane_config.load()

    def no(reason: str, expires_at=None, cid=None) -> ConnectionStatus:
        return ConnectionStatus(False, reason, expires_at, now, customer_id, cid)

    # Read FRESH from the DB at call time. expire_all() defeats any identity-map
    # copy left over from an earlier read in this same session — the anti-caching
    # guarantee C1 asserts.
    session.expire_all()
    link = (await session.execute(
        select(CustomerBrokerLink).where(CustomerBrokerLink.customer_id == customer_id)
    )).scalar_one_or_none()

    if link is None:
        return no("no_broker_link")
    if link.status == CustomerLinkStatus.DISABLED:
        return no("link_disabled", link.token_expires_at, link.broker_client_id)
    if link.status == CustomerLinkStatus.NEVER_CONNECTED:
        return no("never_connected", link.token_expires_at, link.broker_client_id)
    if not link.access_token_enc:
        return no("no_access_token", link.token_expires_at, link.broker_client_id)

    try:
        decrypt_credential(link.access_token_enc)
    except Exception:
        return no("token_undecryptable", link.token_expires_at, link.broker_client_id)

    expires_at = link.token_expires_at
    if expires_at is None:
        return no("unknown_expiry", None, link.broker_client_id)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    horizon = expires_at
    if link.last_connected_at is not None:
        lc = link.last_connected_at
        if lc.tzinfo is None:
            lc = lc.replace(tzinfo=timezone.utc)
        horizon = min(horizon, lc + timedelta(hours=cfg.token_lifetime_hours))

    if horizon <= now:
        return no("token_expired", expires_at, link.broker_client_id)
    if link.status == CustomerLinkStatus.FAILED:
        return no("last_attempt_failed", expires_at, link.broker_client_id)
    if link.status != CustomerLinkStatus.CONNECTED:
        return no(f"status_{link.status.value.lower()}", expires_at, link.broker_client_id)

    return ConnectionStatus(True, "connected", expires_at, now, customer_id,
                            link.broker_client_id, link.last_connected_at)


__all__ = ["is_connected", "ConnectionStatus", "probe_broker_side"]
