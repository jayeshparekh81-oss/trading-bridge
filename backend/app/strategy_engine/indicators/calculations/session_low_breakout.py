"""Session-low breakdown flag — companion to :mod:`session_high_breakout`.

Per intraday bar emits 1.0 when the bar's low is the day's
running low (i.e. price made a new session low). 0.0 otherwise.
``None`` for daily-or-larger frequencies."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def session_low_breakout(
    lows: Sequence[float],
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """1 / 0 per intraday bar; new-session-low flag."""
    n = len(lows)
    if n != len(timestamps):
        raise ValueError(
            f"lows and timestamps must have the same length; "
            f"got {n}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    out: list[float | None] = [None] * n
    running_low: float | None = None
    current_date = None
    for i, ts in enumerate(timestamps):
        if ts.date() != current_date:
            current_date = ts.date()
            running_low = lows[i]
            out[i] = 1.0
            continue
        prior = running_low if running_low is not None else lows[i]
        if lows[i] < prior:
            out[i] = 1.0
            running_low = lows[i]
        else:
            out[i] = 0.0
    return out


__all__ = ["session_low_breakout"]
