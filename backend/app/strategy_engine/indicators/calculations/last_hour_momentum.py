"""Last-hour momentum — close-to-close change in the last ``minutes``
of the trading session.

For bars within the last ``minutes`` of the session (i.e.
timestamp >= close_time - minutes), emits the % change between
the bar's close and the close of the bar that opened the
last-hour window. For bars outside the window, returns ``None``.

Useful as a "close-of-day momentum" filter — strategies that
want to ride afternoon trend continuation or fade exhaustion
moves into the close.

Defaults ``minutes = 60``, ``market_close_hour = 15``,
``market_close_min = 30`` (NSE close).

Frequency-aware: returns all-``None`` for daily-or-larger
candles.

Output length equals input length.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Daily frequency -> all-``None``.
    * Bar before the last-hour window -> ``None``.
    * First bar of the last-hour window -> 0.0 (baseline).
    * Anchor close == 0 -> ``None`` for that day.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def last_hour_momentum(
    closes: Sequence[float],
    timestamps: Sequence[datetime],
    minutes: int = 60,
    market_close_hour: int = 15,
    market_close_min: int = 30,
) -> list[float | None]:
    """Per-intraday-bar % change since the last-hour window opened."""
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
        raise ValueError(f"minutes must be a positive int; got {minutes!r}.")
    if not isinstance(market_close_hour, int) or isinstance(market_close_hour, bool):
        raise ValueError(f"market_close_hour must be an int; got {market_close_hour!r}.")
    if not 0 <= market_close_hour <= 23:
        raise ValueError(f"market_close_hour must be in [0, 23]; got {market_close_hour}.")
    if not isinstance(market_close_min, int) or isinstance(market_close_min, bool):
        raise ValueError(f"market_close_min must be an int; got {market_close_min!r}.")
    if not 0 <= market_close_min <= 59:
        raise ValueError(f"market_close_min must be in [0, 59]; got {market_close_min}.")
    n = len(closes)
    if n != len(timestamps):
        raise ValueError(
            f"closes and timestamps must have the same length; "
            f"got {n}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    # Group bar indices by trading date for per-day window logic.
    by_date: dict[object, list[int]] = {}
    for i, ts in enumerate(timestamps):
        by_date.setdefault(ts.date(), []).append(i)

    out: list[float | None] = [None] * n
    for indices in by_date.values():
        # Compute the last-hour window's start datetime for this date.
        first_ts = timestamps[indices[0]]
        close_dt = first_ts.replace(
            hour=market_close_hour, minute=market_close_min,
            second=0, microsecond=0,
        )
        window_start = close_dt - timedelta(minutes=minutes)
        anchor_close: float | None = None
        for k in indices:
            if timestamps[k] < window_start:
                continue
            if anchor_close is None:
                anchor_close = closes[k]
            if anchor_close == 0:
                continue
            out[k] = (closes[k] - anchor_close) / anchor_close * 100.0
    return out


__all__ = ["last_hour_momentum"]
