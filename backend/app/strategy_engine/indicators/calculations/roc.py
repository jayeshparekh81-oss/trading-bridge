"""Rate of Change.

Definition (matches Pine ``ta.roc``):

    ROC[i] = 100 * (values[i] - values[i - period]) / values[i - period]

The classic % momentum oscillator: positive when price is up
versus ``period`` bars ago, negative when down.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(values)`` -> ``[]`` (the lookback would
      reference an out-of-range index).
    * ``values[i - period] == 0`` -> ``None`` (division by zero).
"""

from __future__ import annotations

from collections.abc import Sequence


def roc(values: Sequence[float], period: int = 9) -> list[float | None]:
    """Rate of Change over ``period`` bars."""
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(values)
    if n == 0 or period >= n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period, n):
        ref = values[i - period]
        if ref == 0.0:
            out[i] = None
            continue
        out[i] = 100.0 * (values[i] - ref) / ref
    return out


__all__ = ["roc"]
