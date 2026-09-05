"""May this customer's mapped static IP be changed right now?

ONE function answers it: :func:`may_change_ip`. It refuses at the POINT OF CHANGE,
not with a warning afterwards, and when it refuses it says WHEN the change becomes
possible — so the customer can be told something useful instead of "no".

TWO CLOCKS, DELIBERATELY NOT COLLAPSED
--------------------------------------
1. **Dhan's 7-day whitelist lock.** After an IP is whitelisted it cannot be changed
   for 7 days. Driven by ``ip_whitelisted_at`` (or an explicit ``ip_lock_until``).
2. **The exchange's once-per-CALENDAR-WEEK rule.** A client may change their mapped
   static IP at most once per calendar week. Driven by ``last_ip_change_at``.

These are different. "Once per calendar week" is NOT "once per 7 days": a change on
Sunday and a change on Monday are one day apart and fall in two different weeks.
Deriving both from one timestamp would make the week rule silently inert, because
7 days after any day always lands in a later week.

TIMEZONE
--------
The calendar week is computed in **IST**, and that choice is load-bearing. The box
runs UTC; a change at 23:00 UTC Sunday is 04:30 IST Monday — a different calendar
week for the exchange. Using UTC here would silently give the wrong answer for
roughly five and a half hours of every week. Weeks start **Monday** (ISO).

FAILS CLOSED
------------
If we cannot prove the locks have expired, we refuse. A customer wrongly allowed to
change their IP is locked out of their own broker account for a week — an
operational mistake that lands on the founder, not on us.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

#: Dhan holds a whitelisted IP for this long.
BROKER_LOCK_DAYS = 7


@dataclass(frozen=True)
class IpChangeDecision:
    permitted: bool
    reason: str
    #: When the change becomes possible. None when permitted, or when unknowable.
    allowed_from: datetime | None
    detail: str

    def __bool__(self) -> bool:
        return self.permitted


def _ist(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST)


def week_start(moment: datetime) -> datetime:
    """Monday 00:00 IST of the calendar week containing ``moment``."""
    local = _ist(moment)
    assert local is not None
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=local.weekday())


def same_calendar_week(a: datetime, b: datetime) -> bool:
    return week_start(a) == week_start(b)


def may_change_ip(
    *,
    current_ip: str | None,
    ip_whitelisted_at: datetime | None,
    last_ip_change_at: datetime | None,
    ip_lock_until: datetime | None = None,
    now: datetime | None = None,
) -> IpChangeDecision:
    """The single decision. See the module docstring for the two clocks."""
    now_ist = _ist(now or datetime.now(timezone.utc))
    assert now_ist is not None

    # No IP assigned yet: this is the FIRST assignment, not a change. Nothing to lock.
    if not current_ip:
        return IpChangeDecision(
            True, "initial_assignment", None,
            "no static IP is assigned yet, so this is an assignment, not a change")

    # FAIL CLOSED. An assigned IP whose history we cannot see might be one day old.
    if ip_whitelisted_at is None and ip_lock_until is None:
        return IpChangeDecision(
            False, "lock_state_unknown", None,
            f"IP {current_ip} is assigned but has no ip_whitelisted_at and no "
            "ip_lock_until, so the 7-day broker lock cannot be shown to have "
            "expired. Refusing: a wrong answer locks the customer out of their own "
            "broker account for a week.")

    # CLOCK 1 — Dhan's 7-day whitelist lock.
    explicit = _ist(ip_lock_until)
    derived = None
    whitelisted = _ist(ip_whitelisted_at)
    if whitelisted is not None:
        derived = whitelisted + timedelta(days=BROKER_LOCK_DAYS)
    lock_end = max([d for d in (explicit, derived) if d is not None])
    if now_ist < lock_end:
        return IpChangeDecision(
            False, "broker_lock_active", lock_end,
            f"Dhan holds this IP until {lock_end:%Y-%m-%d %H:%M} IST "
            f"({BROKER_LOCK_DAYS} days from whitelisting). It can be changed on or "
            f"after that time.")

    # CLOCK 2 — the exchange's once-per-calendar-week rule.
    if last_ip_change_at is None:
        return IpChangeDecision(
            False, "change_history_unknown", None,
            f"IP {current_ip} is assigned but last_ip_change_at is not recorded, so "
            "we cannot show that no change has already been made this calendar week. "
            "Refusing rather than risking a second change in one week.")

    changed = _ist(last_ip_change_at)
    assert changed is not None
    if same_calendar_week(changed, now_ist):
        next_week = week_start(now_ist) + timedelta(days=7)
        return IpChangeDecision(
            False, "already_changed_this_week", next_week,
            f"the IP was already changed on {changed:%Y-%m-%d} IST, which is this "
            f"calendar week. The exchange allows one change per week, so the next "
            f"change is possible from {next_week:%Y-%m-%d} (Monday) IST.")

    return IpChangeDecision(
        True, "permitted", None,
        f"the broker lock expired at {lock_end:%Y-%m-%d %H:%M} IST and the last "
        f"change ({changed:%Y-%m-%d}) was in an earlier calendar week")


class IpChangeRefused(RuntimeError):
    """Raised AT THE POINT OF CHANGE. Carries the decision, including when it becomes
    possible, so the caller can tell the customer something useful."""

    def __init__(self, decision: IpChangeDecision) -> None:
        super().__init__(decision.detail)
        self.decision = decision


async def change_static_ip(session, customer_id, new_ip: str, *,
                           now: datetime | None = None):
    """THE POINT OF CHANGE. Enforces :func:`may_change_ip` before mutating anything.

    There is deliberately no other write path to ``assigned_static_ip`` in the lane:
    a decision function nothing calls would only ever warn after the fact.
    """
    from sqlalchemy import select

    from app.db.models.customer_lane import CustomerBrokerLink

    moment = now or datetime.now(timezone.utc)
    link = (await session.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == customer_id))).scalar_one_or_none()
    if link is None:
        raise IpChangeRefused(IpChangeDecision(
            False, "no_broker_link", None,
            f"no broker link for customer {customer_id}"))

    decision = may_change_ip(
        current_ip=link.assigned_static_ip,
        ip_whitelisted_at=link.ip_whitelisted_at,
        last_ip_change_at=link.last_ip_change_at,
        ip_lock_until=link.ip_lock_until,
        now=moment,
    )
    if not decision.permitted:
        raise IpChangeRefused(decision)

    link.assigned_static_ip = new_ip
    link.last_ip_change_at = moment
    link.ip_whitelisted_at = None   # the NEW ip is not whitelisted until Dhan says so
    link.ip_lock_until = None
    await session.flush()
    return decision


__all__ = ["may_change_ip", "change_static_ip", "IpChangeDecision", "IpChangeRefused",
           "week_start", "same_calendar_week", "BROKER_LOCK_DAYS", "IST"]
