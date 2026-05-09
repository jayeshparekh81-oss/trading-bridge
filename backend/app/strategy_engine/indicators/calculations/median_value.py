"""Rolling Median — middle value of a trailing window.

Matches Pine ``ta.median(source, length)``. Even-length windows
return the average of the two middle elements (standard median
definition); odd-length windows return the middle element.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def median_value(
    values: Sequence[float], period: int = 20
) -> list[float | None]:
    """Median of each trailing ``period``-bar window."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = sorted(values[i - period + 1 : i + 1])
        if period % 2 == 1:
            out[i] = window[period // 2]
        else:
            mid = period // 2
            out[i] = (window[mid - 1] + window[mid]) / 2.0
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["median_value"]
