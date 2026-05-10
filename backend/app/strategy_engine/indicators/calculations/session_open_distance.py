"""Distance from the session's opening price, in % of the open.

For each intraday bar, computes::

    out[i] = (close[i] - session_open[i]) / session_open[i] * 100

where ``session_open`` is the open price of the FIRST bar of the
trading day that bar belongs to. Resets every trading day.

Useful as a session-position signal — strategies that want to
fade extended morning moves or ride afternoon momentum.

Frequency-aware: returns all-``None`` for daily-or-larger
candles (the concept doesn't apply when each bar is one
session).

Output length equals input length.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Daily / weekly frequency -> all-``None``.
    * Session open == 0 -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def session_open_distance(
    opens: Sequence[float],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """% distance from session open."""
    n = len(opens)
    if n != len(closes) or n != len(timestamps):
        raise ValueError(
            f"opens, closes, timestamps must have the same length; "
            f"got {n}, {len(closes)}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    # First-bar-of-day index for each bar.
    out: list[float | None] = [None] * n
    session_open: float | None = None
    current_date = None
    for i, ts in enumerate(timestamps):
        if ts.date() != current_date:
            current_date = ts.date()
            session_open = opens[i]
        if session_open is None or session_open == 0:
            continue
        out[i] = (closes[i] - session_open) / session_open * 100.0
    return out


__all__ = ["session_open_distance"]
