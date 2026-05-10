"""Trade Efficiency — net move per unit of intra-window range.

Per bar, compares the rolling window's *net* close-to-close
change to the *total* path (sum of absolute close-to-close
moves). High efficiency = price moved directly; low efficiency =
choppy / wandering.

Definition::

    net[i]   = close[i] - close[i - period]
    path[i]  = sum(|close[k] - close[k - 1]| for k in window)
    TE[i]    = net[i] / path[i]                            (range -1..+1)

Default ``period = 20``. Same idea as Kaufman's Efficiency Ratio
but signed (uses raw net rather than abs(net)) so direction is
preserved — useful for trend-following strategies that want both
strength + direction.

Output length equals input length. Indices ``0 .. period - 1``
are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
    * Window with zero path (constant prices) -> 0.0 (no
      directional move to score).
"""

from __future__ import annotations

from collections.abc import Sequence


def trade_efficiency(
    closes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Signed efficiency ratio over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period, n):
        net = closes[i] - closes[i - period]
        path = sum(
            abs(closes[k] - closes[k - 1])
            for k in range(i - period + 1, i + 1)
        )
        if path == 0:
            out[i] = 0.0
        else:
            out[i] = net / path
    return out


__all__ = ["trade_efficiency"]
