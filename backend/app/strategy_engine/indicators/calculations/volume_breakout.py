"""Volume breakout detector — current bar's volume vs its rolling average.

Per-bar code based on the ratio ``volume[i] / avg_volume_window[i]``:

    +1.0  → ratio > spike_mult (bullish if close > open, else bearish)
     0.0  → no breakout

We pair the spike with the bar's direction so the value carries
sign:

    +1.0  → volume spike on a green bar (close >= open)
    -1.0  → volume spike on a red bar (close < open)
     0.0  → no spike

Default ``period = 20``, ``spike_mult = 2.0`` (2x average volume).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Window with zero average volume -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def volume_breakout(
    opens: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 20,
    spike_mult: float = 2.0,
) -> list[float | None]:
    """Volume breakout per-bar code."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(spike_mult, (int, float)) or isinstance(spike_mult, bool):
        raise ValueError(f"spike_mult must be a number; got {spike_mult!r}.")
    if spike_mult <= 0:
        raise ValueError(f"spike_mult must be > 0; got {spike_mult}.")
    n = len(opens)
    if n != len(closes) or n != len(volumes):
        raise ValueError(
            f"opens, closes, volumes must have the same length; "
            f"got {n}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        avg_volume = sum(volumes[i - period + 1 : i + 1]) / period
        if avg_volume == 0:
            continue
        ratio = volumes[i] / avg_volume
        if ratio < spike_mult:
            out[i] = 0.0
        else:
            out[i] = 1.0 if closes[i] >= opens[i] else -1.0
    return out


__all__ = ["volume_breakout"]
