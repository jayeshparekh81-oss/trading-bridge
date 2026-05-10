"""Price Channel — lower band (lowest low over a rolling window).

Mirror of Pine ``ta.lowest(low, length)``. Companion to
:mod:`price_channel_high`."""

from __future__ import annotations

from collections.abc import Sequence


def price_channel_low(
    lows: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Lowest-low price channel over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(lows)
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        out[i] = min(lows[i - period + 1 : i + 1])
    return out


__all__ = ["price_channel_low"]
