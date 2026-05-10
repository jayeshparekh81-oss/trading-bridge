"""Linear-regression slope at the end of the trailing window.

Companion to the existing :mod:`linear_regression` (which emits
the regressed value at the current bar). This module emits the
*slope* (per-bar drift) — useful as a directional momentum
signal: positive slope = up-trending best-fit line, negative =
down-trending.

Same closed-form OLS as the parent module; we just project a
different output.

Definition::

    n  = period
    sx = (n - 1) / 2
    Sxx = (n^3 - n) / 12
    Sxy = sum((x - sx) * (y - mean(y)))
    slope = Sxy / Sxx

Default ``period = 14``.

Output length equals input length. Indices ``0 .. period - 2``
are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * ``period < 2`` rejected.
"""

from __future__ import annotations

from collections.abc import Sequence


def linear_regression_slope(
    values: Sequence[float], period: int = 14,
) -> list[float | None]:
    """OLS slope over a trailing ``period``-bar window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(values)
    if n == 0 or period > n:
        return []
    sx = (period - 1) / 2.0
    sxx = (period ** 3 - period) / 12.0
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean_y = sum(window) / period
        sxy = sum(
            (k - sx) * (window[k] - mean_y) for k in range(period)
        )
        out[i] = sxy / sxx
    return out


__all__ = ["linear_regression_slope"]
