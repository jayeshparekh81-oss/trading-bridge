"""Linear Weighted Moving Average.

Definition:
    Weights are 1, 2, ..., period (oldest -> newest). The WMA at index
    ``i >= period - 1`` is::

        WMA[i] = sum(values[i - period + 1 + k] * (k + 1) for k in 0..period - 1)
                 / (period * (period + 1) / 2)

    Positions ``0 .. period - 2`` are ``None``.

Edge cases per Phase 1 contract:
    * ``len(values) == 0`` -> ``[]``
    * ``period > len(values)`` -> ``[]``
"""

from __future__ import annotations

from collections.abc import Sequence


def wma(values: Sequence[float], period: int) -> list[float | None]:
    """Linear-weighted moving average."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    weights = list(range(1, period + 1))
    weight_total = period * (period + 1) / 2.0

    out: list[float | None] = [None] * (period - 1)
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        weighted_sum = sum(v * w for v, w in zip(window, weights, strict=True))
        out.append(weighted_sum / weight_total)
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["wma"]
