"""Buying Pressure Ratio — fraction of window-volume on bullish bars.

Definition::

    bull[i]   = volume[i] if close[i] >= open[i] else 0
    BPR[i]    = sum(bull over period) / sum(volume over period)

Output range is ``[0, 1]``. Sustained > 0.5 = buyers dominate;
< 0.5 = sellers dominate. Distinct from `balance_of_power`
(per-bar, no volume) and `cumulative_volume_delta` (running
total, no normalisation).

Default ``period = 20``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Window with zero total volume -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def buying_pressure_ratio(
    opens: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Buying-pressure ratio over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(opens)
    if n != len(closes) or n != len(volumes):
        raise ValueError(
            f"opens, closes, volumes must have the same length; "
            f"got {n}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or period > n:
        return []

    bull = [
        volumes[i] if closes[i] >= opens[i] else 0.0 for i in range(n)
    ]
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        bull_sum = sum(bull[i - period + 1 : i + 1])
        vol_sum = sum(volumes[i - period + 1 : i + 1])
        if vol_sum == 0:
            continue
        out[i] = bull_sum / vol_sum
    return out


__all__ = ["buying_pressure_ratio"]
