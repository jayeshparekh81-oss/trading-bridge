"""Price velocity - first derivative of close over a window.

ML-style feature. Defined as::

    velocity[i] = (close[i] - close[i - period]) / period

Output is in price units per bar. Sign is direction; magnitude is
the average per-bar move over the lookback. Output length matches
input. Positions ``0 .. period - 1`` are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= len(closes)`` -> ``[]``.
    * ``period`` not a positive int -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def price_velocity(
    closes: Sequence[float],
    period: int = 5,
) -> list[float | None]:
    """Average per-bar price change over ``period`` bars."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period, n):
        out[i] = (closes[i] - closes[i - period]) / period
    return out


__all__ = ["price_velocity"]
