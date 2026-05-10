"""Awesome Oscillator (Bill Williams).

Definition::

    median[i] = (high[i] + low[i]) / 2
    AO        = SMA(median, fast) - SMA(median, slow)

Default fast/slow = 5/34. Pine equivalent is ``ta.ao``. Histogram-
style oscillator — colours typically encode rising vs falling for
the trader's screen, but the raw line is what we expose.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``slow >= n`` -> ``[]``.
    * ``fast >= slow`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def awesome_oscillator(
    highs: Sequence[float],
    lows: Sequence[float],
    fast: int = 5,
    slow: int = 34,
) -> list[float | None]:
    """Bill Williams' Awesome Oscillator over the bar median."""
    _check_period(fast, "fast")
    _check_period(slow, "slow")
    if fast >= slow:
        raise ValueError(
            f"fast must be strictly less than slow; got fast={fast}, slow={slow}."
        )
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or slow > n:
        return []

    median = [(highs[i] + lows[i]) / 2.0 for i in range(n)]
    out: list[float | None] = [None] * n
    for i in range(slow - 1, n):
        fast_avg = sum(median[i - fast + 1 : i + 1]) / fast
        slow_avg = sum(median[i - slow + 1 : i + 1]) / slow
        out[i] = fast_avg - slow_avg
    return out


def _check_period(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive int; got {value!r}.")


__all__ = ["awesome_oscillator"]
