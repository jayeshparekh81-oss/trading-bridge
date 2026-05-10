"""Polynomial regression (degree 2) — current-bar projection.

Per bar, fits a quadratic ``y = a + b*x + c*x^2`` to the
trailing ``period`` window and emits the polynomial's value at
the last (current) x. Useful as a curvilinear smoother that
follows trends with concavity.

Default ``period = 30``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 3`` rejected (need ``degree + 1`` points).
    * ``period > n`` -> ``[]``.
    * Singular fit -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations._polyfit import (
    polyfit_value_at_end,
)


def polynomial_regression_2(
    values: Sequence[float], period: int = 30,
) -> list[float | None]:
    """Quadratic-fit value at the end of every trailing window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 3:
        raise ValueError(f"period must be an int >= 3; got {period!r}.")
    n = len(values)
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        out[i] = polyfit_value_at_end(values[i - period + 1 : i + 1], 2)
    return out


__all__ = ["polynomial_regression_2"]
