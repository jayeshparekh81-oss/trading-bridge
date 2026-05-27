"""Opening Range Breakout (ORB).

For each session day, compute the high / low of the first
``range_minutes`` of trading. Then per bar emit:

    +1.0  → close > opening-range high (long breakout)
    -1.0  → close < opening-range low  (short breakout)
     0.0  → inside the opening range
    None  → before the opening range completes that day

Requires intraday timestamps. If the candle frequency is daily
or larger (we detect by the first inter-bar gap), the function
returns an all-``None`` series with no exception — the dashboard
should surface a "ORB needs intraday data" hint via UI copy
rather than the calc layer raising.

Default ``range_minutes = 15`` (the conventional first-15-min ORB).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta


def opening_range_breakout(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
    range_minutes: int = 15,
) -> list[float | None]:
    """Per-bar ORB code; returns ``[]`` for empty input and
    all-``None`` for daily-or-larger candle frequencies."""
    if not isinstance(range_minutes, int) or isinstance(range_minutes, bool) or range_minutes <= 0:
        raise ValueError(f"range_minutes must be a positive int; got {range_minutes!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, closes, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(timestamps)}."
        )
    if n == 0:
        return []

    # Detect intraday vs daily — if we don't have at least one
    # bar within ``range_minutes`` of another, ORB is meaningless.
    if n >= 2 and (timestamps[1] - timestamps[0]) >= timedelta(minutes=range_minutes):
        return [None] * n

    # Group by trading date.
    out: list[float | None] = [None] * n
    by_date: dict[object, list[int]] = {}
    for i, ts in enumerate(timestamps):
        by_date.setdefault(ts.date(), []).append(i)

    for indices in by_date.values():
        first_ts = timestamps[indices[0]]
        cutoff = first_ts + timedelta(minutes=range_minutes)
        # Bars that fall within the opening-range window.
        or_indices = [k for k in indices if timestamps[k] < cutoff]
        if not or_indices:
            continue
        or_high = max(highs[k] for k in or_indices)
        or_low = min(lows[k] for k in or_indices)
        for k in indices:
            if timestamps[k] < cutoff:
                continue  # leave as None during opening-range window
            if closes[k] > or_high:
                out[k] = 1.0
            elif closes[k] < or_low:
                out[k] = -1.0
            else:
                out[k] = 0.0
    return out


def opening_range_levels(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
    range_minutes: int = 15,
) -> tuple[list[float | None], list[float | None]]:
    """Per-bar opening-range HIGH and LOW series for each session day.

    Companion to :func:`opening_range_breakout`, exposing the range bands that
    function computes internally so conditions can reference ``orb_N_high`` /
    ``orb_N_low``. Same windowing semantics: for each trading date the high/low of
    the first ``range_minutes`` define the range; bars at or after the window
    carry that day's high/low, bars before/within the window are ``None``. Returns
    two all-``None`` series for daily-or-larger candle frequencies (detected the
    same way as the signal calc) and ``([], [])`` for empty input.

    The signal function (``opening_range_breakout``) is intentionally left
    unchanged; this is a strictly additive sibling.
    """
    if not isinstance(range_minutes, int) or isinstance(range_minutes, bool) or range_minutes <= 0:
        raise ValueError(f"range_minutes must be a positive int; got {range_minutes!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(timestamps):
        raise ValueError(
            f"highs, lows, closes, timestamps must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(timestamps)}."
        )
    if n == 0:
        return [], []

    hi_out: list[float | None] = [None] * n
    lo_out: list[float | None] = [None] * n
    if n >= 2 and (timestamps[1] - timestamps[0]) >= timedelta(minutes=range_minutes):
        return hi_out, lo_out

    by_date: dict[object, list[int]] = {}
    for i, ts in enumerate(timestamps):
        by_date.setdefault(ts.date(), []).append(i)

    for indices in by_date.values():
        first_ts = timestamps[indices[0]]
        cutoff = first_ts + timedelta(minutes=range_minutes)
        or_indices = [k for k in indices if timestamps[k] < cutoff]
        if not or_indices:
            continue
        or_high = max(highs[k] for k in or_indices)
        or_low = min(lows[k] for k in or_indices)
        for k in indices:
            if timestamps[k] < cutoff:
                continue  # leave None during the opening-range window
            hi_out[k] = or_high
            lo_out[k] = or_low
    return hi_out, lo_out


__all__ = ["opening_range_breakout", "opening_range_levels"]
