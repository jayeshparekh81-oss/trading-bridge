"""RSI vs price divergence detector.

Wraps the existing :mod:`rsi` calc with the shared divergence
helper. See :mod:`_divergence.detect_divergence` for the contract:

    +1.0 → bullish divergence (price made new low; RSI didn't)
    -1.0 → bearish divergence (price made new high; RSI didn't)
     0.0 → no divergence

Defaults ``rsi_period = 14``, ``lookback = 20``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations._divergence import (
    detect_divergence,
)
from app.strategy_engine.indicators.calculations.rsi import rsi


def rsi_divergence(
    closes: Sequence[float],
    rsi_period: int = 14,
    lookback: int = 20,
) -> list[float | None]:
    """Per-bar RSI-vs-price divergence code."""
    rsi_series = rsi(list(closes), rsi_period)
    if not rsi_series:
        return []
    return detect_divergence(closes, rsi_series, lookback)


__all__ = ["rsi_divergence"]
