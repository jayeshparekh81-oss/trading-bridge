"""Trading-day counter — foundation util for the (later) options near-expiry roll.

Standalone + pure: no I/O, no DB, no imports beyond the stdlib. **NOT wired into
any flow yet.** The options-expiry rewrite (see
``docs/MULTI_INSTRUMENT_ISOLATION_AUDIT.md`` → "OPTIONS EXPIRY — CORRECTED
DESIGN") will consume :func:`trading_days_between` to decide the N-trading-day
near-expiry roll — e.g. "if <= 2-3 trading days to expiry, roll to the next
contract".

A "trading day" here = a weekday (Mon-Fri) that is NOT in the optional
``holidays`` set. ``holidays`` is a refinement, not a requirement for v1: real
exchange expiries (``SEM_EXPIRY_DATE``) already encode holiday shifts, so
weekend-only skipping is a safe default.
"""

from __future__ import annotations

from datetime import date, timedelta

#: ``date.weekday()``: Mon=0 … Fri=4, Sat=5, Sun=6. Sat/Sun are non-trading.
_WEEKEND: frozenset[int] = frozenset({5, 6})


def is_trading_day(day: date, holidays: set[date] | None = None) -> bool:
    """True iff ``day`` is a weekday (Mon-Fri) and not in ``holidays``.

    Pure helper. ``holidays`` defaults to None (weekend-only check).
    """
    if day.weekday() in _WEEKEND:
        return False
    return not (holidays and day in holidays)


def trading_days_between(
    start: date, end: date, holidays: set[date] | None = None
) -> int:
    """Count trading days in the half-open interval ``(start, end]``.

    Convention — **``start`` EXCLUSIVE, ``end`` INCLUSIVE.** This answers
    "how many trading days remain until ``end``" when ``start`` is today:
    today itself is not "remaining", and the expiry day (``end``) itself
    counts. It is the value the options near-expiry roll thresholds on —
    e.g. roll when ``trading_days_between(today, expiry) <= 2``.

    A trading day = a weekday (Mon-Fri) not in ``holidays``. ``holidays``
    defaults to None (weekend-only skip) — a refinement, since real exchange
    expiries already encode holiday shifts.

    Edge cases (documented choices):
      * ``start == end`` → ``0`` — the interval ``(d, d]`` is empty
        (true even if that day is itself a holiday/weekend).
      * ``start > end``  → ``0`` — already past; never negative, since a
        "days remaining" threshold has no use for a negative count.
      * Weekends and holidays inside the interval are skipped.

    Pure + deterministic; no I/O. Standalone — not yet wired into any flow.

    Args:
        start: Reference / "today" date (exclusive).
        end: Target / expiry date (inclusive).
        holidays: Optional set of non-trading dates to also skip.

    Returns:
        Count of trading days in ``(start, end]`` (always ``>= 0``).
    """
    if start >= end:
        return 0
    count = 0
    day = start + timedelta(days=1)  # start EXCLUSIVE
    while day <= end:                # end INCLUSIVE
        if is_trading_day(day, holidays):
            count += 1
        day += timedelta(days=1)
    return count


__all__ = ["trading_days_between", "is_trading_day"]
