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

logger = logging.getLogger("customer_lane.preflight")

IST = timezone(timedelta(hours=5, minutes=30))
SUBSYSTEM = "customer-lane"


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
    accept_unwired = os.environ.get(
        "CUSTOMER_LANE_ACCEPT_UNWIRED_RUNGS", "0").strip().lower() in {
            "1", "true", "yes", "on"}

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
    from app.domains.customer_lane.channels import unavailable_steps
    missing = unavailable_steps()
    if missing and not accept_unwired:
        rungs = ", ".join(f"{s.value}->{c}" for s, c in sorted(
            missing.items(), key=lambda kv: kv[0].value))
        return PreflightResult(
            False, "rung_transport_missing",
            f"{SUBSYSTEM}: these rungs have no transport: {rungs}. Either provide the "
            "transport or accept them as unwired by setting "
            "CUSTOMER_LANE_ACCEPT_UNWIRED_RUNGS=1 — the ladder will then skip them "
            "loudly instead of pretending they ran.")

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
