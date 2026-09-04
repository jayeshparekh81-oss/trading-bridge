"""One-tap connect: issue a single-use, same-day link and consume it exactly once.

THE RAW TOKEN IS NEVER PERSISTED AND NEVER LOGGED. Only its SHA-256 hash reaches the
database. ``issue_link`` returns the raw token exactly once, to its caller, in memory.

Single-use is enforced by a CONDITIONAL UPDATE, not by read-then-write, so two
concurrent taps on the same link cannot both win.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_credential
from app.db.models.customer_lane import (ConnectLinkStatus, CustomerBrokerLink,
                                         CustomerConnectLink, CustomerLinkStatus)
from app.domains.customer_lane import config as lane_config
from app.domains.customer_lane.auth import BrokerToken, get_provider

logger = logging.getLogger("customer_lane.connect")

IST = timezone(timedelta(hours=5, minutes=30))


def hash_token(raw: str) -> str:
    """The ONLY representation of a connect token that may be stored."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedLink:
    customer_id: uuid.UUID
    raw_token: str
    url: str
    expires_at: datetime

    def __repr__(self) -> str:  # keep the token out of tracebacks and logs
        return (f"IssuedLink(customer_id={self.customer_id!r}, raw_token=<redacted>, "
                f"url=<redacted>, expires_at={self.expires_at!r})")


@dataclass(frozen=True)
class ConsumeResult:
    ok: bool
    customer_id: uuid.UUID | None
    reason: str


def _end_of_trading_day(trading_date: date) -> datetime:
    """The same-day wall. A link dies at the END of its own trading date.

    It is deliberately NOT clamped to the 09:15 market-open cutoff: that cutoff
    governs when the LADDER stops nagging and whether a customer joins from the open
    (see status.MID_DAY_JOIN_RULE), not whether they may connect at all. Clamping
    here would make a link issued after 09:15 dead on arrival and would silently
    contradict the mid-day join rule, which exists precisely to let a late customer
    connect and start at the next signal. The TTL is the real limiter."""
    return datetime.combine(trading_date, time(23, 59, 59),
                            tzinfo=IST).astimezone(timezone.utc)


async def issue_link(session: AsyncSession, customer_id: uuid.UUID, *,
                     trading_date: date, now: datetime | None = None) -> IssuedLink:
    cfg = lane_config.load()
    now = now or datetime.now(timezone.utc)
    ttl_expiry = now + timedelta(minutes=cfg.connect_link_ttl_minutes)
    expires_at = min(ttl_expiry, _end_of_trading_day(trading_date))

    raw = secrets.token_urlsafe(32)
    session.add(CustomerConnectLink(
        customer_id=customer_id, token_hash=hash_token(raw),
        expires_at=expires_at, trading_date=trading_date,
        status=ConnectLinkStatus.ISSUED))
    await session.flush()
    logger.info("connect link issued customer=%s trading_date=%s expires=%s",
                customer_id, trading_date, expires_at)
    return IssuedLink(customer_id, raw,
                      get_provider().consent_url(customer_id, raw), expires_at)


async def consume_link(session: AsyncSession, raw_token: str, *,
                       trading_date: date,
                       now: datetime | None = None) -> ConsumeResult:
    """Consume EXACTLY once. The conditional UPDATE is the race guard."""
    now = now or datetime.now(timezone.utc)
    h = hash_token(raw_token)

    row = (await session.execute(
        update(CustomerConnectLink)
        .where(CustomerConnectLink.token_hash == h,
               CustomerConnectLink.status == ConnectLinkStatus.ISSUED,
               CustomerConnectLink.expires_at > now,
               CustomerConnectLink.trading_date == trading_date)
        .values(status=ConnectLinkStatus.CONSUMED, consumed_at=now)
        .returning(CustomerConnectLink.customer_id))).first()
    if row is not None:
        return ConsumeResult(True, row[0], "consumed")

    # Refused. Say WHY, without ever echoing the token.
    link = (await session.execute(select(CustomerConnectLink).where(
        CustomerConnectLink.token_hash == h))).scalar_one_or_none()
    if link is None:
        reason = "unknown_token"
    elif link.status is ConnectLinkStatus.CONSUMED:
        reason = "already_consumed"
    elif link.trading_date != trading_date:
        reason = "wrong_trading_date"
    elif link.expires_at <= now:
        reason = "expired"
    else:
        reason = "refused"
    logger.warning("connect link refused reason=%s", reason)
    return ConsumeResult(False, None, reason)


async def complete_connection(session: AsyncSession, customer_id: uuid.UUID,
                              token: BrokerToken, *,
                              now: datetime | None = None) -> CustomerBrokerLink:
    """Store the broker token ENCRYPTED and mark the customer CONNECTED."""
    now = now or datetime.now(timezone.utc)
    link = (await session.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == customer_id))).scalar_one_or_none()
    if link is None:
        link = CustomerBrokerLink(customer_id=customer_id)
        session.add(link)
    link.access_token_enc = encrypt_credential(token.access_token)
    link.token_expires_at = token.expires_at
    link.last_connected_at = now
    link.status = CustomerLinkStatus.CONNECTED
    await session.flush()
    logger.info("customer connected customer=%s expires=%s",
                customer_id, token.expires_at)
    return link


__all__ = ["issue_link", "consume_link", "complete_connection", "hash_token",
           "IssuedLink", "ConsumeResult"]
