"""Volume Profile — fixed-range typical-price distribution.

Snapshot indicator (not per-bar series): builds a price-bin histogram
of volume over the last ``lookback`` bars.

Definition (LOCKED per reference doc):
    1. Window = last ``lookback`` bars.
    2. price_min = min(low) over window; price_max = max(high) over window.
    3. Divide [price_min, price_max] into ``bins`` equal-width bins.
    4. For each bar i in window:
           typical[i] = (high[i] + low[i] + close[i]) / 3
           Find the SINGLE bin containing typical[i] (not proportional).
           Add volume[i] to that bin's accumulator.
    5. POC = bin with highest accumulated volume; poc_price = midpoint.
    6. Value Area (VA): starting from POC, expand outward greedily
       (include whichever neighbouring bin — above or below — has the
       larger volume next) until accumulated volume >= value_area_pct
       * total_volume.
    7. VAH = upper edge of topmost included bin; VAL = lower edge of
       bottommost included bin.

    Defaults: bins=24, value_area_pct=0.7, lookback=100.

Returns:
    {
        "bins":  [{"price_lo": float, "price_hi": float, "volume": float}, ...],
        "poc":   float,              # midpoint of POC bin
        "vah":   float,              # value-area-high
        "val":   float,              # value-area-low
        "total_volume": float,
    }

Edge cases:
    * Empty / length-mismatch -> {} (empty dict)
    * Series shorter than lookback -> uses what's available (whole series)
    * Flat market (price_min == price_max) -> all volume in one degenerate
      bin, VA = whole range
    * Zero total volume -> still returns bins, poc/vah/val set to midpoint
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def volume_profile(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    bins: int = 24,
    lookback: int = 100,
    value_area_pct: float = 0.7,
) -> dict[str, Any]:
    """Fixed-range typical-price volume profile. Returns snapshot dict."""
    if not isinstance(bins, int) or isinstance(bins, bool) or bins < 1:
        raise ValueError(f"bins must be a positive int; got {bins!r}.")
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 1:
        raise ValueError(f"lookback must be a positive int; got {lookback!r}.")
    if not isinstance(value_area_pct, (int, float)) or isinstance(value_area_pct, bool):
        raise ValueError(f"value_area_pct must be numeric; got {value_area_pct!r}.")
    if not (0 < value_area_pct <= 1):
        raise ValueError(f"value_area_pct must be in (0, 1]; got {value_area_pct}.")

    n = len(highs)
    if not (n == len(lows) == len(closes) == len(volumes)):
        raise ValueError(
            f"highs, lows, closes, volumes must be same length; got "
            f"{n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0:
        return {}

    # Window = last `lookback` bars (or all if shorter).
    start = max(0, n - lookback)
    win_h = [float(x) for x in highs[start:]]
    win_l = [float(x) for x in lows[start:]]
    win_c = [float(x) for x in closes[start:]]
    win_v = [float(x) for x in volumes[start:]]
    m = len(win_h)

    price_min = min(win_l)
    price_max = max(win_h)
    if price_max == price_min:
        # Degenerate: single price. One bin holds everything.
        bin_volumes = [sum(win_v)]
        return {
            "bins": [
                {"price_lo": price_min, "price_hi": price_max, "volume": bin_volumes[0]}
            ],
            "poc": price_min,
            "vah": price_max,
            "val": price_min,
            "total_volume": bin_volumes[0],
        }

    bin_width = (price_max - price_min) / bins
    bin_volumes = [0.0] * bins

    for i in range(m):
        tp = (win_h[i] + win_l[i] + win_c[i]) / 3.0
        # Find bin index; clamp to last bin if tp == price_max exactly.
        idx = int((tp - price_min) / bin_width)
        if idx >= bins:
            idx = bins - 1
        elif idx < 0:
            idx = 0
        bin_volumes[idx] += win_v[i]

    total_volume = sum(bin_volumes)

    # Build bin descriptors.
    bin_descriptors = []
    for k in range(bins):
        lo = price_min + k * bin_width
        hi = price_min + (k + 1) * bin_width
        bin_descriptors.append({"price_lo": lo, "price_hi": hi, "volume": bin_volumes[k]})

    # POC = bin with max volume; tie-break by lowest index.
    poc_idx = max(range(bins), key=lambda k: bin_volumes[k])
    poc_price = (bin_descriptors[poc_idx]["price_lo"] + bin_descriptors[poc_idx]["price_hi"]) / 2.0

    # Value area: expand greedily from POC.
    if total_volume == 0.0:
        # No volume — return degenerate VA at POC.
        return {
            "bins": bin_descriptors,
            "poc": poc_price,
            "vah": bin_descriptors[poc_idx]["price_hi"],
            "val": bin_descriptors[poc_idx]["price_lo"],
            "total_volume": 0.0,
        }

    target = value_area_pct * total_volume
    included = {poc_idx}
    acc = bin_volumes[poc_idx]
    lower = poc_idx
    upper = poc_idx
    while acc < target and (lower > 0 or upper < bins - 1):
        # Look one bin below and one above; pick the higher-volume side.
        below_idx = lower - 1 if lower > 0 else None
        above_idx = upper + 1 if upper < bins - 1 else None
        below_vol = bin_volumes[below_idx] if below_idx is not None else -1.0
        above_vol = bin_volumes[above_idx] if above_idx is not None else -1.0
        if below_vol > above_vol:
            included.add(below_idx)
            acc += below_vol
            lower = below_idx  # type: ignore[assignment]
        elif above_idx is not None:
            included.add(above_idx)
            acc += above_vol
            upper = above_idx
        else:
            break  # nothing more to include

    vah = bin_descriptors[upper]["price_hi"]
    val = bin_descriptors[lower]["price_lo"]

    return {
        "bins": bin_descriptors,
        "poc": poc_price,
        "vah": vah,
        "val": val,
        "total_volume": total_volume,
    }


__all__ = ["volume_profile"]
