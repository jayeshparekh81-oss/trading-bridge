"""Exit engine — reports every triggered exit primitive on the bar.

The locked Phase 2 contract: when target + stop-loss + partial all
trigger inside the same bar, **report all of them**. Phase 3's backtest
runner is what assigns priority (conservative-mode picks SL first,
optimistic picks target first, etc.).

Primitives covered (in order returned):

    target               full-quantity exit at target_percent above (BUY)
                         / below (SELL) entry
    stop_loss            full-quantity exit at stop_loss_percent below (BUY)
                         / above (SELL) entry
    trailing_stop        full-quantity exit if the bar's range crosses the
                         position's current trailing_stop_price
    partial              one event per partialExits[] threshold the bar's
                         range crosses (in declared order); the engine does
                         not deduplicate against position.partial_exits_done
                         — that's the runner's job
    indicator            one event per indicator-driven exit condition
                         (uses the same evaluator as entry)
    reverse_signal       caller passes ``reverse_signal_fired=True`` when
                         a fresh entry on the opposite side fires
    time                 exit when current bar's time matches an exit time
                         condition (Phase 2 stub — no time-conditioned
                         exits in the schema yet, see Phase 9 expansion)
    square_off           exit at the configured square-off time

The engine pulls the bar's high/low to decide whether an intra-bar
target / stop / trail level was crossed. ``current.close`` alone isn't
enough — a target hit and reversed inside one bar still counts.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.engines.indicator_eval import evaluate_indicator_condition
from app.strategy_engine.engines.position import PositionState
from app.strategy_engine.engines.time_condition import evaluate_time_condition
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import (
    ExitRules,
    IndicatorCondition,
    Side,
    TimeCondition,
    TimeConditionOp,
)


class ExitType(StrEnum):
    TARGET = "target"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    PARTIAL = "partial"
    INDICATOR = "indicator"
    REVERSE_SIGNAL = "reverse_signal"
    TIME = "time"
    SQUARE_OFF = "square_off"


class ExitEvent(BaseModel):
    """One exit primitive that fired on this bar.

    ``qty_percent`` is 100 for full exits and < 100 for partials.
    ``price`` is the level at which the exit would fill — engines pass
    candidates (``target_price``, ``stop_loss_price`` etc.); the runner
    decides which actually fills given fill semantics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    exit_type: ExitType
    qty_percent: float = Field(..., gt=0, le=100)
    price: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=256)


