"""Opening gap size — today's open vs yesterday's close, in %.

For each bar that starts a new session day, computes::

    out[i] = (open[i] - prior_session_close) / prior_session_close * 100

For non-session-opening bars within the same trading day, the
value is the same gap size (constant for the rest of the day —
the gap is a per-day property).

Distinct from Pack 8's :mod:`gap_up_down` (which classifies
gaps as +1 / 0 / -1 based on a threshold). This indicator
returns the continuous % size — useful as input to "fade large
gaps" or "follow small gaps" strategies.

No params — works on intraday + daily bars equally.

Output length equals input length. The first session in the
input gets ``None`` (no prior session to gap from).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Prior-session close == 0 -> ``None`` for that day.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime


def opening_gap_size(
    opens: Sequence[float],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
) -> list[float | None]:
    """Per-bar opening-gap size as % of prior-session close."""
    n = len(opens)
    if n != len(closes) or n != len(timestamps):
        raise ValueError(
            f"opens, closes, timestamps must have the same length; "
            f"got {n}, {len(closes)}, {len(timestamps)}."
        )
    if n == 0:
        return []

    # Per-date: opening price (first bar's open) and closing
    # price (last bar's close) for each trading date.
    by_date: dict[object, list[int]] = {}
    date_keys: list[object] = []
    for i, ts in enumerate(timestamps):
        d = ts.date()
        if d not in by_date:
            by_date[d] = []
            date_keys.append(d)
        by_date[d].append(i)

    daily_gap: dict[object, float | None] = {}
    for pos, d in enumerate(date_keys):
        if pos == 0:
            daily_gap[d] = None  # no prior session
            continue
        prior_close = closes[by_date[date_keys[pos - 1]][-1]]
        today_open = opens[by_date[d][0]]
        if prior_close == 0:
            daily_gap[d] = None
        else:
            daily_gap[d] = (today_open - prior_close) / prior_close * 100.0

    out: list[float | None] = [None] * n
    for i, ts in enumerate(timestamps):
        out[i] = daily_gap[ts.date()]
    return out


__all__ = ["opening_gap_size"]
