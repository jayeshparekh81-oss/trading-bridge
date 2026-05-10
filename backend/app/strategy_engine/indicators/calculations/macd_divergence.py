"""MACD line vs price divergence detector.

Uses the *MACD line* (not the signal or histogram) for the
divergence comparison. Defaults match conventional MACD:
``fast = 12``, ``slow = 26``, ``signal = 9``, ``lookback = 20``.

The signal-period parameter is kept for parameter-shape parity
with the standard MACD config — it doesn't affect the divergence
detection (which reads the MACD line only)."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations._divergence import (
    detect_divergence,
)
from app.strategy_engine.indicators.calculations.macd import macd


def macd_divergence(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    lookback: int = 20,
) -> list[float | None]:
    """Per-bar MACD-line-vs-price divergence code."""
    macd_line, _signal_line, _hist = macd(list(closes), fast, slow, signal)
    if not macd_line:
        return []
    return detect_divergence(closes, macd_line, lookback)


__all__ = ["macd_divergence"]
