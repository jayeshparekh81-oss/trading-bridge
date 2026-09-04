"""Auth providers for one-tap connect.

WE NEVER HOLD CUSTOMER CREDENTIALS. Nothing in this module accepts, stores, logs or
transmits a customer's password, PIN or TOTP seed. The customer authenticates on the
BROKER's own page. We only ever see the consent handoff the broker gives back.

TRADETRI HAS NO DHAN PARTNER CREDENTIALS. ``DhanPartnerAuthProvider`` therefore
FAILS CLOSED: it raises rather than guessing an endpoint or degrading to a silent
no-op. It additionally refuses while ``allow_partner_network`` is false, which is the
default, so no partner call can leave the box in this run even if credentials appear.
"""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping, Protocol

from app.domains.customer_lane import config as lane_config

logger = logging.getLogger("customer_lane.auth")

#: The documented Dhan partner flow, recorded so it is not re-invented from memory
#: later. NOTHING HERE IS CALLED IN THIS RUN.
DHAN_PARTNER_FLOW = (
    "1. partner generate-consent  -> consentId",
    "2. customer logs in on Dhan's own page with consentId",
    "3. partner consume-consent   -> accessToken",
)


class PartnerCredentialsMissing(RuntimeError):
    """Raised when a partner provider is asked to act without real credentials."""


class PartnerNetworkDisabled(RuntimeError):
    """Raised when a partner call is attempted while egress is disarmed."""


@dataclass(frozen=True)
class BrokerToken:
    access_token: str
    expires_at: datetime

    def __repr__(self) -> str:  # never let a token reach a log via repr
        return f"BrokerToken(access_token=<redacted>, expires_at={self.expires_at!r})"


class AuthProvider(Protocol):
    name: str

    def consent_url(self, customer_id: uuid.UUID, raw_token: str) -> str: ...

    async def exchange(self, customer_id: uuid.UUID,
                       payload: Mapping[str, str]) -> BrokerToken: ...


class StubAuthProvider:
    """Default provider. Makes NO network call of any kind."""

    name = "stub"

    def consent_url(self, customer_id: uuid.UUID, raw_token: str) -> str:
        base = lane_config.load().connect_base_url.rstrip("/")
        return f"{base}/connect/{raw_token}"

    async def exchange(self, customer_id: uuid.UUID,
                       payload: Mapping[str, str]) -> BrokerToken:
        cfg = lane_config.load()
        return BrokerToken(
            access_token="STUB-" + secrets.token_urlsafe(24),
            expires_at=datetime.now(timezone.utc)
                       + timedelta(hours=cfg.token_lifetime_hours))


class DhanPartnerAuthProvider:
    """Real shape, deliberately inert. See module docstring."""

    name = "dhan_partner"

    def __init__(self) -> None:
        self._partner_id = os.environ.get("DHAN_PARTNER_ID") or None
        self._partner_secret = os.environ.get("DHAN_PARTNER_SECRET") or None

    @property
    def credentials_available(self) -> bool:
        return bool(self._partner_id and self._partner_secret)

    def _guard(self) -> None:
        if not self.credentials_available:
            raise PartnerCredentialsMissing(
                "TRADETRI has no Dhan partner credentials. Refusing to guess an "
                "endpoint. Steps: " + " | ".join(DHAN_PARTNER_FLOW))
        if not lane_config.load().allow_partner_network:
            raise PartnerNetworkDisabled(
                "CUSTOMER_LANE_ALLOW_PARTNER_NETWORK is false; no partner call "
                "may leave the box.")

    def consent_url(self, customer_id: uuid.UUID, raw_token: str) -> str:
        self._guard()
        raise NotImplementedError(
            "Partner consent handoff is unbuilt pending real credentials.")

    async def exchange(self, customer_id: uuid.UUID,
                       payload: Mapping[str, str]) -> BrokerToken:
        self._guard()
        raise NotImplementedError(
            "consume-consent is unbuilt pending real credentials.")


PROVIDERS: dict[str, type] = {
    "stub": StubAuthProvider,
    "dhan_partner": DhanPartnerAuthProvider,
}


def get_provider(name: str | None = None) -> AuthProvider:
    """Resolve the provider FRESH from config. Unknown name fails closed."""
    key = name or lane_config.load().auth_provider
    try:
        return PROVIDERS[key]()
    except KeyError:
        raise PartnerCredentialsMissing(f"unknown auth provider {key!r}") from None


__all__ = ["AuthProvider", "StubAuthProvider", "DhanPartnerAuthProvider",
           "BrokerToken", "get_provider", "PROVIDERS", "DHAN_PARTNER_FLOW",
           "PartnerCredentialsMissing", "PartnerNetworkDisabled"]
