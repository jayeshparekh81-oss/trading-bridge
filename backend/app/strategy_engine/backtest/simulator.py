"""Candle-by-candle simulator — the heart of the deterministic backtest.

The lifecycle on each bar ``i >= 1`` is::

    1. If a queued entry is pending, FILL IT at candle[i].open
       (entry-on-next-bar-open per the master prompt's locked rule).
       Apply slippage + entry cost.
    2. If position is open, evaluate exits using the bar's high/low
       (intra-bar triggers) and the position state from end of bar i-1
       (so trail stops use yesterday's value, no lookahead). Multiple
       triggers in the same bar are reported by the engine; the
       simulator resolves priority via the configured AmbiguityMode.
    3. Update position watermarks + trailing stop on candle CLOSE
       (locked Phase 2 decision: trail updates after close, not intra-bar).
    4. Compute runtime risk stats from completed trades + today's
       state, run :func:`evaluate_risk`. If BLOCKED, skip step 5.
    5. Evaluate entry on candle CLOSE. If signalled and position is
       flat, queue the entry to fill at candle[i+1].open.
    6. Mark equity to market for the equity curve.

Edge cases (locked):
    * First candle (``i=0``) is never an entry bar — needs prior candle
      for crossovers; equity = initial_capital.
    * If a position is still open after the last candle, force-close at
      the last candle's close with ``exit_reason="backtest_end"``.
    * Costs apply on entry AND exit (round-trip).
    * Determinism: identical input -> identical output. The simulator
      never reads from any source except its arguments.

The simulator does NOT call any LLM, network, or DB. Every metric in
the output comes from this function or :mod:`metrics`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from app.strategy_engine.backtest.costs import (
    CostSettings,
    adjust_for_slippage,
    leg_cost,
)
from app.strategy_engine.backtest.indicator_runner import values_at
from app.strategy_engine.backtest.trade_log import EquityPoint, Trade
from app.strategy_engine.engines.entry import EntryDecision, evaluate_entry
from app.strategy_engine.engines.exit import ExitEvent, ExitType, evaluate_exit
from app.strategy_engine.engines.position import (
    PositionState,
    apply_partial_exit,
    close_position,
    open_position,
    update_on_candle,
)
from app.strategy_engine.engines.risk import (
    RiskRuntimeStats,
    RiskSeverity,
    evaluate_risk,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import Side, StrategyJSON

# ─── Ambiguity-mode priority resolution ─────────────────────────────────
#
# When target + stop_loss BOTH trigger inside one bar, intra-bar tick
# order is unknowable from OHLC alone. The locked Phase 3 contract:
#
#   conservative          -> SL fills first (worst plausible outcome)
#   optimistic            -> target fills first (best plausible outcome)
#   accurate_placeholder  -> falls back to conservative until tick data
#                            integration lands (Phase 8/9).
#
# Partials and indicator/reverse/square-off exits don't conflict with
# the target/SL race — they fire independently when their level is
# crossed. The simulator dedupes against position.partial_exits_done so
# the same partial doesn't fire on a later bar.


@dataclass
class _SimResult:
    """Internal aggregate the simulator returns; runner re-packages into
    the Pydantic :class:`BacktestResult`.
    """

    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _DailyStats:
    """Running daily risk accumulators; reset when the candle's date changes."""

    current_day: date | None = None
    trades_today: int = 0
    daily_pnl: float = 0.0


