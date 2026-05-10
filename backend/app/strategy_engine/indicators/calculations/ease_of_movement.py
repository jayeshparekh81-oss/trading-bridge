"""Ease of Movement (Richard Arms, 1995).

Definition::

    midpoint[i] = (high[i] + low[i]) / 2
    distance[i] = midpoint[i] - midpoint[i - 1]
    box_ratio[i] = (volume[i] / scale) / (high[i] - low[i])
    EMV_raw[i]  = distance[i] / box_ratio[i]
    EMV         = SMA(EMV_raw, period)

The ``scale`` factor is applied to keep the box ratio numerically
reasonable; we use ``10_000`` (the original reference) — the exact
constant doesn't change the sign or relative ordering, only the
unit. Default smoothing period = 14.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Flat bar (high == low) or zero volume -> EMV_raw is 0 that bar.
    * ``period >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

#: Box-ratio scale factor. Pure unit choice — see Richard Arms' 1995
#: book. Documented here so a future "what's this number?" reader
#: doesn't have to dig.
_BOX_RATIO_SCALE = 10_000.0


def ease_of_movement(
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """SMA-smoothed Ease of Movement."""
    _check_period(period)
    n = len(highs)
    if n != len(lows) or n != len(volumes):
        raise ValueError(
            f"highs, lows, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(volumes)}."
        )
    if n == 0 or period >= n:
        return []

    raw: list[float] = [0.0] * n
    for i in range(1, n):
        midpoint = (highs[i] + lows[i]) / 2.0
        prev_midpoint = (highs[i - 1] + lows[i - 1]) / 2.0
        distance = midpoint - prev_midpoint
        rng = highs[i] - lows[i]
        if rng == 0 or volumes[i] == 0:
            raw[i] = 0.0
            continue
        box_ratio = (volumes[i] / _BOX_RATIO_SCALE) / rng
        raw[i] = distance / box_ratio if box_ratio != 0 else 0.0

    out: list[float | None] = [None] * n
    for i in range(period, n):
        # SMA over the trailing ``period`` raw values (1-indexed
        # because raw[0] is always 0 by construction).
        window = raw[i - period + 1 : i + 1]
        out[i] = sum(window) / period
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["ease_of_movement"]
