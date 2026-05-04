"""Time-of-day condition evaluator.

The strategy schema's :class:`TimeCondition` carries an ``HH:MM`` value
(and an optional ``end`` for ``BETWEEN``). At evaluation time the engine
compares against the *time-of-day* component of the bar's timestamp;
date and timezone are the caller's concern. The runner is expected to
pass a tz-aware datetime in the strategy's working timezone (IST for
Indian markets).

``BETWEEN`` semantics are inclusive on both endpoints, matching how
intraday session windows are usually specified ("active 09:15-15:25").
Same-time start/end is treated as a single-minute window. Wrap-around
windows (start > end, e.g. 22:00-02:00) are NOT supported in Phase 2 —
F&O markets we serve are intraday-only — and raise ``ValueError`` so
the bug is loud rather than silent.
"""

from __future__ import annotations

from datetime import datetime, time

from app.strategy_engine.schema.strategy import TimeCondition, TimeConditionOp


def evaluate_time_condition(
    condition: TimeCondition,
    *,
    moment: datetime,
) -> bool:
    """Return True iff ``moment``'s time-of-day satisfies ``condition``."""
    target = _parse_hhmm(condition.value)
    bar = moment.time()

    if condition.op is TimeConditionOp.EXACT:
        # HH:MM granularity — equal hour AND minute, ignore seconds/microseconds.
        return bar.hour == target.hour and bar.minute == target.minute

    if condition.op is TimeConditionOp.AFTER:
        return bar > target

    if condition.op is TimeConditionOp.BEFORE:
        return bar < target

    if condition.op is TimeConditionOp.BETWEEN:
        if condition.end is None:  # pragma: no cover — schema validator catches this
            raise ValueError("BETWEEN requires 'end'.")
        end = _parse_hhmm(condition.end)
        if target > end:
            raise ValueError(
                f"BETWEEN does not support wrap-around windows; "
                f"got start={condition.value} > end={condition.end}."
            )
        return target <= bar <= end

    raise ValueError(  # pragma: no cover — unreachable if enum is exhaustive
        f"Unhandled TimeConditionOp: {condition.op!r}"
    )


def _parse_hhmm(value: str) -> time:
    """``HH:MM`` -> :class:`datetime.time`. Schema already validated the format."""
    hours_str, minutes_str = value.split(":", 1)
    return time(hour=int(hours_str), minute=int(minutes_str))


__all__ = ["evaluate_time_condition"]
