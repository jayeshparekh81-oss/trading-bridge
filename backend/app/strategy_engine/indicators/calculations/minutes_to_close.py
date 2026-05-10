"""Minutes-to-close — bars left until session close.

Per intraday bar, computes the number of minutes from the bar's
timestamp to the day's market close (default 15:30 IST). Useful
as an intraday session-position signal (e.g. flatten positions
in the last 15 minutes).

Returns negative values for bars *after* the close (e.g.
synthetic post-market data); ``None`` for bars before the
session opens that morning (treated as "previous day's overlap"
which doesn't apply for forward-looking strategies).

Defaults ``market_close_hour = 15``, ``market_close_min = 30``
(NSE close).

Output length equals input length.

Edge cases:
    * Empty input -> ``[]``.
    * Daily / weekly frequency -> all-``None``.
    * Bar later than session close -> negative number (informative).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def minutes_to_close(
    timestamps: Sequence[datetime],
    market_close_hour: int = 15,
    market_close_min: int = 30,
) -> list[float | None]:
    """Per-bar minutes-until-close (intraday only)."""
    if not isinstance(market_close_hour, int) or isinstance(market_close_hour, bool):
        raise ValueError(f"market_close_hour must be an int; got {market_close_hour!r}.")
    if not 0 <= market_close_hour <= 23:
        raise ValueError(f"market_close_hour must be in [0, 23]; got {market_close_hour}.")
    if not isinstance(market_close_min, int) or isinstance(market_close_min, bool):
        raise ValueError(f"market_close_min must be an int; got {market_close_min!r}.")
    if not 0 <= market_close_min <= 59:
        raise ValueError(f"market_close_min must be in [0, 59]; got {market_close_min}.")
    n = len(timestamps)
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    out: list[float | None] = [None] * n
    for i, ts in enumerate(timestamps):
        # Construct that day's close datetime in the same naive/aware
        # mode as the input timestamp.
        close_dt = ts.replace(
            hour=market_close_hour, minute=market_close_min,
            second=0, microsecond=0,
        )
        delta = close_dt - ts
        out[i] = delta.total_seconds() / 60.0
    return out


__all__ = ["minutes_to_close"]
