"""Volume-Weighted Average Close (VWAC).

Rolling volume-weighted average of close. Distinct from the
existing :mod:`vwap` indicator (which uses the typical price
(H+L+C)/3 and resets at session boundaries) — VWAC is a pure
trailing-window measure on the close series.

Definition::

    VWAC[i] = sum(close[k] * volume[k] for k in window)
              / sum(volume[k] for k in window)

Default ``period = 14``.

Output length equals input length. Indices ``0 .. period - 2`` are
``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Window with zero total volume -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def volume_weighted_avg_close(
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """VWAC over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        vol_sum = sum(volumes[i - period + 1 : i + 1])
        if vol_sum == 0:
            continue
        weighted = sum(
            closes[k] * volumes[k] for k in range(i - period + 1, i + 1)
        )
        out[i] = weighted / vol_sum
    return out


__all__ = ["volume_weighted_avg_close"]
