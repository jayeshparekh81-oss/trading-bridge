"""Session-high breakout flag — 1 when current bar's high is the
day's running high (excluding the current bar's own contribution).

Useful as an intraday breakout signal: bar high crossing above
the prior intra-day high that hasn't been seen since session
open. Resets every trading day.

Per bar emits:

    1.0  -> current bar's high > prior running session high
    0.0  -> not a new session high

The "prior running session high" excludes the current bar so
the signal fires on the bar that broke out, not after.

Frequency-aware: returns all-``None`` for daily+ candles.

Output length equals input length.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Daily frequency -> all-``None``.
    * First bar of day -> always 1.0 (no prior bar to compare).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def session_high_breakout(
    highs: Sequence[float],
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """1 / 0 per intraday bar; new-session-high flag."""
    n = len(highs)
    if n != len(timestamps):
        raise ValueError(
            f"highs and timestamps must have the same length; "
            f"got {n}, {len(timestamps)}."
        )
    if n == 0:
        return []
    if n < 2 or timestamps[1] - timestamps[0] >= timedelta(hours=24):
        return [None] * n

    out: list[float | None] = [None] * n
    running_high: float | None = None
    current_date = None
    for i, ts in enumerate(timestamps):
        if ts.date() != current_date:
            current_date = ts.date()
            # First bar of the session — always counts as a new high.
            running_high = highs[i]
            out[i] = 1.0
            continue
        # ``running_high`` is set above when we first hit this date.
        prior = running_high if running_high is not None else highs[i]
        if highs[i] > prior:
            out[i] = 1.0
            running_high = highs[i]
        else:
            out[i] = 0.0
    return out


__all__ = ["session_high_breakout"]
