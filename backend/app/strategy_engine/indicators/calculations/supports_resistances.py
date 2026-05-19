"""Supports & Resistances — fractal-pivot algorithm.

Algorithm A (LOCKED per reference doc):

    Pivot high at bar N: high[N] > high[N-2], high[N-1], high[N+1], high[N+2]
    Pivot low at bar N:  low[N]  < low[N-2],  low[N-1],  low[N+1],  low[N+2]
    (Symmetric 5-bar fractal — lookback=2 each side.)

    Touch detection: a level at price P is "touched" by a later bar j if
        abs(price_j - P) / P <= tolerance_pct / 100.0
    where price_j is high[j] for resistance, low[j] for support.

    Strength = count of subsequent touches (no recency weighting).

    Merge: scan resulting levels; combine any two within tolerance_pct
    by averaging prices and summing strengths. Repeat until stable.

    Truncate: keep at most `max_levels`. When over, drop LOWEST strength
    first (NOT oldest).

Returns: list of dicts:
    {
        "price": float,
        "type":  "support" | "resistance",
        "strength": int,
        "bar_index": int,        # original pivot bar
        "formed_at_index": int,  # bar at which pivot was confirmed (= bar_index + lookback)
    }

This is a snapshot-style indicator: returns the active S/R levels as
of the END of the input series. Not per-bar.

Edge cases:
    * Empty / length-mismatch -> []
    * Series shorter than 2*lookback + 1 -> []
    * No pivots found -> []
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def supports_resistances(
    highs: Sequence[float],
    lows: Sequence[float],
    lookback: int = 2,
    tolerance_pct: float = 0.5,
    max_levels: int = 10,
) -> list[dict[str, Any]]:
    """Fractal-pivot S/R level detection — returns list of Level dicts."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 1:
        raise ValueError(f"lookback must be a positive int; got {lookback!r}.")
    if not isinstance(tolerance_pct, (int, float)) or isinstance(tolerance_pct, bool):
        raise ValueError(f"tolerance_pct must be numeric; got {tolerance_pct!r}.")
    if tolerance_pct <= 0:
        raise ValueError(f"tolerance_pct must be > 0; got {tolerance_pct}.")
    if not isinstance(max_levels, int) or isinstance(max_levels, bool) or max_levels < 1:
        raise ValueError(f"max_levels must be a positive int; got {max_levels!r}.")

    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must be same length; got {n} vs {len(lows)}."
        )
    if n < 2 * lookback + 1:
        return []

    tol = tolerance_pct / 100.0
    h = [float(x) for x in highs]
    l = [float(x) for x in lows]

    # Step 1: identify pivots (confirmed_only -> require lookback bars to the right).
    levels: list[dict[str, Any]] = []
    for N in range(lookback, n - lookback):
        # Pivot high: high[N] strictly greater than all neighbours
        is_high = True
        for k in range(1, lookback + 1):
            if not (h[N] > h[N - k]) or not (h[N] > h[N + k]):
                is_high = False
                break
        if is_high:
            levels.append(
                {
                    "price": h[N],
                    "type": "resistance",
                    "strength": 0,  # touches counted below
                    "bar_index": N,
                    "formed_at_index": N + lookback,
                }
            )

        # Pivot low
        is_low = True
        for k in range(1, lookback + 1):
            if not (l[N] < l[N - k]) or not (l[N] < l[N + k]):
                is_low = False
                break
        if is_low:
            levels.append(
                {
                    "price": l[N],
                    "type": "support",
                    "strength": 0,
                    "bar_index": N,
                    "formed_at_index": N + lookback,
                }
            )

    # Step 2: count subsequent touches for each level.
    for lvl in levels:
        p = lvl["price"]
        start = lvl["formed_at_index"] + 1  # touches START after confirmation
        if p == 0:
            continue
        threshold = abs(p) * tol
        if lvl["type"] == "resistance":
            for j in range(start, n):
                if abs(h[j] - p) <= threshold:
                    lvl["strength"] += 1
        else:  # support
            for j in range(start, n):
                if abs(l[j] - p) <= threshold:
                    lvl["strength"] += 1

    # Step 3: merge nearby levels (same type). Repeat until stable.
    merged_changed = True
    while merged_changed:
        merged_changed = False
        new_levels: list[dict[str, Any]] = []
        used = [False] * len(levels)
        for i in range(len(levels)):
            if used[i]:
                continue
            base = dict(levels[i])
            for j in range(i + 1, len(levels)):
                if used[j]:
                    continue
                if levels[j]["type"] != base["type"]:
                    continue
                if base["price"] == 0:
                    continue
                if (
                    abs(levels[j]["price"] - base["price"]) / abs(base["price"])
                    <= tol
                ):
                    # Merge j into base: mean price, summed strengths,
                    # keep earlier bar_index + earlier formed_at_index.
                    base["price"] = (base["price"] + levels[j]["price"]) / 2.0
                    base["strength"] += levels[j]["strength"]
                    base["bar_index"] = min(base["bar_index"], levels[j]["bar_index"])
                    base["formed_at_index"] = min(
                        base["formed_at_index"], levels[j]["formed_at_index"]
                    )
                    used[j] = True
                    merged_changed = True
            used[i] = True
            new_levels.append(base)
        levels = new_levels

    # Step 4: truncate to max_levels, keeping highest strengths.
    if len(levels) > max_levels:
        levels.sort(key=lambda d: d["strength"], reverse=True)
        levels = levels[:max_levels]

    # Stable ordering for tests: by bar_index ascending.
    levels.sort(key=lambda d: d["bar_index"])
    return levels


__all__ = ["supports_resistances"]
