"""Moving Average Envelope — upper band.

Definition::

    base[i]  = SMA(close, period)[i]
    upper[i] = base[i] * (1 + pct / 100)

Default ``period = 20``, ``pct = 2.5`` (a percent value, not a
fraction — ``2.5`` means ±2.5 % around the mean).

Output length equals input length. ``None`` for the warm-up
(period - 1 bars).

Edge cases:
    * Empty input -> ``[]``.
    * ``period > n`` -> ``[]``.
    * ``pct < 0`` -> ``ValueError`` (would invert the bands).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.sma import sma


def envelope_upper(
    values: Sequence[float],
    period: int = 20,
    pct: float = 2.5,
) -> list[float | None]:
    """Upper envelope = SMA * (1 + pct/100)."""
    _validate(period, pct)
    base = sma(list(values), period)
    if not base:
        return []
    factor = 1.0 + pct / 100.0
    return [None if v is None else v * factor for v in base]


def _validate(period: int, pct: float) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(pct, (int, float)) or isinstance(pct, bool):
        raise ValueError(f"pct must be a number; got {pct!r}.")
    if pct < 0:
        raise ValueError(f"pct must be >= 0; got {pct}.")


__all__ = ["envelope_upper"]
