"""Zero-Lag Exponential Moving Average (ZLEMA, John Ehlers).

Removes the EMA's intrinsic lag by using a *de-lagged* input
series (price + the lookback delta) rather than raw price.

Definition::

    lag    = (period - 1) / 2                              # rounded
    delta  = value[i] - value[i - lag]
    de_lagged[i] = value[i] + delta
    ZLEMA  = EMA(de_lagged, period)

Default ``period = 20``.

Output length equals input length. ``None`` for the EMA warm-up
plus the additional ``lag`` bars at the start (we can't compute
``de_lagged`` for those).

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` rejected.
    * ``period > n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def zlema(
    values: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Zero-Lag EMA over a de-lagged input series."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(values)
    if n == 0 or period > n:
        return []

    lag = (period - 1) // 2
    if lag >= n:
        return [None] * n

    de_lagged: list[float] = [0.0] * n
    for i in range(n):
        if i < lag:
            de_lagged[i] = values[i]
        else:
            de_lagged[i] = values[i] + (values[i] - values[i - lag])

    smoothed = ema(de_lagged, period)
    if not smoothed:
        return [None] * n

    # Mask the first ``lag`` bars where the de-lagged input was a
    # placeholder; downstream values are the real ZLEMA.
    out: list[float | None] = list(smoothed)
    for i in range(min(lag, n)):
        out[i] = None
    return out


__all__ = ["zlema"]
