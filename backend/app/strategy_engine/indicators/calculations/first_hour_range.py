"""First-hour range — high-low of the first ``minutes`` of each session.

Per intraday bar, returns the range (max-high - min-low) of the
first ``minutes`` of the trading day that bar belongs to. The
value is ``None`` for bars within the first-hour window itself
(the range isn't determined yet); after that the value is
constant for the rest of the session.

Useful as a session-volatility filter: large first-hour ranges
historically indicate trending sessions; tight ranges indicate
chop.

Default ``minutes = 60``.

Frequency-aware: returns all-``None`` for daily-or-larger
candles.

Output length equals input length.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Daily frequency -> all-``None``.
    * Bar inside the opening window -> ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def first_hour_range(
    highs: Sequence[float],
    lows: Sequence[float],
    timestamps: Sequence[datetime],
    minutes: int = 60,
) -> list[float | None]:
    """Per-intraday-bar first-hour range of its session day."""
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
        raise ValueError(f"minutes must be a positive int; got {minutes!r}.")
    n = len(highs)
    if n != len(lows) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    # Group bar indices by trading date.
    by_date: dict[object, list[int]] = {}
    for i, ts in enumerate(timestamps):
        by_date.setdefault(ts.date(), []).append(i)

    out: list[float | None] = [None] * n
    for indices in by_date.values():
        first_ts = timestamps[indices[0]]
        cutoff = first_ts + timedelta(minutes=minutes)
        # Bars inside the opening window contribute to the range
        # but don't get an emitted value (range not finalised).
        opening_bars = [k for k in indices if timestamps[k] < cutoff]
        if not opening_bars:
            continue
        opening_high = max(highs[k] for k in opening_bars)
        opening_low = min(lows[k] for k in opening_bars)
        rng = opening_high - opening_low
        for k in indices:
            if timestamps[k] < cutoff:
                continue
            out[k] = rng
    return out


__all__ = ["first_hour_range"]
