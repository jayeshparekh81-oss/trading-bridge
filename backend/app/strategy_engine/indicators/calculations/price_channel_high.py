"""Price Channel — upper band (highest high over a rolling window).

Mirror of Pine ``ta.highest(high, length)``. Distinct from the
existing ``donchian_channel`` indicator (which exposes the
midline of the high/low envelope as its primary output) — this
is the raw upper line, useful as a single-value breakout signal.

Definition::

    upper[i] = max(high over period bars ending at i)

Default ``period = 20``.

Output length equals input length. Indices ``0 .. period - 2`` are
``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period > n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def price_channel_high(
    highs: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Highest-high price channel over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        out[i] = max(highs[i - period + 1 : i + 1])
    return out


__all__ = ["price_channel_high"]
