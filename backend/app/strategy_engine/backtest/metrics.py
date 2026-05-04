"""Pure metric functions for the backtest output.

Locked Phase 3 conventions (per the approval message):

    profit_factor   sum(wins) / sum(abs(losses))
                    math.inf when there are wins but no losses
                    0.0 when there are no trades at all (so the field is
                    always a float — callers don't have to guard NaN)

    expectancy      avg_win * win_rate - avg_loss * (1 - win_rate)
                    where avg_loss is the *magnitude* of the average
                    loss (positive number)

    max_drawdown    peak-to-trough on the equity curve, expressed as a
                    POSITIVE percentage of the peak (e.g. 0.10 == 10 % DD).
                    A monotonically rising curve has 0.0 drawdown.

All inputs are plain ``Sequence[float]`` so the metrics module is fully
decoupled from the rest of the backtest stack — Phase 4 reliability can
import these directly when computing trust scores.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def total_pnl(pnls: Sequence[float]) -> float:
    """Sum of trade P&Ls. Empty -> 0.0."""
    return float(sum(pnls)) if pnls else 0.0


def win_rate(pnls: Sequence[float]) -> float:
    """Fraction of trades with strictly positive P&L. Empty -> 0.0.

    Returned as a fraction in [0, 1]; callers multiply by 100 to display.
    Zero-P&L trades are counted as neither win nor loss for the rate.
    """
    if not pnls:
        return 0.0
    wins = sum(1 for p in pnls if p > 0)
    return wins / len(pnls)


def loss_rate(pnls: Sequence[float]) -> float:
    """Fraction of trades with strictly negative P&L. Empty -> 0.0."""
    if not pnls:
        return 0.0
    losses = sum(1 for p in pnls if p < 0)
    return losses / len(pnls)


def average_win(pnls: Sequence[float]) -> float:
    """Mean of strictly positive P&Ls. No wins -> 0.0."""
    wins = [p for p in pnls if p > 0]
    return float(sum(wins) / len(wins)) if wins else 0.0


def average_loss(pnls: Sequence[float]) -> float:
    """Mean MAGNITUDE of strictly negative P&Ls (positive number). No losses -> 0.0.

    Returning the magnitude (not the signed value) keeps every consumer
    of this number on the same page — expectancy multiplies it by
    ``(1 - win_rate)`` and subtracts.
    """
    losses = [-p for p in pnls if p < 0]
    return float(sum(losses) / len(losses)) if losses else 0.0


def largest_win(pnls: Sequence[float]) -> float:
    """Largest positive P&L. No wins -> 0.0."""
    wins = [p for p in pnls if p > 0]
    return float(max(wins)) if wins else 0.0


def largest_loss(pnls: Sequence[float]) -> float:
    """Most negative P&L (returned as a NEGATIVE number). No losses -> 0.0."""
    losses = [p for p in pnls if p < 0]
    return float(min(losses)) if losses else 0.0


def profit_factor(pnls: Sequence[float]) -> float:
    """``sum(wins) / sum(|losses|)``. See module docstring for edge cases."""
    if not pnls:
        return 0.0
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    if gross_loss == 0:
        # Wins-only deck: math.inf is a stable fixed value (math.inf == math.inf).
        return math.inf if gross_win > 0 else 0.0
    return float(gross_win / gross_loss)


def expectancy(pnls: Sequence[float]) -> float:
    """``avg_win * win_rate - avg_loss * (1 - win_rate)``. Empty -> 0.0.

    ``avg_loss`` here is the magnitude returned by :func:`average_loss`,
    so the subtraction sign already reflects "losses subtract".
    """
    if not pnls:
        return 0.0
    wr = win_rate(pnls)
    aw = average_win(pnls)
    al = average_loss(pnls)
    return aw * wr - al * (1.0 - wr)


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Peak-to-trough drawdown as a positive fraction of the peak.

    Walks the curve once, tracking the running maximum. At each point::

        dd = (peak - equity) / peak    if peak > 0 else 0
        max_dd = max(max_dd, dd)

    Empty curve or a curve that never dips returns ``0.0``. Negative
    equity is tolerated (the curve can go below zero on a blow-up); we
    use ``peak`` as the denominator so the metric stays interpretable.
    """
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > worst:
                worst = dd
    return float(worst)


def total_return_percent(initial_capital: float, final_equity: float) -> float:
    """``(final - initial) / initial * 100``. ``initial == 0`` -> 0.0."""
    if initial_capital == 0:
        return 0.0
    return float((final_equity - initial_capital) / initial_capital * 100.0)


__all__ = [
    "average_loss",
    "average_win",
    "expectancy",
    "largest_loss",
    "largest_win",
    "loss_rate",
    "max_drawdown",
    "profit_factor",
    "total_pnl",
    "total_return_percent",
    "win_rate",
]
