"""Smoothed ROC - EMA of Rate-of-Change.

Reduces ROC's whipsaw by EMA-smoothing the raw ROC line. Two
parameters::

    roc_period    - lookback for the underlying ROC (default 10)
    smooth_period - EMA window applied to the ROC line (default 5)

Output is in the same units as ROC (percent change). Output length
matches input. ``None`` until both ROC and the smoothing EMA have
seeded.

Edge cases:
    * Empty input -> ``[]``.
    * Either period non-positive int -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema
from app.strategy_engine.indicators.calculations.roc import roc


def roc_smoothed(
    closes: Sequence[float],
    roc_period: int = 10,
    smooth_period: int = 5,
) -> list[float | None]:
    """EMA-smoothed ROC."""
    if not isinstance(roc_period, int) or isinstance(roc_period, bool) or roc_period < 1:
        raise ValueError(f"roc_period must be a positive int; got {roc_period!r}.")
    if not isinstance(smooth_period, int) or isinstance(smooth_period, bool) or smooth_period < 1:
        raise ValueError(f"smooth_period must be a positive int; got {smooth_period!r}.")
    n = len(closes)
    if n == 0:
        return []
    raw = roc(closes, roc_period)
    if not raw:
        return [None] * n
    defined: list[float] = []
    first_idx: int | None = None
    for i, v in enumerate(raw):
        if v is not None:
            if first_idx is None:
                first_idx = i
            defined.append(v)
    if first_idx is None:
        return [None] * n
    smoothed = ema(defined, smooth_period)
    if not smoothed:
        return [None] * n
    out: list[float | None] = [None] * n
    for k, v in enumerate(smoothed):
        out[first_idx + k] = v
    return out


__all__ = ["roc_smoothed"]