def simulate(
    *,
    candles: Sequence[Candle],
    strategy: StrategyJSON,
    indicator_series: dict[str, list[float | None]],
    initial_capital: float,
    quantity: float,
    cost_settings: CostSettings,
    ambiguity_mode: str,
) -> _SimResult:
    """Run the deterministic candle-by-candle simulation.

    Args:
        candles: Sorted, validated bars. Caller (runner) supplies via
            :func:`normalize_candles`.
        strategy: Validated :class:`StrategyJSON`.
        indicator_series: Pre-computed series keyed by indicator id.
            Same length as ``candles``; ``None`` denotes warm-up.
        initial_capital: Starting equity for the equity curve.
        quantity: Position size for each entry (Phase 3 ships fixed
            qty; Phase 4+ may add dynamic sizing).
        cost_settings: Per-leg cost configuration.
        ambiguity_mode: ``"conservative" | "optimistic" | "accurate_placeholder"``.

    Returns:
        :class:`_SimResult` — runner re-packages with metrics.
    """
    result = _SimResult()
    if cost_settings.spread_percent > 0:
        result.warnings.append(
            "spread_percent is configured but Phase 3 does not apply it; "
            "see costs module docstring."
        )

    capital = float(initial_capital)
    realised_pnl = 0.0
    completed_trade_pnls: list[float] = []
    consecutive_loss_streak = 0
    daily = _DailyStats()

    position: PositionState | None = None
    pending_entry: _PendingEntry | None = None
    # Reasons captured at the moment of entry — kept as a parallel local
    # to ``position`` so that even after ``update_on_candle`` returns a
    # new (frozen) PositionState with a different ``id()``, the runner
    # still has the original reasons for the eventual Trade row.
    open_reasons: tuple[str, ...] = ()

    # First bar: only used as "prior" for bar 1; equity seeded.
    result.equity_curve.append(
        EquityPoint(timestamp=candles[0].timestamp, equity=capital + realised_pnl)
    )

    for i in range(1, len(candles)):
        bar = candles[i]
        prior_bar = candles[i - 1]
        _roll_daily_stats(daily, bar.timestamp.date())

        # ── 1. Fill any queued entry at this bar's OPEN ─────────────────
        if pending_entry is not None and position is None:
            position = _fill_pending_entry(
                pending_entry,
                bar=bar,
                quantity=quantity,
                cost_settings=cost_settings,
                capital_ledger=_CapitalLedger(),
            )
            open_reasons = pending_entry.decision.reasons
            # Cost is paid as a deduction from realised_pnl; track on the
            # ledger we constructed inline so the deduction is visible to
            # the open trade's eventual P&L.
            entry_cost = leg_cost(
                price=position.entry_price,
                quantity=position.quantity,
                settings=cost_settings,
            )
            realised_pnl -= entry_cost
            daily.trades_today += 1
            pending_entry = None

        # ── 2. Evaluate exits using the position from end-of-prior-bar ─
        if position is not None:
            current_indicator_values = values_at(indicator_series, i)
            prior_indicator_values = values_at(indicator_series, i - 1)
            events = evaluate_exit(
                position=position,
                current_candle=bar,
                prior_candle=prior_bar,
                exit_rules=strategy.exit,
                indicator_values=current_indicator_values,
                prior_indicator_values=prior_indicator_values,
            )
            if events:
                position, closed_trades, exit_realised = _apply_exit_events(
                    position=position,
                    events=events,
                    bar=bar,
                    pending_entry_reasons=open_reasons,
                    ambiguity_mode=ambiguity_mode,
                    cost_settings=cost_settings,
                    quantity=quantity,
                )
                if position is None:
                    open_reasons = ()
                for tr in closed_trades:
                    result.trades.append(tr)
                    completed_trade_pnls.append(tr.pnl)
                    daily.daily_pnl += tr.pnl
                    if tr.pnl < 0:
                        consecutive_loss_streak += 1
                    elif tr.pnl > 0:
                        consecutive_loss_streak = 0
                realised_pnl += exit_realised

        # ── 3. Update position state on candle close ────────────────────
        if position is not None:
            position = update_on_candle(
                position,
                bar,
                trailing_stop_percent=strategy.exit.trailing_stop_percent,
            )

        # ── 4. Runtime-risk evaluation ──────────────────────────────────
        stats = RiskRuntimeStats(
            daily_pnl_percent=(
                (daily.daily_pnl / initial_capital) * 100.0 if initial_capital > 0 else None
            ),
            trades_today=daily.trades_today,
            consecutive_loss_streak=consecutive_loss_streak,
        )
        risk = evaluate_risk(strategy, stats=stats)
        risk_blocked = risk.severity is RiskSeverity.BLOCK or not risk.allowed

        # ── 5. Entry evaluation on close ─────────────────────────────────
        if position is None and not risk_blocked:
            decision = evaluate_entry(
                strategy,
                current_candle=bar,
                prior_candle=prior_bar,
                indicator_values=values_at(indicator_series, i),
                prior_indicator_values=values_at(indicator_series, i - 1),
            )
            if decision.should_enter:
                pending_entry = _PendingEntry(decision=decision, signalled_at=bar.timestamp)

        # ── 6. Equity mark-to-market on bar close ───────────────────────
        unrealised = _unrealised_pnl(position, bar.close) if position else 0.0
        result.equity_curve.append(
            EquityPoint(
                timestamp=bar.timestamp,
                equity=capital + realised_pnl + unrealised,
            )
        )

    # ── Force-close any open position at backtest end ───────────────────
    if position is not None:
        last_bar = candles[-1]
        exit_price = adjust_for_slippage(
            price=last_bar.close,
            side=position.side,
            leg="exit",
            settings=cost_settings,
        )
        exit_cost = leg_cost(
            price=exit_price,
            quantity=position.remaining_quantity,
            settings=cost_settings,
        )
        pnl = (
            _trade_pnl(
                side=position.side,
                entry_price=position.entry_price,
                exit_price=exit_price,
                quantity=position.remaining_quantity,
            )
            - exit_cost
        )
        realised_pnl += pnl - 0  # exit cost already inside `pnl`
        result.trades.append(
            Trade(
                entry_time=position.entry_time,
                exit_time=last_bar.timestamp,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=exit_price,
                quantity=position.remaining_quantity,
                pnl=pnl,
                exit_reason="backtest_end",
                entry_reasons=open_reasons,
            )
        )
        # Re-anchor the last equity point so the curve reflects the
        # forced-exit P&L (the loop above had a stale unrealised value).
        result.equity_curve[-1] = EquityPoint(
            timestamp=last_bar.timestamp,
            equity=capital + realised_pnl,
        )
        position = None

    return result


