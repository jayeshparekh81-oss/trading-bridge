"""On-Balance Volume — EMA-smoothed.

Wrapper around the existing :mod:`obv` cumulative line plus an
EMA smoothing pass. Crossings of OBV vs its smoothed line are
classic Granville signals (1963 — original OBV inventor).

Definition::

    OBV_smooth[i] = EMA(OBV(close, volume), ema_period)[i]

Default ``ema_period = 21``.

Output length equals input length. The EMA seeds at
``ema_period - 1``; everything before is ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``ema_period > n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema
from app.strategy_engine.indicators.calculations.obv import obv


def on_balance_volume_ema(
    closes: Sequence[float],
    volumes: Sequence[float],
    ema_period: int = 21,
) -> list[float | None]:
    """OBV smoothed by an EMA of ``ema_period`` bars."""
    if not isinstance(ema_period, int) or isinstance(ema_period, bool) or ema_period <= 0:
        raise ValueError(f"ema_period must be a positive int; got {ema_period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0 or ema_period > n:
        return []

    obv_line = obv(list(closes), list(volumes))
    if not obv_line:
        return [None] * n
    obv_filled = [v if v is not None else 0.0 for v in obv_line]
    smoothed = ema(obv_filled, ema_period)
    if not smoothed:
        return [None] * n
    return list(smoothed)


__all__ = ["on_balance_volume_ema"]
