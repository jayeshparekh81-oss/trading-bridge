"""Polynomial regression (degree 3) — current-bar projection.

Cubic variant of :mod:`polynomial_regression_2`. Captures
inflection points the quadratic can't (S-shaped trends, double
tops/bottoms in regression form).

Default ``period = 30``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 4`` rejected (need ``degree + 1`` points).
    * ``period > n`` -> ``[]``.
    * Singular fit -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations._polyfit import (
    polyfit_value_at_end,
)


def polynomial_regression_3(
    values: Sequence[float], period: int = 30,
) -> list[float | None]:
    """Cubic-fit value at the end of every trailing window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 4:
        raise ValueError(f"period must be an int >= 4; got {period!r}.")
    n = len(values)
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        out[i] = polyfit_value_at_end(values[i - period + 1 : i + 1], 3)
    return out


__all__ = ["polynomial_regression_3"]