# ─── Pending-entry + exit-resolution helpers ────────────────────────────


@dataclass
class _PendingEntry:
    """Entry that fires on next bar's open. Captured at signal time so
    the trade row can carry the entry reasons even after the position
    has closed.
    """

    decision: EntryDecision
    signalled_at: datetime


@dataclass
class _CapitalLedger:
    """Reserved for Phase 4 dynamic-sizing. Phase 3 uses fixed qty."""


def _fill_pending_entry(
    pending: _PendingEntry,
    *,
    bar: Candle,
    quantity: float,
    cost_settings: CostSettings,
    capital_ledger: _CapitalLedger,
) -> PositionState:
    """Materialise the queued entry at this bar's open price + slippage.

    Entry reasons are NOT keyed off the returned :class:`PositionState`'s
    ``id()`` — the simulator keeps them in a parallel ``open_reasons``
    local instead. ``update_on_candle`` returns a new frozen copy each
    bar with a fresh id, so id-keying would silently break (and id-reuse
    across runs would silently leak stale reasons).
    """
    side = pending.decision.side
    if side is None:  # pragma: no cover — entry decision invariant
        raise ValueError("Pending entry has no side; entry-engine contract violated.")
    fill_price = adjust_for_slippage(price=bar.open, side=side, leg="entry", settings=cost_settings)
    return open_position(
        side=side,
        entry_price=fill_price,
        quantity=quantity,
        entry_time=bar.timestamp,
    )


# ─── Exit-event resolution ──────────────────────────────────────────────


def _apply_exit_events(
    *,
    position: PositionState,
    events: list[ExitEvent],
    bar: Candle,
    pending_entry_reasons: tuple[str, ...],
    ambiguity_mode: str,
    cost_settings: CostSettings,
    quantity: float,
) -> tuple[PositionState | None, list[Trade], float]:
    """Apply the exit events for one bar in priority order.

    Returns ``(new_position_or_None, closed_trades, realised_pnl_delta)``.
    """
    # Local is widened to ``PositionState | None`` so we can collapse to
    # None at end-of-function when the position fully closes.
    pos: PositionState | None = position
    realised: float = 0.0
    closed: list[Trade] = []

    sorted_events = _prioritise_events(events, ambiguity_mode)

    for event in sorted_events:
        if pos is None or not pos.is_open:
            break

        # Slippage on the trigger price. PARTIAL/full exits use slipped
        # fill so the simulator's friction model is consistent across
        # primitives.
        fill_price = adjust_for_slippage(
            price=event.price,
            side=pos.side,
            leg="exit",
            settings=cost_settings,
        )

        if event.exit_type is ExitType.PARTIAL:
            # Skip if this partial level was already booked on a prior
            # bar — engine just *reports* triggers, runner dedupes.
            partial_idx = _partial_index_for_event(event, pos, quantity)
            if partial_idx is not None:
                # Already done; keep walking events.
                continue

            qty_to_close = quantity * (event.qty_percent / 100.0)
            cost = leg_cost(
                price=fill_price,
                quantity=qty_to_close,
                settings=cost_settings,
            )
            pnl = (
                _trade_pnl(
                    side=pos.side,
                    entry_price=pos.entry_price,
                    exit_price=fill_price,
                    quantity=qty_to_close,
                )
                - cost
            )
            realised += pnl

            pos, _ = apply_partial_exit(
                pos,
                qty_percent=event.qty_percent,
                price=fill_price,
                timestamp=bar.timestamp,
                reason=event.reason,
            )
            # Emit a Trade row per partial leg so the audit trail shows
            # every booked exit. Phase 9 may add a parent/child link
            # between the original entry and its partial children.
            closed.append(
                Trade(
                    entry_time=pos.entry_time,
                    exit_time=bar.timestamp,
                    side=pos.side,
                    entry_price=pos.entry_price,
                    exit_price=fill_price,
                    quantity=qty_to_close,
                    pnl=pnl,
                    exit_reason=event.reason,
                    entry_reasons=pending_entry_reasons,
                )
            )
            continue

        # Full-quantity exit (target / stop_loss / trailing_stop /
        # indicator / reverse_signal / square_off).
        qty_to_close = pos.remaining_quantity
        cost = leg_cost(
            price=fill_price,
            quantity=qty_to_close,
            settings=cost_settings,
        )
        pnl = (
            _trade_pnl(
                side=pos.side,
                entry_price=pos.entry_price,
                exit_price=fill_price,
                quantity=qty_to_close,
            )
            - cost
        )
        realised += pnl
        closed.append(
            Trade(
                entry_time=pos.entry_time,
                exit_time=bar.timestamp,
                side=pos.side,
                entry_price=pos.entry_price,
                exit_price=fill_price,
                quantity=qty_to_close,
                pnl=pnl,
                exit_reason=event.exit_type.value,
                entry_reasons=pending_entry_reasons,
            )
        )
        pos = close_position(pos)

    # Collapse a closed-but-not-None state to None so the simulator's
    # main loop can fire a fresh entry on the same bar's close.
    if pos is not None and not pos.is_open:
        pos = None

    return pos, closed, realised


