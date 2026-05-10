"""R-squared — coefficient of determination of the linear-regression fit.

Per bar, fits a line to the trailing ``period`` window of values
and reports R^2 — the fraction of variance explained by the linear
fit. Range ``[0, 1]``.

    1.0 -> perfect linear fit (window points all on the line)
    0.0 -> no linear relationship (line explains no variance)

Useful as a "trend purity" filter — high R^2 = clean trend; low =
choppy / non-linear regime.

Definition::

    n          = period
    sx         = (n - 1) / 2
    Sxx        = (n^3 - n) / 12
    Sxy        = sum((x - sx) * (y - mean(y)))
    Syy        = sum((y - mean(y))^2)
    R^2        = Sxy^2 / (Sxx * Syy)        (0 if Syy == 0)

Default ``period = 14``.

Output length equals input length. Indices ``0 .. period - 2``
are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period > n`` -> ``[]``.
    * Constant window (Syy = 0) -> 0.0 (no variance to explain).
"""

from __future__ import annotations

from collections.abc import Sequence


def r_squared(
    values: Sequence[float], period: int = 14,
) -> list[float | None]:
    """R^2 of the linear-regression fit over a trailing window."""
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
        syy = sum((y - mean_y) ** 2 for y in window)
        if syy == 0:
            out[i] = 0.0
            continue
        r2 = (sxy * sxy) / (sxx * syy)
        # Clamp to [0, 1] (defensive — round-off can nudge slightly
        # over 1 on near-perfect fits).
        out[i] = max(0.0, min(1.0, r2))
    return out


__all__ = ["r_squared"]
