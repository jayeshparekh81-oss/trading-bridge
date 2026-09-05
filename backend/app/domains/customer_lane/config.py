"""Customer-lane settings — its OWN settings object, deliberately NOT added to the
shared ``app.core.config.Settings``, so this run cannot change behaviour for any
existing consumer of that object.

EVERY flag here defaults to OFF / safe. Reconnect cadence is CONFIGURABLE because the
partner-token lifetime has NOT BEEN MEASURED (see the run's NOT MEASURED list).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time


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
    #: THE SEND-FOR-REAL GATE. While false, every channel logs and returns STUBBED
    #: without touching NotificationService, so nothing can reach a person. This is
    #: deliberately separate from ladder_enabled: the ladder can be exercised end to
    #: end with the delivery half still inert.
    channels_live: bool = field(default_factory=lambda: _b("CUSTOMER_LANE_CHANNELS_LIVE"))

    #: The transport the lane leads with. Founder decision (run J): EMAIL FIRST —
    #: all 12 users already have an address, so it needs credentials only, whereas
    #: Telegram additionally requires every customer to start a bot chat.
    #: This is not a switch that bypasses NotificationService: that service already
    #: defaults email ON (``prefs.get("email", True)``) and Telegram OPT-IN (needs
    #: both a preference and a per-user chat id), so email-first is its natural
    #: behaviour. The value here records the decision and tells preflight WHICH
    #: credentials to insist on before arming.
    primary_message_transport: str = field(
        default_factory=lambda: os.environ.get(
            "CUSTOMER_LANE_PRIMARY_TRANSPORT", "email").strip().lower())

    #: Rungs whose missing transport has been DECIDED about and accepted.
    #: Defaults to CALL: the founder decided (run J) that no voice transport will be
    #: built now — a vendor plus Indian DLT registration is its own project, and it is
    #: not worth blocking on while there is no partner credential, no egress IP and no
    #: customer. This is the DOCUMENTED DEFAULT STATE, not an accident of missing
    #: config. Any OTHER rung that loses its transport is NOT covered by this and must
    #: still refuse to arm, because nobody decided about it.
    unwired_rungs: frozenset[str] = field(
        default_factory=lambda: frozenset(
            r.strip().upper()
            for r in os.environ.get("CUSTOMER_LANE_UNWIRED_RUNGS", "CALL").split(",")
            if r.strip()))
    #: GLOBAL KILL. When true the whole customer lane refuses, regardless of any
    #: other flag. It is checked at every act, never cached.
    kill_all: bool = field(default_factory=lambda: _b("CUSTOMER_LANE_KILL_ALL"))
    #: When true, an unverifiable egress is a REFUSAL rather than a warning.
    require_verified_egress: bool = field(
        default_factory=lambda: _b("CUSTOMER_LANE_REQUIRE_VERIFIED_EGRESS", True))

    # ---- ladder times (IST), all configurable ----
    # Times chosen to MISS the pre-market job grid, not for their own sake
    # (founder decision, run G). The estate already runs, in IST:
    #   08:30 auto_login + pnl-reconciler-intraday, 08:55 calendar_health,
    #   09:05 scrip-master-warm-premarket + preopen_forever.
    # The 09:05 slot is the one that matters: the scrip-master warm exists so the
    # day's first F&O signal never pays a ~9s CSV download inside the order path.
    # Nothing may share its minute. Each rung is therefore offset by +2 minutes.
    r1_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_R1", "07:45"))
    r2_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_R2", "08:32"))
    call_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_CALL", "08:57"))
    red_at: time = field(default_factory=lambda: _t("CUSTOMER_LANE_RED", "09:07"))
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

    # ---- exchange holidays: the estate's ONE list, orderflow_engine/holidays.yaml,
    # read by app.domains.customer_lane.calendar. There is deliberately NO holiday
    # field here: a settable set would be a second calendar, and an empty default
    # would silently mean "no holidays". Point CUSTOMER_LANE_HOLIDAYS_FILE at a
    # different file to override which file is read - never at a second source.


def load() -> CustomerLaneConfig:
    """Read config FRESH. Never cache — a long-lived process must reload, because a
    03:00 UTC token rotation previously killed a process that cached."""
    return CustomerLaneConfig()


__all__ = ["CustomerLaneConfig", "load"]
