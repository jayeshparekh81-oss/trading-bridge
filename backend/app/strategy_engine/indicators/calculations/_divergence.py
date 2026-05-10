"""Shared divergence-detection helper.

Used by :mod:`rsi_divergence`, :mod:`macd_divergence`, and
:mod:`obv_divergence`. Detects "regular" divergence — the
classic textbook variety:

    +1.0  → bullish divergence (price made new low; indicator did not)
    -1.0  → bearish divergence (price made new high; indicator did not)
     0.0  → no divergence at this bar

For each bar i, looks back ``lookback`` bars and finds the *prior*
swing extreme in the price series. If the current bar prints a
new extreme but the indicator at that bar fails to confirm
(doesn't print a matching extreme), we flag a divergence.

Cleanest, deterministic, single-bar emission — operators wanting
a multi-bar swing window can build on top.
"""

from __future__ import annotations

from collections.abc import Sequence


def detect_divergence(
    prices: Sequence[float],
    indicator: Sequence[float | None],
    lookback: int,
) -> list[float | None]:
    """Per-bar divergence code over a trailing ``lookback`` window.

    ``prices`` and ``indicator`` must have the same length. The
    indicator may carry ``None`` entries (warmup bars); divergence
    is always ``None`` at any bar where the indicator window
    contains a ``None``.
    """
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 2:
        raise ValueError(f"lookback must be an int >= 2; got {lookback!r}.")
    n = len(prices)
    if n != len(indicator):
        raise ValueError(
            f"prices and indicator must have the same length; "
            f"got {n}, {len(indicator)}."
        )
    if n == 0 or lookback >= n:
        return []
    out: list[float | None] = [None] * n
    for i in range(lookback, n):
        ind_now = indicator[i]
        if ind_now is None:
            continue
        window_prices = prices[i - lookback : i]
        window_indicator = indicator[i - lookback : i]
        # Skip if any indicator value in the window is unavailable.
        if any(v is None for v in window_indicator):
            out[i] = 0.0
            continue
        prior_price_high = max(window_prices)
        prior_price_low = min(window_prices)
        # Reify the type narrowing — every entry is non-None inside
        # this branch.
        ind_floats: list[float] = [v for v in window_indicator if v is not None]
        prior_ind_high = max(ind_floats)
        prior_ind_low = min(ind_floats)

        new_price_high = prices[i] > prior_price_high
        new_price_low = prices[i] < prior_price_low
        ind_confirms_high = ind_now > prior_ind_high
        ind_confirms_low = ind_now < prior_ind_low

        if new_price_high and not ind_confirms_high:
            out[i] = -1.0  # bearish divergence
        elif new_price_low and not ind_confirms_low:
            out[i] = 1.0  # bullish divergence
        else:
            out[i] = 0.0
    return out


__all__ = ["detect_divergence"]
