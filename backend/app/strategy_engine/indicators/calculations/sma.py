"""Simple Moving Average — arithmetic mean over a sliding window.

Definition:
    ``SMA[i] = mean(values[i - period + 1 .. i])`` for ``i >= period - 1``.

Edge cases per Phase 1 contract:
    * ``len(values) == 0`` -> ``[]``
    * ``period > len(values)`` -> ``[]`` (insufficient data)
    * Otherwise: positions ``0 .. period - 2`` are ``None``; from
      ``period - 1`` onward, the SMA value is filled in.
"""

from __future__ import annotations

from collections.abc import Sequence


def sma(values: Sequence[float], period: int) -> list[float | None]:
    """Simple moving average of ``values`` with window ``period``.

    Args:
        values: Source price (or any numeric) series.
        period: Window size, must be a positive integer.

    Raises:
        ValueError: ``period`` is not a positive int.
    """
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * (period - 1)
    window_sum = float(sum(values[:period]))
    out.append(window_sum / period)
    for i in range(period, n):
        window_sum += values[i] - values[i - period]
        out.append(window_sum / period)
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["sma"]
