"""Entry engine — combines all condition primitives with AND/OR.

The runner calls :func:`evaluate_entry` once per bar with the current
candle, the prior candle (for crossover / breakout / engulfing), and
the indicator-value dicts at both bars. The engine walks the strategy's
:attr:`EntryRules.conditions`, evaluates each via the appropriate
sub-engine, then combines results per :attr:`EntryRules.operator`.

Output is an :class:`EntryDecision` listing the matched and failed
condition descriptions so the AI advisor (Phase 6) can show the user
*why* an entry did or did not fire.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.engines.candle_pattern import detect_candle_pattern
from app.strategy_engine.engines.indicator_eval import evaluate_indicator_condition
from app.strategy_engine.engines.price_condition import evaluate_price_condition
from app.strategy_engine.engines.time_condition import evaluate_time_condition
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import (
    CandleCondition,
    Condition,
    EntryRules,
    IndicatorCondition,
    PriceCondition,
    Side,
    StrategyJSON,
    TimeCondition,
)


class EntryDecision(BaseModel):
    """Result of one entry evaluation.

    ``reasons`` lists the human-readable description of every condition
    that passed; ``failed_conditions`` lists those that did not. Both
    are populated regardless of the final ``should_enter`` value so the
    advisor can explain partial matches under OR semantics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    should_enter: bool
    side: Side | None = None
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    failed_conditions: tuple[str, ...] = Field(default_factory=tuple)


def evaluate_entry(
    strategy: StrategyJSON,
    *,
    current_candle: Candle,
    prior_candle: Candle | None = None,
    indicator_values: Mapping[str, float | None],
    prior_indicator_values: Mapping[str, float | None] | None = None,
) -> EntryDecision:
    """Decide whether to enter on this bar.

    Returns ``EntryDecision`` with ``should_enter=False`` (and ``side=None``)
    whenever the rules don't match — the caller never has to introspect
    further.
    """
    rules: EntryRules = strategy.entry
    matched: list[str] = []
    failed: list[str] = []

    for cond in rules.conditions:
        passed = _evaluate_condition(
            cond,
            current_candle=current_candle,
            prior_candle=prior_candle,
            indicator_values=indicator_values,
            prior_indicator_values=prior_indicator_values,
        )
        label = _describe(cond)
        if passed:
            matched.append(label)
        else:
            failed.append(label)

    # AND — every condition must pass; OR — at least one must.
    fired = (not failed) if rules.operator == "AND" else bool(matched)

    return EntryDecision(
        should_enter=fired,
        side=rules.side if fired else None,
        reasons=tuple(matched),
        failed_conditions=tuple(failed),
    )


# ─── Internals ──────────────────────────────────────────────────────────


def _evaluate_condition(
    cond: Condition,
    *,
    current_candle: Candle,
    prior_candle: Candle | None,
    indicator_values: Mapping[str, float | None],
    prior_indicator_values: Mapping[str, float | None] | None,
) -> bool:
    """Dispatch by condition type to the matching sub-engine."""
    if isinstance(cond, IndicatorCondition):
        return evaluate_indicator_condition(
            cond,
            current_values=indicator_values,
            prior_values=prior_indicator_values,
        )
    if isinstance(cond, CandleCondition):
        return detect_candle_pattern(cond.pattern, current=current_candle, prior=prior_candle)
    if isinstance(cond, TimeCondition):
        return evaluate_time_condition(cond, moment=current_candle.timestamp)
    if isinstance(cond, PriceCondition):
        return evaluate_price_condition(cond, current=current_candle, prior=prior_candle)
    raise TypeError(  # pragma: no cover — discriminated union is exhaustive
        f"Unhandled condition type: {type(cond).__name__}"
    )


def _describe(cond: Condition) -> str:
    """Human-readable summary of a condition for ``reasons``/``failed_conditions``."""
    if isinstance(cond, IndicatorCondition):
        rhs = cond.right if cond.right is not None else cond.value
        return f"indicator: {cond.left} {cond.op.value} {rhs}"
    if isinstance(cond, CandleCondition):
        return f"candle: {cond.pattern.value}"
    if isinstance(cond, TimeCondition):
        end = f"-{cond.end}" if cond.end else ""
        return f"time: {cond.op.value} {cond.value}{end}"
    if isinstance(cond, PriceCondition):
        rhs = "" if cond.value is None else f" {cond.value}"
        return f"price: {cond.op.value}{rhs}"
    # pragma: no cover — discriminated union exhausted; reaching here means
    # someone added a new Condition variant without updating this dispatcher.
    raise TypeError(f"unknown condition type: {type(cond).__name__}")


__all__ = ["EntryDecision", "evaluate_entry"]
