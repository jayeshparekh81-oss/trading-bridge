"""McGinley Dynamic — adaptive moving average (John McGinley, 1990).

A self-tuning moving average that responds faster in up-trends
and slower in down-trends than a fixed-period EMA, reducing
whipsaw on volatile markets.

Definition::

    MD[0] = close[0]
    MD[i] = MD[i - 1]
            + (close[i] - MD[i - 1])
              / (constant * period * (close[i] / MD[i - 1])^4)

Default ``period = 14``, ``constant = 0.6`` (McGinley's
recommendations).

Output length equals input length. No warm-up gap (the average
seeds at the first close).

Edge cases:
    * Empty input -> ``[]``.
    * ``period <= 0`` / ``constant <= 0`` -> ``ValueError``.
    * ``MD[i - 1] == 0`` (degenerate) -> ``MD[i] = close[i]`` for that bar
      to avoid division by zero.
"""

from __future__ import annotations

from collections.abc import Sequence


def mcginley_dynamic(
    closes: Sequence[float],
    period: int = 14,
    constant: float = 0.6,
) -> list[float | None]:
    """McGinley Dynamic adaptive moving average."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(constant, (int, float)) or isinstance(constant, bool):
        raise ValueError(f"constant must be a number; got {constant!r}.")
    if constant <= 0:
        raise ValueError(f"constant must be > 0; got {constant}.")
    n = len(closes)
    if n == 0:
        return []
    out: list[float | None] = [closes[0]]
    for i in range(1, n):
        prev = out[i - 1]
        if prev is None or prev == 0:
            out.append(closes[i])
            continue
        ratio = closes[i] / prev
        denom = constant * period * (ratio ** 4)
        if denom == 0:
            out.append(closes[i])
            continue
        out.append(prev + (closes[i] - prev) / denom)
    return out


__all__ = ["mcginley_dynamic"]
