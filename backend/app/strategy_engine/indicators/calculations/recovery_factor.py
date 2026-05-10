"""Recovery Factor — net return / max drawdown over a window.

Definition:

    Over a trailing ``period``-bar window:
        net_return = close[i] - close[i - period + 1]   (rupee terms)
        max_dd_$   = max(peak - trough) over the window

        Recovery = net_return / max_dd_$

Higher values mean the strategy / instrument climbed more rupees
of return per rupee of drawdown — a robustness measure favoured by
trend-following systems.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(closes)`` -> ``[]``.
    * Window with zero drawdown (monotone rise) -> ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence


def recovery_factor(
    closes: Sequence[float], period: int = 60
) -> list[float | None]:
    """Net return / max drawdown ratio over a trailing window."""
    _check_period(period)
    n = len(closes)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        start = closes[i - period + 1]
        end = closes[i]
        net_return = end - start

        peak = start
        max_dd = 0.0
        for j in range(i - period + 1, i + 1):
            if closes[j] > peak:
                peak = closes[j]
            dd = peak - closes[j]
            if dd > max_dd:
                max_dd = dd
        if max_dd == 0.0:
            continue
        out[i] = net_return / max_dd
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["recovery_factor"]