def _partial_index_for_event(
    event: ExitEvent, position: PositionState, _quantity: float
) -> int | None:
    """Return the index of the prior partial-exit record matching ``event``,
    or ``None`` if this partial threshold has not yet been booked.

    Match heuristic: same ``qty_percent`` already on
    ``position.partial_exits_done``. The exit engine emits one event per
    declared partial threshold; declared partials are unique per
    qty_percent in the Phase 1 schema (no duplicates in the list).
    """
    for idx, rec in enumerate(position.partial_exits_done):
        if math.isclose(rec.qty_percent, event.qty_percent, rel_tol=1e-9):
            return idx
    return None


def _prioritise_events(events: list[ExitEvent], mode: str) -> list[ExitEvent]:
    """Return events in apply order per the ambiguity mode.

    Conservative / accurate_placeholder: stop_loss > trailing_stop >
    partials (in declared order) > target > indicator/reverse/square_off.
    Optimistic: target > partials > trailing_stop > stop_loss >
    indicator/reverse/square_off — i.e. let the favourable hits fire
    before the adverse ones.
    """
    rank_map = (
        _OPTIMISTIC_RANK
        if mode == "optimistic"
        else _CONSERVATIVE_RANK  # both 'conservative' and 'accurate_placeholder' fall here
    )
    return sorted(events, key=lambda e: rank_map.get(e.exit_type, 99))


_CONSERVATIVE_RANK: dict[ExitType, int] = {
    ExitType.STOP_LOSS: 0,
    ExitType.TRAILING_STOP: 1,
    ExitType.PARTIAL: 2,
    ExitType.TARGET: 3,
    ExitType.INDICATOR: 4,
    ExitType.REVERSE_SIGNAL: 5,
    ExitType.SQUARE_OFF: 6,
    ExitType.TIME: 7,
}

_OPTIMISTIC_RANK: dict[ExitType, int] = {
    ExitType.TARGET: 0,
    ExitType.PARTIAL: 1,
    ExitType.TRAILING_STOP: 2,
    ExitType.STOP_LOSS: 3,
    ExitType.INDICATOR: 4,
    ExitType.REVERSE_SIGNAL: 5,
    ExitType.SQUARE_OFF: 6,
    ExitType.TIME: 7,
}


# ─── P&L helpers ────────────────────────────────────────────────────────


def _trade_pnl(*, side: Side, entry_price: float, exit_price: float, quantity: float) -> float:
    """Signed P&L for one trade leg, before any cost subtraction."""
    if side is Side.BUY:
        return (exit_price - entry_price) * quantity
    return (entry_price - exit_price) * quantity


def _unrealised_pnl(position: PositionState, mark_price: float) -> float:
    """Mark-to-market on ``mark_price`` for the open quantity."""
    return _trade_pnl(
        side=position.side,
        entry_price=position.entry_price,
        exit_price=mark_price,
        quantity=position.remaining_quantity,
    )


def _roll_daily_stats(daily: _DailyStats, current_day: date) -> None:
    """Reset trades_today and daily_pnl when the wall-clock day changes."""
    if daily.current_day is None:
        daily.current_day = current_day
        return
    if current_day != daily.current_day:
        daily.current_day = current_day
        daily.trades_today = 0
        daily.daily_pnl = 0.0


__all__ = ["simulate"]
