"""Is-expiry-week flag — 1 if bar falls in monthly F&O expiry week.

Indian F&O monthly expiry is the LAST Thursday of each calendar
month. "Expiry week" = the calendar week (Mon-Sun) that contains
that Thursday. This indicator returns 1 for any bar within that
week, 0 otherwise.

Honest scope note: weekly-options expiries (Bank Nifty, Nifty)
have changed multiple times in recent years (Wed/Thu rotations).
This indicator captures *monthly* expiry only — the more stable
and widely-used signal for typical retail strategies. A
weekly-expiry flag would need exchange-symbol context to know
which weekday applies, which we don't have at the calc layer.

Output length equals input length. No frequency restriction —
works on intraday + daily + weekly bars (the week containing
the bar is always derivable from its date).

Edge cases:
    * Empty input -> ``[]``.
    * Bar in a month where the last Thursday is a holiday: still
      flagged. Strategy logic is responsible for handling
      "expiry shifted to Wednesday" rare cases.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Sequence
from datetime import date, datetime, timedelta


def is_expiry_week(
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """1.0 if bar's calendar week contains the month's last Thursday."""
    n = len(timestamps)
    if n == 0:
        return []
    out: list[float | None] = []
    # Cache the last-Thursday date per (year, month) for the
    # input set so we don't recompute on every bar.
    last_thursday_cache: dict[tuple[int, int], date] = {}
    for ts in timestamps:
        ym = (ts.year, ts.month)
        if ym not in last_thursday_cache:
            last_thursday_cache[ym] = _last_thursday_of_month(ts.year, ts.month)
        last_thu = last_thursday_cache[ym]
        # Same ISO week (Mon-Sun) as the bar's date.
        bar_iso = ts.isocalendar()
        thu_iso = last_thu.isocalendar()
        if bar_iso.year == thu_iso.year and bar_iso.week == thu_iso.week:
            out.append(1.0)
        else:
            out.append(0.0)
    return out


def _last_thursday_of_month(year: int, month: int) -> date:
    """Date of the last Thursday in the (year, month)."""
    _, last_day = monthrange(year, month)
    last = date(year, month, last_day)
    # weekday(): Monday = 0, Thursday = 3.
    while last.weekday() != 3:
        last -= timedelta(days=1)
    return last


__all__ = ["is_expiry_week"]
