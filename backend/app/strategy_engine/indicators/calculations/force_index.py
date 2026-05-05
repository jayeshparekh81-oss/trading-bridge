"""Force Index (Elder, 1993).

Definition::

    raw[i] = (close[i] - close[i - 1]) * volume[i]              # for i >= 1
    FI[i]  = EMA(raw, period)[i]                                 # smoothed

The EMA smoothing damps single-bar noise so the indicator's sign tracks
the dominant short-term flow. The raw bar-by-bar version is the
``period = 1`` special case.

Output length equals input length. Index 0 is always ``None`` (no prior
close to take the difference); the EMA seed lands at index ``period``
because the raw series has its first defined value at index 1.

Edge cases per Phase 1 contract:
    * Empty input or mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= len(closes)`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def force_index(
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 13,
) -> list[float | None]:
    """Smoothed Force Index over ``period`` bars."""
    _check_period(period)
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0 or period >= n:
        return []

    raw = [0.0] * (n - 1)
    for i in range(1, n):
        raw[i - 1] = (closes[i] - closes[i - 1]) * volumes[i]

    smoothed = ema(raw, period)
    if not smoothed:
        return [None] * n

    out: list[float | None] = [None] * n
    # `raw` is shifted by 1 vs the original index (raw[k] corresponds to
    # bar k + 1). Place the smoothed values back at their original bars.
    for k, val in enumerate(smoothed):
        out[k + 1] = val
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["force_index"]
