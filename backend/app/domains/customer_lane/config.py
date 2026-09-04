"""Customer-lane settings — its OWN settings object, deliberately NOT added to the
shared ``app.core.config.Settings``, so this run cannot change behaviour for any
existing consumer of that object.

EVERY flag here defaults to OFF / safe. Reconnect cadence is CONFIGURABLE because the
partner-token lifetime has NOT BEEN MEASURED (see the run's NOT MEASURED list).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, time


def _b(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


def _t(name: str, default: str) -> time:
    hh, mm = os.environ.get(name, default).split(":")
    return time(int(hh), int(mm))


@dataclass(frozen=True)
class CustomerLaneConfig:
    # ---- master arming flags: ALL OFF ----
    ladder_enabled: bool = field(default_factory=lambda: _b("CUSTOMER_LANE_LADDER_ENABLED"))
    order_lane_enabled: bool = field(default_factory=lambda: _b("CUSTOMER_LANE_ORDER_ENABLED"))
    egress_verify_enabled: bool = field(default_factory=lambda: _b("CUSTOMER_LANE_EGRESS_VERIFY_ENABLED"))
    beat_enabled: bool = field(default_factory=lambda: _b("CUSTOMER_LANE_BEAT_ENABLED"))
    #: GLOBAL KILL. When true the whole customer lane refuses, regardless of any
    #: other flag. It is checked at every act, never cached.
    kill_all: bool = field(default_factory=lambda: _b("CUSTOMER_LANE_KILL_ALL"))
    #: When true, an unverifiable egress is a REFUSAL rather than a warning.
    require_verified_egress: bool = field(
        default_factory=lambda: _b("CUSTOMER_LANE_REQUIRE_VERIFIED_EGRESS", True))

    # ---- ladder times (IST), all configurable ----
    r1_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_R1", "07:45"))
    r2_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_R2", "08:30"))
    call_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_CALL", "08:55"))
    red_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_RED", "09:05"))
    link_cutoff_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_LINK_CUTOFF", "09:15"))

    # ---- token lifetime: NOT MEASURED, therefore configurable ----
    token_lifetime_hours: float = field(
        default_factory=lambda: float(os.environ.get("CUSTOMER_LANE_TOKEN_LIFETIME_HOURS", "24")))

    # ---- auth provider selection: stub unless explicitly switched ----
    auth_provider: str = field(default_factory=lambda: os.environ.get("CUSTOMER_LANE_AUTH_PROVIDER", "stub"))
    connect_link_ttl_minutes: int = field(
        default_factory=lambda: int(os.environ.get("CUSTOMER_LANE_LINK_TTL_MIN", "30")))
    connect_base_url: str = field(
        default_factory=lambda: os.environ.get("CUSTOMER_LANE_CONNECT_BASE_URL", "https://app.tradetri.local"))
    #: HARD GUARD for this run: no partner network call may leave the box.
    allow_partner_network: bool = field(
        default_factory=lambda: _b("CUSTOMER_LANE_ALLOW_PARTNER_NETWORK"))

    # ---- exchange holidays: NOT AVAILABLE in this repo (see report). Weekend-only
    # until a holiday source is supplied. Configurable, empty by default.
    holidays: frozenset[date] = field(default_factory=frozenset)


def load() -> CustomerLaneConfig:
    """Read config FRESH. Never cache — a long-lived process must reload, because a
    03:00 UTC token rotation previously killed a process that cached."""
    return CustomerLaneConfig()


__all__ = ["CustomerLaneConfig", "load"]
