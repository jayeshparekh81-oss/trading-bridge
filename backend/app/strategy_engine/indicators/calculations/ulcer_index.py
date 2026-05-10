"""Ulcer Index — pessimistic drawdown measure (Peter Martin, 1987).

Definition::

    drawdown[i]   = (close[i] - max(close over period)) / max(close) * 100
    sq_avg[i]     = sum(drawdown^2 over period) / period
    UI[i]         = sqrt(sq_avg[i])

Output is non-negative — measures the *depth + duration* of
drawdowns over the window. Higher UI = more painful drawdowns.

Default ``period = 14``.

Output length equals input length. Indices ``0 .. period - 1``
are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period > n`` -> ``[]``.
    * ``max(close) == 0`` (degenerate) -> ``None`` for that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def ulcer_index(
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Ulcer Index over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = closes[i - period + 1 : i + 1]
        # Running peak as we walk forward through the window —
        # the textbook Martin definition. Computing ``max(window)``
        # instead would give every bar credit for *future* highs,
        # turning monotone uptrends into spurious drawdowns.
        running_peak = window[0]
        sq_sum = 0.0
        for c in window:
            running_peak = max(running_peak, c)
            if running_peak == 0:
                continue
            dd = (c - running_peak) / running_peak * 100.0
            sq_sum += dd * dd
        out[i] = math.sqrt(sq_sum / period)
    return out


__all__ = ["ulcer_index"]
