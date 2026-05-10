"""Moving Average Convergence Divergence.

Definition:
    macd_line  = EMA(fast_period) - EMA(slow_period)
    signal     = EMA(signal_period) of the macd_line (over its non-None tail)
    histogram  = macd_line - signal

The signal-line EMA is computed only over positions where macd_line is
defined. To preserve output-length parity with the input, positions where
either operand is ``None`` are filled with ``None``.

Edge cases per Phase 1 contract:
    * ``len(values) == 0`` -> three empty lists.
    * ``slow_period > len(values)`` -> three empty lists (macd would be
      empty anyway, so signal/histogram are too).
    * Otherwise, all three returned lists have ``len(values)`` elements.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def macd(
    values: Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD, signal line, histogram. Returns three same-length lists."""
    _check_periods(fast_period, slow_period, signal_period)
    n = len(values)
    if n == 0:
        return [], [], []

    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    if not fast or not slow:
        return [], [], []

    macd_line: list[float | None] = []
    for f, s in zip(fast, slow, strict=True):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    # Signal EMA computed only on the defined tail of macd_line.
    first_defined = next((i for i, v in enumerate(macd_line) if v is not None), None)
    if first_defined is None:
        return macd_line, [None] * n, [None] * n

    defined_tail = [v for v in macd_line[first_defined:] if v is not None]
    signal_tail = ema(defined_tail, signal_period)

    signal: list[float | None] = [None] * n
    if signal_tail:
        for offset, val in enumerate(signal_tail):
            signal[first_defined + offset] = val

    histogram: list[float | None] = []
    for m, sg in zip(macd_line, signal, strict=True):
        if m is None or sg is None:
            histogram.append(None)
        else:
            histogram.append(m - sg)

    return macd_line, signal, histogram


def _check_periods(fast: int, slow: int, signal: int) -> None:
    for name, value in (("fast_period", fast), ("slow_period", slow), ("signal_period", signal)):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive int; got {value!r}.")
    if fast >= slow:
        raise ValueError(
            f"fast_period ({fast}) must be < slow_period ({slow}); MACD is defined as fast - slow."
        )


__all__ = ["macd"]
