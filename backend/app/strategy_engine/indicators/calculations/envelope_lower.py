"""Moving Average Envelope — lower band.

Companion to :mod:`envelope_upper`. See that module for the
formula (this is just the matching ``-pct`` line)."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.sma import sma


def envelope_lower(
    values: Sequence[float],
    period: int = 20,
    pct: float = 2.5,
) -> list[float | None]:
    """Lower envelope = SMA * (1 - pct/100)."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(pct, (int, float)) or isinstance(pct, bool):
        raise ValueError(f"pct must be a number; got {pct!r}.")
    if pct < 0:
        raise ValueError(f"pct must be >= 0; got {pct}.")
    base = sma(list(values), period)
    if not base:
        return []
    factor = 1.0 - pct / 100.0
    return [None if v is None else v * factor for v in base]


__all__ = ["envelope_lower"]
