"""Indicator-condition evaluator.

Two operand patterns:

    indicator vs indicator     ``left`` and ``right`` are both indicator ids.
                               Reads both from ``current_values`` (and
                               ``prior_values`` for crossover/crossunder).
    indicator vs constant      ``left`` is an indicator id, ``value`` is a
                               float. Standard comparators only; crossover
                               against a constant is intentionally not
                               supported (schema validator rejects it).

Crossover semantics (locked Phase 2 decision):
    The condition fires on the bar where the relationship flips. For
    ``crossover``: ``prior(left) <= prior(right)`` AND
    ``current(left) > current(right)``. Crossunder is the mirror image.
    A condition can only evaluate to ``True`` when both prior values are
    available; the first bar of input always reports False.

Missing values:
    Indicator series have ``None`` warm-up positions (Phase 1 contract).
    A condition referencing an indicator whose value is ``None`` at the
    current bar evaluates to ``False`` — there is nothing to compare yet.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.strategy_engine.schema.strategy import (
    IndicatorCondition,
    IndicatorConditionOp,
)


def evaluate_indicator_condition(
    condition: IndicatorCondition,
    *,
    current_values: Mapping[str, float | None],
    prior_values: Mapping[str, float | None] | None = None,
) -> bool:
    """Return True iff the indicator-on-indicator / -on-value comparison holds."""
    op = condition.op
    left_now = current_values.get(condition.left)
    if left_now is None:
        return False

    if op in (IndicatorConditionOp.CROSSOVER, IndicatorConditionOp.CROSSUNDER):
        return _evaluate_cross(
            condition=condition,
            current_values=current_values,
            prior_values=prior_values,
        )

    # Comparator — RHS may be another indicator id or a constant.
    rhs_now = _resolve_rhs(condition, current_values)
    if rhs_now is None:
        return False
    return _compare(op, left_now, rhs_now)


def _evaluate_cross(
    *,
    condition: IndicatorCondition,
    current_values: Mapping[str, float | None],
    prior_values: Mapping[str, float | None] | None,
) -> bool:
    """Crossover / crossunder require both prior + current values defined."""
    if prior_values is None or condition.right is None:
        return False
    left_prev = prior_values.get(condition.left)
    right_prev = prior_values.get(condition.right)
    left_now = current_values.get(condition.left)
    right_now = current_values.get(condition.right)
    if any(v is None for v in (left_prev, right_prev, left_now, right_now)):
        return False

    # mypy: the None-check above narrows; assert silences it without runtime cost.
    assert left_prev is not None
    assert right_prev is not None
    assert left_now is not None
    assert right_now is not None

    if condition.op is IndicatorConditionOp.CROSSOVER:
        return left_prev <= right_prev and left_now > right_now
    # CROSSUNDER
    return left_prev >= right_prev and left_now < right_now


def _resolve_rhs(
    condition: IndicatorCondition,
    current_values: Mapping[str, float | None],
) -> float | None:
    """RHS is either ``current_values[right]`` or the constant ``value``."""
    if condition.right is not None:
        return current_values.get(condition.right)
    # The schema's xor validator guarantees value is not None when right is None.
    return condition.value


def _compare(op: IndicatorConditionOp, left: float, right: float) -> bool:
    if op is IndicatorConditionOp.GT:
        return left > right
    if op is IndicatorConditionOp.LT:
        return left < right
    if op is IndicatorConditionOp.GTE:
        return left >= right
    if op is IndicatorConditionOp.LTE:
        return left <= right
    if op is IndicatorConditionOp.EQ:
        return left == right
    if op is IndicatorConditionOp.NEQ:
        return left != right
    raise ValueError(  # pragma: no cover — caller handles cross ops separately
        f"_compare called with non-comparator op {op!r}."
    )


__all__ = ["evaluate_indicator_condition"]
