"""Autocorrelation of returns at a configurable lag.

Definition::

    return[i] = (close[i] - close[i - 1]) / close[i - 1]
    mu        = mean(returns over period)
    cov(lag)  = sum((r[k] - mu) * (r[k - lag] - mu)) / period
    var       = sum((r[k] - mu)^2) / period
    AC(lag)   = cov(lag) / var

Range ``[-1, +1]``. Positive at lag 1 = momentum (consecutive
returns tend to agree); negative = mean-reversion.

Defaults ``period = 30``, ``lag = 1``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period <= lag`` -> ``ValueError``.
    * ``period + lag >= n`` -> ``[]``.
    * Constant window (var = 0) -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def autocorrelation(
    closes: Sequence[float], period: int = 30, lag: int = 1,
) -> list[float | None]:
    """Per-bar autocorrelation of returns at the supplied lag."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 3:
        raise ValueError(f"period must be an int >= 3; got {period!r}.")
    if not isinstance(lag, int) or isinstance(lag, bool) or lag < 1:
        raise ValueError(f"lag must be a positive int; got {lag!r}.")
    if period <= lag:
        raise ValueError(
            f"period must be > lag; got period={period}, lag={lag}."
        )
    n = len(closes)
    if n == 0 or period + lag >= n:
        return []

    returns: list[float] = [0.0] * n
    for i in range(1, n):
        prev = closes[i - 1]
        if prev != 0:
            returns[i] = (closes[i] - prev) / prev

    out: list[float | None] = [None] * n
    for i in range(period + lag, n):
        window = returns[i - period + 1 : i + 1]
        mu = sum(window) / period
        var = sum((r - mu) ** 2 for r in window) / period
        if var == 0:
            continue
        cov = 0.0
        # AC: average of (r[k] - mu) * (r[k - lag] - mu) over the
        # period-lag pairs that fit inside the window.
        for k in range(lag, period):
            cov += (window[k] - mu) * (window[k - lag] - mu)
        cov /= (period - lag)
        out[i] = cov / var
    return out


__all__ = ["autocorrelation"]
