"""Capitulation Signal — panic-bar detector.

Per-bar code that flags climax / capitulation events: huge
volume spike + range expansion + close near the bar's extreme.

    +1.0  -> buying-side capitulation (vol + range spike with
             close at the high — short-squeeze blowoff)
    -1.0  -> selling-side capitulation (vol + range spike with
             close at the low — panic flush)
     0.0  -> not a capitulation bar

Both signals are *contrarian* — capitulation often marks short-
term exhaustion, with mean-reversion to follow over the next
few bars.

Default ``vol_mult = 3.0`` (3x rolling-avg volume), ``range_mult
= 2.0`` (2x rolling-avg range), ``lookback = 20``,
``close_position_threshold = 0.85`` (close in the top/bottom
15 % of the bar's range).

Output length equals input length. Indices ``0 .. lookback - 1``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``lookback >= n`` -> ``[]``.
    * Window with zero average vol / range -> ``None`` for that bar.
    * Flat bar (high == low) -> 0.0 (no extreme to be near).
"""

from __future__ import annotations

from collections.abc import Sequence


def capitulation_signal(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    vol_mult: float = 3.0,
    range_mult: float = 2.0,
    lookback: int = 20,
    close_position_threshold: float = 0.85,
) -> list[float | None]:
    """Per-bar capitulation code."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback <= 0:
        raise ValueError(f"lookback must be a positive int; got {lookback!r}.")
    for name, val in (("vol_mult", vol_mult), ("range_mult", range_mult)):
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise ValueError(f"{name} must be a number; got {val!r}.")
        if val <= 0:
            raise ValueError(f"{name} must be > 0; got {val}.")
    if not 0 < close_position_threshold <= 1:
        raise ValueError(
            f"close_position_threshold must be in (0, 1]; "
            f"got {close_position_threshold}."
        )
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            f"highs, lows, closes, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or lookback >= n:
        return []

    ranges = [highs[i] - lows[i] for i in range(n)]
    out: list[float | None] = [None] * n
    for i in range(lookback, n):
        avg_vol = sum(volumes[i - lookback : i]) / lookback
        avg_range = sum(ranges[i - lookback : i]) / lookback
        if avg_vol == 0 or avg_range == 0:
            continue
        vol_spike = volumes[i] >= vol_mult * avg_vol
        range_spike = ranges[i] >= range_mult * avg_range
        if not (vol_spike and range_spike):
            out[i] = 0.0
            continue
        rng = highs[i] - lows[i]
        if rng == 0:
            out[i] = 0.0
            continue
        close_position = (closes[i] - lows[i]) / rng  # 0 = at low, 1 = at high
        if close_position >= close_position_threshold:
            out[i] = 1.0  # buying capitulation (close near high)
        elif close_position <= 1.0 - close_position_threshold:
            out[i] = -1.0  # selling capitulation (close near low)
        else:
            out[i] = 0.0
    return out


__all__ = ["capitulation_signal"]
