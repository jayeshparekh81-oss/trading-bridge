"""F&O Lot Size ATR - ATR scaled to one F&O contract's rupee risk.

Multiplies the ATR (in price units) by the F&O lot size to give the
per-contract risk in rupees. Indian F&O traders size positions in
multiples of the lot, so ATR-per-contract is the natural unit for
position-sizing maths.

Default ``assumed_lot_size = 50`` (e.g. NIFTY index futures lot was
50 prior to the November 2024 SEBI lot-size revision). Operators
should override per symbol from the latest exchange circular.

Output is in rupees; output length matches input.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``atr_period < 2`` or ``assumed_lot_size < 1`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr


def fno_lot_size_atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    atr_period: int = 14,
    assumed_lot_size: int = 50,
) -> list[float | None]:
    """ATR * assumed_lot_size, in rupees per contract."""
    if not isinstance(atr_period, int) or isinstance(atr_period, bool) or atr_period < 2:
        raise ValueError(f"atr_period must be int >= 2; got {atr_period!r}.")
    if (
        not isinstance(assumed_lot_size, int)
        or isinstance(assumed_lot_size, bool)
        or assumed_lot_size < 1
    ):
        raise ValueError(
            f"assumed_lot_size must be a positive int; got {assumed_lot_size!r}."
        )
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs/lows/closes must match in length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0:
        return []
    atr_line = atr(highs, lows, closes, atr_period)
    if not atr_line:
        return [None] * n
    out: list[float | None] = [None] * n
    for i, v in enumerate(atr_line):
        if v is None:
            continue
        out[i] = v * assumed_lot_size
    return out


__all__ = ["fno_lot_size_atr"]
