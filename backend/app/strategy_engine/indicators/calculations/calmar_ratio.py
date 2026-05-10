"""Calmar Ratio — annualised return divided by max drawdown.

Definition (Young, 1991):

    Over a trailing ``period``-bar window:
        annual_return = (close[i] / close[i - period + 1])
                        ** (annualization / period) - 1
        max_dd        = max((peak[j] - close[j]) / peak[j])
                        over the window, where peak is running max.

        Calmar = annual_return / max_dd

Calmar is the most stable of the drawdown-based ratios because
``max_dd`` is bounded in ``(0, 1]`` and its reciprocal isn't
explosive in low-volatility regimes (unlike Sharpe's ``1 / std``).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(closes)`` -> ``[]``.
    * Window with no drawdown (monotone uptrend) -> ``None``
      (Calmar is undefined when ``max_dd == 0``).
"""

from __future__ import annotations

from collections.abc import Sequence


def calmar_ratio(
    closes: Sequence[float],
    period: int = 252,
    annualization: int = 252,
) -> list[float | None]:
    """Annualised return / max drawdown over a trailing window."""
    _check_period(period)
    if not isinstance(annualization, int) or annualization < 1:
        raise ValueError(
            f"annualization must be a positive int; got {annualization!r}."
        )
    n = len(closes)
    if n == 0 or period >= n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period, n):
        start = closes[i - period]
        end = closes[i]
        if start <= 0:
            continue
        annual_return = (end / start) ** (annualization / period) - 1.0

        peak = closes[i - period]
        max_dd = 0.0
        for j in range(i - period, i + 1):
            if closes[j] > peak:
                peak = closes[j]
            if peak <= 0:
                continue
            dd = (peak - closes[j]) / peak
            if dd > max_dd:
                max_dd = dd
        if max_dd == 0.0:
            continue
        out[i] = annual_return / max_dd
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["calmar_ratio"]
