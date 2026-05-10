"""Momentum Oscillator - classic ``close - close[period]``.

Pine ``ta.mom(source, length)`` equivalent. Unbounded; sign is
direction, magnitude is price units. Distinct from ROC (which is a
percentage). Distinct from ``momentum_quality_score`` (Pack 17,
which is a normalised 0..100 composite).

Output length matches input. Positions ``0 .. period - 1`` are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period`` not a positive int -> ``ValueError``.
    * ``period >= len(closes)`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def momentum_oscillator(
    closes: Sequence[float],
    period: int = 10,
) -> list[float | None]:
    """``close[i] - close[i - period]`` per bar."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period, n):
        out[i] = closes[i] - closes[i - period]
    return out


__all__ = ["momentum_oscillator"]
