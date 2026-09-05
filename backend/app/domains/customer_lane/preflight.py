"""Can the customer lane safely arm? Ask BEFORE anything is scheduled.

THE FAILURE THIS PREVENTS. The lane's trading-day calendar is
``orderflow_engine/holidays.yaml`` — deliberately the estate's one shared list,
never a copy (founder ruling, 13 Aug 2026). But ``orderflow_engine/`` is a
SIBLING of ``backend/``, and the backend image is built with
``context: ./backend``, so the file is structurally outside the build context
and is NOT in the deployed image. Verified inside the running container:
``find / -name holidays.yaml`` returns nothing, and neither container has any
host mount.

So on the box as it stands, ``is_trading_day`` raises ``CalendarUnavailable``.
That is the CORRECT behaviour — it refuses rather than guessing — but it means
the ladder would be armed and then fail every morning. Arming a subsystem that
cannot answer "is today a trading day?" is the thing being prevented here: the
refusal must happen at ARM time, loudly, by name, not at 07:45 in a worker log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
import os
from datetime import date, datetime, timedelta, timezone

from app.domains.customer_lane import calendar as cal
from app.domains.customer_lane import config as lane_config

logger = logging.getLogger("customer_lane.preflight")

IST = timezone(timedelta(hours=5, minutes=30))
SUBSYSTEM = "customer-lane"


def _missing_transport_credentials(transport: str) -> list[str]:
    """Which settings the primary transport needs and does not have.

    Names only — this NEVER reads or reports a credential value.
    """
    from app.core.config import get_settings

    settings = get_settings()

    def empty(attr: str) -> bool:
        return not str(getattr(settings, attr, "") or "").strip()

    if transport == "email":
        required = ("aws_access_key_id", "aws_secret_access_key",
                    "aws_ses_region", "from_email")
        return [a for a in required if empty(a)]
    if transport == "telegram":
        missing = [a for a in ("telegram_bot_token",) if empty(a)]
        if not getattr(settings, "telegram_enabled", False):
            missing.append("telegram_enabled (is False)")
        return missing
    return [f"unknown transport {transport!r}"]


class CustomerLaneNotReady(RuntimeError):
    """The lane refuses to arm. The message names the subsystem and the reason."""


@dataclass(frozen=True)
class PreflightResult:
    ready: bool
    reason: str
    detail: str

    def __bool__(self) -> bool:
        return self.ready


def check(today: date | None = None) -> PreflightResult:
    """Read-only. Safe to call from a health endpoint or an operator shell."""
    today = today or datetime.now(IST).date()
    try:
        holidays = cal.load_holidays()
    except cal.CalendarUnavailable as exc:
        return PreflightResult(
            False, "calendar_unavailable",
            f"{SUBSYSTEM}: the trading-day calendar could not be read — {exc}")

    try:
        end = cal.coverage_end()
    except Exception as exc:  # pragma: no cover - load succeeded, this cannot normally fail
        return PreflightResult(False, "coverage_unreadable", f"{SUBSYSTEM}: {exc}")

    if today > end:
        return PreflightResult(
            False, "calendar_expired",
            f"{SUBSYSTEM}: the calendar stops at {end} and today is {today}. "
            f"Load the NSE {today.year} circular into {cal.holidays_path()}.")

    # A rung whose transport does not exist must be acknowledged BEFORE arming, not
    # discovered at 08:57 when the CALL refuses. H1 established that no voice
    # transport exists anywhere in the estate.
    # A rung whose transport does not exist must be ACKNOWLEDGED before arming. The
    # acceptance is per-rung on purpose: CALL is a decided, documented absence
    # (run J), but a DIFFERENT rung losing its transport is something nobody decided
    # about, and that must still refuse. A blanket "accept anything missing" would
    # turn the next accident into a silent skip.
    from app.domains.customer_lane.channels import unavailable_steps
    accepted = lane_config.load().unwired_rungs
    missing = unavailable_steps()
    undecided = {step: chan for step, chan in missing.items()
                 if step.value.upper() not in accepted}
    if undecided:
        rungs = ", ".join(f"{s.value}->{c}" for s, c in sorted(
            undecided.items(), key=lambda kv: kv[0].value))
        return PreflightResult(
            False, "rung_transport_missing",
            f"{SUBSYSTEM}: these rungs have no transport and nobody decided about "
            f"them: {rungs}. Provide the transport, or add the rung to "
            f"CUSTOMER_LANE_UNWIRED_RUNGS as a deliberate decision. "
            f"(Already accepted as unwired: {', '.join(sorted(accepted)) or 'none'}.)")

    # CREDENTIALS ARE CHECKED AT ARM TIME, NOT AT SEND TIME. Discovering an empty
    # AWS key at 07:45 on a live morning is the failure this prevents. Only insisted
    # on when the lane may actually deliver (channels_live); a disarmed lane logs
    # STUBBED and needs no credentials.
    cfg = lane_config.load()
    if cfg.channels_live:
        missing_creds = _missing_transport_credentials(cfg.primary_message_transport)
        if missing_creds:
            return PreflightResult(
                False, "transport_credentials_missing",
                f"{SUBSYSTEM}: channels are live and the primary transport "
                f"({cfg.primary_message_transport}) is missing: "
                f"{', '.join(missing_creds)}. Supply them in the server environment "
                "at arming time — they are never stored in git.")

    return PreflightResult(
        True, "ready",
        f"{SUBSYSTEM}: calendar {cal.holidays_path()} — {len(holidays)} dates, "
        f"covers through {end}")


def assert_can_arm(today: date | None = None) -> PreflightResult:
    """Raise unless the lane may arm. Call this at every ARM point."""
    result = check(today)
    if not result.ready:
        logger.error("customer lane REFUSED TO ARM: %s", result.detail)
        raise CustomerLaneNotReady(result.detail)
    logger.info("customer lane preflight OK: %s", result.detail)
    return result


__all__ = ["check", "assert_can_arm", "PreflightResult", "CustomerLaneNotReady",
           "SUBSYSTEM"]
