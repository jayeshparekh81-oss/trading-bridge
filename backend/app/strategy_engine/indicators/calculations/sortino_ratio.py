"""Annualised rolling Sortino Ratio.

Like Sharpe but uses the *downside* deviation — only negative
returns contribute to the denominator. Captures the upside-vs-
downside asymmetry traders care about.

Definition:

    downside_dev[i] = sqrt(mean(min(r - target, 0) ** 2))
                      over the window. Target defaults to 0.

    annual_excess  = (mean_r - risk_free / annualization) * annualization
    annual_dd      = downside_dev * sqrt(annualization)

    Sortino = annual_excess / annual_dd

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(closes)`` -> ``[]``.
    * Window with no losing bars (downside_dev == 0) -> ``None``
      (Sortino is undefined; treat as "ratio not meaningful here").
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def sortino_ratio(
    closes: Sequence[float],
    period: int = 252,
    annualization: int = 252,
    risk_free_rate: float = 0.0,
    target_return: float = 0.0,
) -> list[float | None]:
    """Annualised Sortino Ratio over a trailing window."""
    _check_period(period)
    if not isinstance(annualization, int) or annualization < 1:
        raise ValueError(
            f"annualization must be a positive int; got {annualization!r}."
        )
    n = len(closes)
    if n == 0 or period >= n:
        return []

    returns: list[float | None] = [None] * n
    for i in range(1, n):
        prev = closes[i - 1]
        if prev == 0:
            continue
        returns[i] = closes[i] / prev - 1.0

    rfr_per_bar = risk_free_rate / annualization
    sqrt_a = math.sqrt(annualization)
    out: list[float | None] = [None] * n
    for i in range(period, n):
        window = returns[i - period + 1 : i + 1]
        if any(v is None for v in window):
            continue
        floats = [v for v in window if v is not None]
        mean_r = sum(floats) / period
        downside_sq = sum(
            min(v - target_return, 0.0) ** 2 for v in floats
        )
        downside_dev = math.sqrt(downside_sq / period)
        if downside_dev == 0.0:
            continue
        out[i] = (mean_r - rfr_per_bar) * annualization / (
            downside_dev * sqrt_a
        )
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["sortino_ratio"]
