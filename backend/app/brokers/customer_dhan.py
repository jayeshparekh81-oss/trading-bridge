"""Per-customer Dhan order lane. A NEW file: ``app/brokers/dhan.py`` is untouched and
is not imported here, so this module has zero blast radius on the live BSE path.

THE INVARIANT THIS FILE EXISTS TO ENFORCE
    A customer's order must be impossible to send through another customer's IP or
    token. Every lane is built for exactly ONE customer_id, carries that customer's
    own credentials and egress, and refuses to act on any other.

THIS LANE IS DISARMED. ``order_lane_enabled`` defaults FALSE and ``place_order``
refuses while it is off. Even when armed, this run's lane is DRY-RUN ONLY: it builds
the request and returns it. It sends nothing. ``_transmit`` is the single, named seam
where a real send would later live, and it raises today.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_credential
from app.db.models.customer_lane import CustomerBrokerLink
from app.domains.customer_lane import config as lane_config
from app.domains.customer_lane.connection import is_connected
from app.domains.customer_lane.egress import enforce as enforce_egress
from app.domains.customer_lane.egress import verify_egress
from app.domains.customer_lane.kill_switch import assert_lane_permitted
from app.domains.customer_lane.participation import (Intent, may_enter, may_exit)

logger = logging.getLogger("customer_lane.order")

#: F&O is NRML only. MIS/INTRADAY is forbidden for derivatives, estate-wide.
FORBIDDEN_FNO_PRODUCTS = {"MIS", "INTRADAY"}


class OrderLaneRefused(RuntimeError):
    """Base refusal. Every refusal in this module is LOUD and returns nothing."""


class LaneDisarmed(OrderLaneRefused): ...
class CustomerNotConnected(OrderLaneRefused): ...
class EgressNotConfigured(OrderLaneRefused): ...
class EgressNotExclusive(OrderLaneRefused): ...
class CustomerMismatch(OrderLaneRefused): ...
class ProductNotAllowed(OrderLaneRefused): ...
class JoinRuleRefused(OrderLaneRefused): ...


@dataclass(frozen=True)
class LaneEgress:
    """One customer's outbound identity. Never shared, never defaulted."""
    proxy_url: str
    proxy_username: str | None
    proxy_password: str | None = field(repr=False, default=None)
    static_ip: str | None = None

    def __repr__(self) -> str:
        return (f"LaneEgress(proxy_url={self.proxy_url!r}, "
                f"proxy_username={self.proxy_username!r}, "
                f"proxy_password=<redacted>, static_ip={self.static_ip!r})")


@dataclass(frozen=True)
class PreparedOrder:
    customer_id: uuid.UUID
    payload: dict[str, Any]
    egress: LaneEgress
    dry_run: bool
    prepared_at: datetime

    def __repr__(self) -> str:
        return (f"PreparedOrder(customer_id={self.customer_id!r}, "
                f"payload=<{len(self.payload)} fields>, egress={self.egress!r}, "
                f"dry_run={self.dry_run!r})")


