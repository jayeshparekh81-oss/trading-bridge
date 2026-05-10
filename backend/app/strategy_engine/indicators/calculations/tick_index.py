"""Tick Index — net up-tick proxy.

The real NYSE Tick Index is the net of up-ticking minus down-
ticking issues across the exchange. At the single-symbol calc
level we proxy with bar direction:

    bar_dir[i] = +1 if close[i] > close[i - 1] else -1 (0 if flat)
    TI[i]      = sum(bar_dir over period)

Range ``[-period, +period]``. Positive readings = net buying
pressure across the window; negative = net selling.

Default ``period = 5``.

Output length equals input length. Indices ``0 .. period - 1``
are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def tick_index(
    closes: Sequence[float],
    period: int = 5,
) -> list[float | None]:
    """Per-bar net up-tick count over the trailing window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []
    bar_dir: list[int] = [0] * n
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            bar_dir[i] = 1
        elif closes[i] < closes[i - 1]:
            bar_dir[i] = -1
    out: list[float | None] = [None] * n
    for i in range(period, n):
        out[i] = float(sum(bar_dir[i - period + 1 : i + 1]))
    return out


__all__ = ["tick_index"]