def evaluate_exit(
    *,
    position: PositionState,
    current_candle: Candle,
    prior_candle: Candle | None,
    exit_rules: ExitRules,
    indicator_values: Mapping[str, float | None],
    prior_indicator_values: Mapping[str, float | None] | None = None,
    reverse_signal_fired: bool = False,
) -> list[ExitEvent]:
    """Walk every exit primitive and return one ExitEvent per fired trigger.

    Returns an empty list when nothing fires. Order:
    target -> stop_loss -> trailing -> partials -> indicator -> reverse ->
    time/square-off. The runner's priority logic chooses among the
    returned events; this engine only reports.
    """
    if not position.is_open:
        return []

    events: list[ExitEvent] = []

    # ─── Fixed target ───────────────────────────────────────────────────
    if exit_rules.target_percent is not None:
        target_price = _level_above(position, exit_rules.target_percent)
        if _bar_crossed_long(position.side, current_candle, target_price):
            events.append(
                ExitEvent(
                    exit_type=ExitType.TARGET,
                    qty_percent=100.0,
                    price=target_price,
                    reason=f"target {exit_rules.target_percent}% from entry",
                )
            )

    # ─── Fixed stop-loss ───────────────────────────────────────────────
    if exit_rules.stop_loss_percent is not None:
        sl_price = _level_below(position, exit_rules.stop_loss_percent)
        if _bar_crossed_short(position.side, current_candle, sl_price):
            events.append(
                ExitEvent(
                    exit_type=ExitType.STOP_LOSS,
                    qty_percent=100.0,
                    price=sl_price,
                    reason=f"stop loss {exit_rules.stop_loss_percent}% from entry",
                )
            )

    # ─── Trailing stop ─────────────────────────────────────────────────
    # We don't recompute the trail here — the position state already has
    # the latest trail (updated on each prior candle close per locked
    # decision). We just check whether THIS bar's range crosses it.
    if exit_rules.trailing_stop_percent is not None and position.trailing_stop_price is not None:
        trail = position.trailing_stop_price
        if _bar_crossed_short(position.side, current_candle, trail):
            events.append(
                ExitEvent(
                    exit_type=ExitType.TRAILING_STOP,
                    qty_percent=100.0,
                    price=trail,
                    reason=(
                        f"trailing stop ({exit_rules.trailing_stop_percent}%) "
                        f"crossed at {trail:.4f}"
                    ),
                )
            )

    # ─── Partial exits ─────────────────────────────────────────────────
    # One event per declared partial whose target-from-entry the bar
    # crosses. Deduplication against partial_exits_done belongs to the
    # runner — engine just reports.
    for idx, partial in enumerate(exit_rules.partial_exits, start=1):
        partial_price = _level_above(position, partial.target_percent)
        if _bar_crossed_long(position.side, current_candle, partial_price):
            events.append(
                ExitEvent(
                    exit_type=ExitType.PARTIAL,
                    qty_percent=partial.qty_percent,
                    price=partial_price,
                    reason=(
                        f"partial #{idx}: {partial.qty_percent}% off at "
                        f"{partial.target_percent}% target"
                    ),
                )
            )

    # ─── Indicator-driven exits ────────────────────────────────────────
    for cond in exit_rules.indicator_exits:
        if isinstance(cond, IndicatorCondition) and evaluate_indicator_condition(
            cond,
            current_values=indicator_values,
            prior_values=prior_indicator_values,
        ):
            events.append(
                ExitEvent(
                    exit_type=ExitType.INDICATOR,
                    qty_percent=100.0,
                    price=current_candle.close,
                    reason=f"indicator exit: {cond.left} {cond.op.value} "
                    + (cond.right or str(cond.value)),
                )
            )
        # Non-indicator conditions inside indicator_exits are accepted by
        # the schema but ignored by the engine in Phase 2 — the schema
        # validator already lets a strategy author put them there for
        # future expansion. Phase 9 will widen this.

    # ─── Reverse-signal exit ───────────────────────────────────────────
    if exit_rules.reverse_signal_exit and reverse_signal_fired:
        events.append(
            ExitEvent(
                exit_type=ExitType.REVERSE_SIGNAL,
                qty_percent=100.0,
                price=current_candle.close,
                reason="reverse-direction signal fired on this bar",
            )
        )

    # ─── Square-off time ───────────────────────────────────────────────
    if exit_rules.square_off_time is not None:
        cond = TimeCondition(
            type="time",
            op=TimeConditionOp.EXACT,
            value=exit_rules.square_off_time,
        )
        # Square-off fires AT or AFTER the configured time so a bar
        # whose timestamp is one tick past the cutoff still triggers.
        after_cond = TimeCondition(
            type="time",
            op=TimeConditionOp.AFTER,
            value=exit_rules.square_off_time,
        )
        if evaluate_time_condition(
            cond, moment=current_candle.timestamp
        ) or evaluate_time_condition(after_cond, moment=current_candle.timestamp):
            events.append(
                ExitEvent(
                    exit_type=ExitType.SQUARE_OFF,
                    qty_percent=100.0,
                    price=current_candle.close,
                    reason=f"square-off at {exit_rules.square_off_time}",
                )
            )

    return events


# ─── Helpers ────────────────────────────────────────────────────────────


def _level_above(position: PositionState, percent: float) -> float:
    """Compute a price ``percent``% in the position's favour above (BUY) /
    below (SELL) the entry price.
    """
    factor = percent / 100.0
    if position.side is Side.BUY:
        return position.entry_price * (1.0 + factor)
    return position.entry_price * (1.0 - factor)


def _level_below(position: PositionState, percent: float) -> float:
    """Compute a price ``percent``% AGAINST the position (BUY: below, SELL: above)."""
    factor = percent / 100.0
    if position.side is Side.BUY:
        return position.entry_price * (1.0 - factor)
    return position.entry_price * (1.0 + factor)


def _bar_crossed_long(side: Side, candle: Candle, level: float) -> bool:
    """Did the bar reach ``level`` in the position's favour?

    BUY  position: level ABOVE entry; "reached" = candle.high >= level.
    SELL position: level BELOW entry; "reached" = candle.low <= level.
    """
    if side is Side.BUY:
        return candle.high >= level
    return candle.low <= level


def _bar_crossed_short(side: Side, candle: Candle, level: float) -> bool:
    """Did the bar reach ``level`` AGAINST the position?

    BUY  position: level BELOW entry; "reached" = candle.low <= level.
    SELL position: level ABOVE entry; "reached" = candle.high >= level.
    """
    if side is Side.BUY:
        return candle.low <= level
    return candle.high >= level


__all__ = ["ExitEvent", "ExitType", "evaluate_exit"]
