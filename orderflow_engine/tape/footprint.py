"""Footprint stacked-imbalance detector (Module R3).

Operates on a bar's footprint (price_bin -> [buy_vol, sell_vol], where buy_vol is
volume that lifted the ask and sell_vol volume that hit the bid). Diagonal
imbalance is the standard order-flow construction:

  * BUY imbalance at level P:  buy_vol[P]  >= ratio * sell_vol[P - bin]   (diagonal down)
  * SELL imbalance at level P: sell_vol[P] >= ratio * buy_vol[P + bin]    (diagonal up)

A STACKED imbalance is >= ``min_levels`` CONSECUTIVE price bins all showing the
same-side imbalance. This is a SIGNAL-firing detector, so it is INERT when
``ratio <= 0`` (no events) — the uncalibrated default.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StackedImbalance:
    side: str            # "buy" | "sell"
    levels: int          # number of consecutive imbalanced bins
    price_low: float
    price_high: float


def _imbalanced(footprint: dict, price: float, bin_size: float, ratio: float) -> tuple[bool, bool]:
    buy_p, sell_p = footprint.get(price, [0, 0])
    below = round(price - bin_size, 6)
    above = round(price + bin_size, 6)
    sell_below = footprint.get(below, [0, 0])[1]
    buy_above = footprint.get(above, [0, 0])[0]
    buy_imb = buy_p > 0 and buy_p >= ratio * sell_below
    sell_imb = sell_p > 0 and sell_p >= ratio * buy_above
    return buy_imb, sell_imb


def detect_stacked_imbalance(footprint: dict, bin_size: float, ratio: float,
                             min_levels: int) -> list[StackedImbalance]:
    """Return stacked-imbalance runs. INERT (empty) while ratio <= 0."""
    if ratio <= 0 or not footprint or bin_size <= 0:
        return []
    prices = sorted(footprint)
    out: list[StackedImbalance] = []
    for side, idx in (("buy", 0), ("sell", 1)):
        run: list[float] = []
        prev = None
        for p in prices:
            buy_imb, sell_imb = _imbalanced(footprint, p, bin_size, ratio)
            flag = buy_imb if side == "buy" else sell_imb
            contiguous = prev is not None and abs(p - prev - bin_size) < 1e-6
            if flag and (not run or contiguous):
                run.append(p)
            else:
                if len(run) >= min_levels:
                    out.append(StackedImbalance(side, len(run), run[0], run[-1]))
                run = [p] if flag else []
            prev = p
        if len(run) >= min_levels:
            out.append(StackedImbalance(side, len(run), run[0], run[-1]))
    return out