class CustomerOrderLane:
    """Built ONLY by :func:`build_lane`. The constructor takes no defaults; there is
    no way to obtain a lane without naming a customer."""

    def __init__(self, customer_id: uuid.UUID, access_token: str,
                 egress: LaneEgress, broker_client_id: str | None,
                 connected_at: datetime | None = None) -> None:
        if customer_id is None:
            raise CustomerMismatch("a lane cannot exist without a customer_id")
        self._customer_id = customer_id
        self.__access_token = access_token          # name-mangled; never a public attr
        self._egress = egress
        self._broker_client_id = broker_client_id
        self._connected_at = connected_at

    @property
    def customer_id(self) -> uuid.UUID:
        return self._customer_id

    @property
    def egress(self) -> LaneEgress:
        return self._egress

    def __repr__(self) -> str:
        return f"CustomerOrderLane(customer_id={self._customer_id!r}, token=<redacted>)"

    def _auth_headers(self) -> dict[str, str]:
        return {"access-token": self.__access_token,
                "client-id": self._broker_client_id or ""}

    async def _transmit(self, prepared: PreparedOrder) -> None:  # pragma: no cover
        """THE ONLY SEAM WHERE A REAL ORDER COULD EVER LEAVE. Unimplemented by design."""
        raise NotImplementedError(
            "real order transmission is not built in this run; the lane is dry-run only")

    async def place_order(self, customer_id: uuid.UUID, payload: Mapping[str, Any], *,
                          intent: Intent = Intent.ENTRY,
                          signal_emitted_at: datetime | None = None,
                          closes_order_id: str | None = None,
                          dry_run: bool = True) -> PreparedOrder:
        """``customer_id`` is passed again ON PURPOSE. The caller must say who this
        order is for, and it must match the lane, or the lane refuses. A mixed-up
        caller cannot silently borrow this customer's token or IP."""
        if customer_id != self._customer_id:
            raise CustomerMismatch(
                f"order addressed to {customer_id} cannot be sent on the lane of "
                f"{self._customer_id}")

        # The global kill stops even PREPARATION. Checked fresh, every order.
        assert_lane_permitted(self._customer_id)

        cfg = lane_config.load()
        if not cfg.order_lane_enabled:
            raise LaneDisarmed("CUSTOMER_LANE_ORDER_ENABLED is false; refusing to act")

        product = str(payload.get("productType") or payload.get("product") or "").upper()
        instrument = str(payload.get("instrument") or payload.get("segment") or "").upper()
        if any(k in instrument for k in ("FUT", "OPT", "DERIV", "FNO")) \
                and product in FORBIDDEN_FNO_PRODUCTS:
            raise ProductNotAllowed(f"F&O is NRML only; refusing product {product!r}")

        # ---- THE MID-DAY JOIN RULE (participation.RULE_ID), enforced HERE so it
        # cannot be bypassed by a caller that forgets to ask. See
        # app.domains.customer_lane.participation.
        if intent is Intent.ENTRY:
            if signal_emitted_at is None:
                raise JoinRuleRefused(
                    "an ENTRY needs signal_emitted_at: the join rule cannot be "
                    "evaluated without knowing when the signal was emitted")
            decision = may_enter(connected_at=self._connected_at,
                                 signal_emitted_at=signal_emitted_at)
            if not decision.participates:
                raise JoinRuleRefused(
                    f"{decision.rule}: customer {self._customer_id} does not take this "
                    f"entry ({decision.reason})")
        else:
            decision = may_exit(customer_entry_order_id=closes_order_id)
            if not decision.participates:
                raise JoinRuleRefused(
                    f"{decision.rule}: customer {self._customer_id} has no entry to "
                    f"close ({decision.reason})")

        prepared = PreparedOrder(self._customer_id, dict(payload), self._egress,
                                 dry_run, datetime.now(timezone.utc))
        if not dry_run:
            # Egress is proved at the transmit boundary, not before it: a dry run
            # never leaves the box, so there is no identity to prove. A real send
            # must prove whose IP it is going out on, or not go.
            enforce_egress(await verify_egress(self._customer_id,
                                               self._egress.static_ip,
                                               self._egress.proxy_url))
            await self._transmit(prepared)
        logger.info("order prepared customer=%s dry_run=%s", self._customer_id, dry_run)
        return prepared


async def build_lane(session: AsyncSession, customer_id: uuid.UUID, *,
                     at: datetime | None = None) -> CustomerOrderLane:
    """The ONLY factory. ``customer_id`` is positional with NO DEFAULT, so a lane can
    never be built 'for whoever'. Fails closed on every missing precondition."""
    if customer_id is None:
        raise CustomerMismatch("build_lane requires an explicit customer_id")

    assert_lane_permitted(customer_id)

    status = await is_connected(session, customer_id, at=at)
    if not status.connected:
        raise CustomerNotConnected(
            f"customer {customer_id} is not connected ({status.reason})")

    link = (await session.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == customer_id))).scalar_one_or_none()
    if link is None:
        raise CustomerNotConnected(f"no broker link for {customer_id}")

    # EGRESS MUST BE EXCLUSIVE. Distinct tokens are not enough: if two customers
    # share an outbound identity, A's order DOES leave through the same IP as B's,
    # which is precisely what the isolation invariant forbids. Found by the FF
    # failure-injection sweep, which built two lanes on one IP without complaint.
    shared = (await session.execute(
        select(CustomerBrokerLink.customer_id).where(
            CustomerBrokerLink.customer_id != customer_id,
            or_(
                and_(CustomerBrokerLink.assigned_static_ip.is_not(None),
                     CustomerBrokerLink.assigned_static_ip == link.assigned_static_ip),
                and_(CustomerBrokerLink.proxy_url.is_not(None),
                     CustomerBrokerLink.proxy_url == link.proxy_url),
            ),
        ).limit(1))).scalars().first()
    if shared is not None:
        raise EgressNotExclusive(
            f"customer {customer_id} shares an outbound identity "
            f"(ip={link.assigned_static_ip!r}, proxy={link.proxy_url!r}) with customer "
            f"{shared} — refusing: their order would leave through another customer's "
            "IP, which is the one thing this lane exists to prevent")

    if not link.proxy_url:
        raise EgressNotConfigured(
            f"customer {customer_id} has no dedicated egress; refusing to fall back "
            f"to the shared IP, which would send their order from another identity")

    token = decrypt_credential(link.access_token_enc)
    egress = LaneEgress(
        proxy_url=link.proxy_url, proxy_username=link.proxy_username,
        proxy_password=(decrypt_credential(link.proxy_password_enc)
                        if link.proxy_password_enc else None),
        static_ip=link.assigned_static_ip)
    return CustomerOrderLane(customer_id, token, egress, link.broker_client_id,
                             connected_at=status.connected_at)


__all__ = ["build_lane", "CustomerOrderLane", "LaneEgress", "PreparedOrder",
           "OrderLaneRefused", "LaneDisarmed", "CustomerNotConnected",
           "EgressNotConfigured", "EgressNotExclusive", "CustomerMismatch",
           "ProductNotAllowed",
           "JoinRuleRefused"]
