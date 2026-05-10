"""Price-condition evaluator — comparators + breakout primitives.

Comparators (``>``/``<``/``>=``/``<=``) test the **current bar's close**
against ``condition.value`` because close-bar-only signals are the
locked Phase 2 contract (no intra-bar look-ahead). Breakout primitives
(``previous_high_breakout`` / ``previous_low_breakdown``) test the
current bar's high or low against the prior bar's high or low — the
shape of the bar is what matters, not the close.

The schema validator already enforces that comparators carry a
``value`` and that breakouts do not. Edge cases here are limited to the
"prior bar absent" path (first bar of the input window): breakout
primitives quietly return ``False`` so a strategy doesn't fire on bar
zero. Comparators are independent of ``prior``.
"""

from __future__ import annotations

from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import PriceCondition, PriceConditionOp


def evaluate_price_condition(
    condition: PriceCondition,
    *,
    current: Candle,
    prior: Candle | None = None,
) -> bool:
    """Return True iff ``current`` (and ``prior`` for breakouts) satisfies ``condition``."""
    op = condition.op

    if op is PriceConditionOp.PREVIOUS_HIGH_BREAKOUT:
        if prior is None:
            return False
        return current.high > prior.high

    if op is PriceConditionOp.PREVIOUS_LOW_BREAKDOWN:
        if prior is None:
            return False
        return current.low < prior.low

    # Comparators — schema guaranteed value is non-None.
    assert condition.value is not None
    value = condition.value
    close = current.close

    if op is PriceConditionOp.GT:
        return close > value
    if op is PriceConditionOp.LT:
        return close < value
    if op is PriceConditionOp.GTE:
        return close >= value
    if op is PriceConditionOp.LTE:
        return close <= value

    raise ValueError(  # pragma: no cover — unreachable if enum is exhaustive
        f"Unhandled PriceConditionOp: {op!r}"
    )


__all__ = ["evaluate_price_condition"]
