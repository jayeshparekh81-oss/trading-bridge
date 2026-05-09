"""Stochastic Oscillator — George Lane.

Two outputs:

    * ``%K`` (fast) — ``100 * (close - LL) / (HH - LL)`` over the
      last ``k_period`` bars.
    * ``%D`` (slow) — SMA of ``%K`` over ``d_period`` bars.

Pine's ``ta.stoch`` returns ``%K`` only; the canonical "Stochastic"
in chart UIs returns both.

Edge cases per Phase 1 contract:
    * Empty input -> ``([], [])``.
    * ``k_period > len(values)`` -> ``([], [])``.
    * Flat window (HH == LL) -> ``%K`` for that bar is ``None``.
    * ``%D`` is ``None`` until ``d_period`` consecutive ``%K``
      values are defined.
"""

from __future__ import annotations

from collections.abc import Sequence


def stochastic(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[list[float | None], list[float | None]]:
    """Return ``(percent_k, percent_d)``."""
    if not isinstance(k_period, int) or k_period < 1:
        raise ValueError(f"k_period must be a positive int; got {k_period!r}.")
    if not isinstance(d_period, int) or d_period < 1:
        raise ValueError(f"d_period must be a positive int; got {d_period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or k_period > n:
        return ([], [])

    k_line: list[float | None] = [None] * n
    for i in range(k_period - 1, n):
        hh = max(highs[i - k_period + 1 : i + 1])
        ll = min(lows[i - k_period + 1 : i + 1])
        denom = hh - ll
        if denom == 0.0:
            k_line[i] = None
            continue
        k_line[i] = 100.0 * (closes[i] - ll) / denom

    d_line: list[float | None] = [None] * n
    for i in range(d_period - 1, n):
        window = k_line[i - d_period + 1 : i + 1]
        if any(v is None for v in window):
            continue
        # mypy: window contents are guaranteed float here.
        d_line[i] = sum(v for v in window if v is not None) / d_period
    return (k_line, d_line)


__all__ = ["stochastic"]
