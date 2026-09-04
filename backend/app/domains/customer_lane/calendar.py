"""Exchange trading-day calendar for the customer lane.

REUSES THE ESTATE'S EXISTING LIST. It does not ship dates of its own and it does
not keep a copy. It reads ``orderflow_engine/holidays.yaml`` — the same
git-tracked NSE circular list the tick recorder, the depth recorder, the daily
pulse and the morning watchdog already run on. Two calendars that disagree would
be worse than none, so there is exactly one file.

CORRECTION OF RECORD: an earlier run of this build reported that "no exchange
holiday list exists in this repo" and hard-coded an empty holiday set on the
strength of it. That was wrong — the list was git-tracked in this same repo the
whole time. This module replaces that assumption.

FAILS LOUD, NEVER SILENT. The recorder's own loader (``recorder.scheduler.
load_holidays``) warns and returns an EMPTY set when the file is missing, which
is safe for a recorder (it connects and records nothing) and unsafe for us: an
empty set would read as "no holidays this year" and we would phone customers on
Diwali. Every failure here raises instead:

  * file missing / unreadable        -> CalendarUnavailable
  * file parses to zero dates        -> CalendarUnavailable
  * the asked-for date is beyond the list's coverage -> CalendarCoverageError

The list speaks only through 31 December of the newest year it mentions. Silence
past that point is not "no holidays"; it is "not loaded yet".

SCOPE: NSE **trading** holidays only. Clearing/settlement holidays and the Diwali
Muhurat session are deliberately out of scope — see the header of holidays.yaml.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

#: Candidate locations, in order. The first is this repo; the second is the
#: production box, where the same file lives under the deploy root.
_CANDIDATES = (
    Path(__file__).resolve().parents[4] / "orderflow_engine" / "holidays.yaml",
    Path("/home/ubuntu/trading-bridge/orderflow_engine/holidays.yaml"),
)

#: Test/ops override. Points at an alternative holidays.yaml. There is still only
#: ONE calendar at a time — this changes which file, never adds a second source.
ENV_OVERRIDE = "CUSTOMER_LANE_HOLIDAYS_FILE"


class CalendarUnavailable(RuntimeError):
    """The holiday list could not be read. Never degrade to 'no holidays'."""


class CalendarCoverageError(RuntimeError):
    """The list does not reach the date asked about. The next year is not loaded."""


def holidays_path() -> Path:
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return Path(override)
    for candidate in _CANDIDATES:
        if candidate.exists():
            return candidate
    return _CANDIDATES[0]


def _load(path: Path) -> frozenset[date]:
    import yaml

    if not path.exists():
        raise CalendarUnavailable(
            f"holiday list {path} not found — refusing to judge trading days. "
            "An empty set here would mean 'no holidays', which is a different "
            "claim and would message customers on an exchange holiday.")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception as exc:  # malformed YAML is unreadable, not 'no holidays'
        raise CalendarUnavailable(f"holiday list {path} is unreadable: {exc}") from exc

    out: set[date] = set()
    for item in data.get("holidays") or []:
        if isinstance(item, date):
            out.add(item)
        elif isinstance(item, str):
            out.add(date.fromisoformat(item.strip()))
    if not out:
        raise CalendarUnavailable(
            f"holiday list {path} parsed to ZERO dates — treating that as "
            "unreadable, not as 'a year with no holidays'.")
    return frozenset(out)


@lru_cache(maxsize=4)
def _cached(path_str: str, mtime: float) -> frozenset[date]:
    return _load(Path(path_str))


def load_holidays() -> frozenset[date]:
    """Read the list. Keyed on mtime, so editing the file is picked up without a
    restart — a long-lived worker must never serve a stale calendar."""
    path = holidays_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _load(path)  # raises CalendarUnavailable with the good message
    return _cached(str(path), mtime)


def coverage_end() -> date:
    """31 December of the newest year the list mentions."""
    return date(max(d.year for d in load_holidays()), 12, 31)


def is_trading_day(day: date) -> bool:
    """True iff ``day`` is an exchange trading day. Raises rather than guess."""
    if day.weekday() >= 5:
        return False
    end = coverage_end()
    if day > end:
        raise CalendarCoverageError(
            f"the holiday list covers through {end}, but {day} is beyond it. "
            f"Load the NSE {day.year} circular into {holidays_path()} before "
            "judging that date — refusing to assume it is a trading day.")
    return day not in load_holidays()


def coverage_alarm(today: date | None = None, *, alarm_from_month: int = 11) -> str | None:
    """Yearly-refresh alarm. From 1 November, if next year's list is absent, say so.

    Returns the alert text, or ``None`` when coverage is fine. Cheap and read-only
    so it can be called from a health check or a beat task.
    """
    today = today or datetime.now(IST).date()
    try:
        end = coverage_end()
    except CalendarUnavailable as exc:
        return f"CUSTOMER LANE CALENDAR: {exc}"
    if today > end:
        return (f"CUSTOMER LANE CALENDAR EXPIRED: the holiday list stops at {end} and "
                f"today is {today}. The ladder cannot judge trading days. Load the NSE "
                f"{today.year} circular into {holidays_path()} now.")
    if today.month >= alarm_from_month and end.year <= today.year:
        days = (end - today).days
        return (f"CUSTOMER LANE CALENDAR RUNNING OUT: coverage ends {end} ({days} days). "
                f"The NSE {today.year + 1} circular is not loaded. "
                f"See docs/HOLIDAY_CALENDAR_REFRESH.md")
    return None


__all__ = ["is_trading_day", "load_holidays", "coverage_end", "coverage_alarm",
           "holidays_path", "CalendarUnavailable", "CalendarCoverageError",
           "ENV_OVERRIDE"]
