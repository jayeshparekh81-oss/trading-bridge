"""Volume-at-Price — Point Of Control (POC) projection.

For each bar i, looks back ``period`` bars and bins the price
range into ``bins`` equal-width buckets. Each bucket accumulates
the volumes of bars whose close fell in it. The bin with the
highest accumulated volume is the *Point Of Control* (POC) — we
emit its centre price.

Definition::

    window      = bars [i - period + 1 .. i]
    price_low   = min(close in window)
    price_high  = max(close in window)
    bin_width   = (price_high - price_low) / bins
    poc_bin     = argmax(sum(volume per bin))
    POC[i]      = price_low + (poc_bin + 0.5) * bin_width

Default ``period = 60``, ``bins = 50``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n`` -> ``[]``.
    * Flat window (price_high == price_low) -> POC is the flat price itself.
"""

from __future__ import annotations

from collections.abc import Sequence


def volume_at_price_high(
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 60,
    bins: int = 50,
) -> list[float | None]:
    """Per-bar Point-Of-Control price."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(bins, int) or isinstance(bins, bool) or bins < 2:
        raise ValueError(f"bins must be an int >= 2; got {bins!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0 or period >= n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window_closes = closes[i - period + 1 : i + 1]
        window_volumes = volumes[i - period + 1 : i + 1]
        price_low = min(window_closes)
        price_high = max(window_closes)
        if price_high == price_low:
            out[i] = price_low
            continue
        width = (price_high - price_low) / bins
        bin_volumes = [0.0] * bins
        for c, v in zip(window_closes, window_volumes, strict=True):
            idx = int((c - price_low) / width)
            if idx >= bins:
                idx = bins - 1  # top edge of the highest bin
            bin_volumes[idx] += v
        # argmax — first match wins (deterministic for ties).
        poc_bin = max(range(bins), key=lambda k: bin_volumes[k])
        out[i] = price_low + (poc_bin + 0.5) * width
    return out


__all__ = ["volume_at_price_high"]
