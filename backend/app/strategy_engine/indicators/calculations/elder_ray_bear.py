"""Elder Ray Bear Power (Alexander Elder, 1989).

Definition::

    Bear[i] = low[i] - EMA(close, period)[i]

Default ``period = 13``. Negative readings signal selling
pressure (the bar's low penetrated below the EMA); the magnitude
is the depth of penetration. Pair with :mod:`elder_ray_bull` for
the full Elder Ray system.

Output length equals input length. ``None`` for the EMA warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def elder_ray_bear(
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 13,
) -> list[float | None]:
    """Elder's Bear Power over an EMA of close."""
    _check_period(period)
    n = len(lows)
    if n != len(closes):
        raise ValueError(
            f"lows and closes must have the same length; got {n}, {len(closes)}."
        )
    if n == 0 or period >= n:
        return []

    base = ema(list(closes), period)
    if not base:
        return [None] * n
    out: list[float | None] = [None] * n
    for i in range(n):
        b = base[i]
        if b is None:
            continue
        out[i] = lows[i] - b
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["elder_ray_bear"]
