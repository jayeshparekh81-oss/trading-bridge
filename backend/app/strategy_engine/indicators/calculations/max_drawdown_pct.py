"""Rolling Max Drawdown (percent).

Definition:

    Over a trailing ``period``-bar window:
        peak[j]      = running max of closes[i - period + 1..j]
        drawdown[j]  = (peak[j] - closes[j]) / peak[j]
        out[i]       = max(drawdown[j] for j in window) * 100

Output is non-negative (a percent magnitude); ``0.0`` means the
window was monotonically rising.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(closes)`` -> ``[]``.
    * Bars where ``peak <= 0`` are skipped during the inner scan.
"""

from __future__ import annotations

from collections.abc import Sequence


def max_drawdown_pct(
    closes: Sequence[float], period: int = 60
) -> list[float | None]:
    """Rolling max drawdown as a percent over a trailing window."""
    _check_period(period)
    n = len(closes)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        peak = closes[i - period + 1]
        max_dd = 0.0
        for j in range(i - period + 1, i + 1):
            if closes[j] > peak:
                peak = closes[j]
            if peak <= 0:
                continue
            dd = (peak - closes[j]) / peak
            if dd > max_dd:
                max_dd = dd
        out[i] = max_dd * 100.0
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["max_drawdown_pct"]
