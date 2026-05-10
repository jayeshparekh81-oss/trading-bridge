"""Streaming paper-trading engine.

Pure-Python, AI-free, broker-free. Every transition is deterministic
and chained through the Phase 2 entry / exit / position primitives —
the same primitives Phase 3's batch backtest uses, just driven one
candle at a time.

Lifecycle::

    start_session(strategy, user_id)         → PaperSession (frozen)
    process_candle(session, candle, ivals)   → list[PaperTrade] closed
    process_candle(session, candle, ivals)   → ...
    end_session(session)                     → PaperSession (with ended_at)
    compute_readiness(strategy, sessions)    → PaperReadinessReport

The engine holds **mutable** state in a module-level
``_RECORDS: dict[UUID, _SessionRecord]`` map. The frozen
:class:`PaperSession` snapshots returned to the caller never leak
that state; ``get_session_trades`` is the canonical way to fetch the
trades a session produced. ``clear_paper_state()`` resets the dict —
tests use it for isolation.

Conservative exit prioritisation (locked for paper trading)::

    stop_loss > trailing_stop > square_off > time > reverse_signal >
    target > partial > indicator

When multiple primitives fire on the same bar this priority picks the
most adverse one to the position — matching live-trading conservatism.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.strategy_engine.engines.entry import evaluate_entry
from app.strategy_engine.engines.exit import ExitEvent, ExitType, evaluate_exit
from app.strategy_engine.engines.position import (
    PositionState,
    close_position,
    open_position,
    update_on_candle,
)
from app.strategy_engine.paper_trading.models import (
    PaperReadinessReport,
    PaperSession,
    PaperTrade,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import Side, StrategyJSON

# ─── Live-readiness thresholds ─────────────────────────────────────────


MIN_COMPLETED_SESSIONS: int = 7
MIN_WIN_RATE: float = 0.40
MIN_RULE_ADHERENCE_PCT: float = 80.0
DEFAULT_PAPER_QUANTITY: float = 1.0

#: Conservative exit priority — most adverse triggers win when several
#: fire on a single bar.
_EXIT_PRIORITY: dict[ExitType, int] = {
    ExitType.STOP_LOSS: 0,
    ExitType.TRAILING_STOP: 1,
    ExitType.SQUARE_OFF: 2,
    ExitType.TIME: 3,
    ExitType.REVERSE_SIGNAL: 4,
    ExitType.TARGET: 5,
    ExitType.PARTIAL: 6,
    ExitType.INDICATOR: 7,
}


# ─── Private state ─────────────────────────────────────────────────────


@dataclass
class _SessionRecord:
    """Mutable engine state for one paper-trading session."""

    session: PaperSession
    strategy: StrategyJSON
    is_active: bool = True
    position: PositionState | None = None
    pending_entry_side: Side | None = None
    pending_entry_reasons: tuple[str, ...] = ()
    last_candle: Candle | None = None
    last_indicator_values: dict[str, float | None] = field(default_factory=dict)
    closed_trades: list[PaperTrade] = field(default_factory=list)
    signals_fired: int = 0
    """Count of *fresh* entry signals — off→on transitions of the
    entry rule. Persistent ``price > X`` conditions therefore count
    once at the bar they first become true, not on every subsequent
    bar where the condition stays true."""
    signals_executed: int = 0
    """How many of those signals actually opened a position next bar."""
    last_should_enter: bool = False
    """The previous bar's ``EntryDecision.should_enter`` — used to
    detect the off→on transition that increments ``signals_fired``."""


_RECORDS: dict[uuid.UUID, _SessionRecord] = {}


# ─── Public API ────────────────────────────────────────────────────────


def start_session(strategy: StrategyJSON, user_id: uuid.UUID) -> PaperSession:
    """Register a new paper-trading session and return its snapshot."""
    session_id = uuid.uuid4()
    started_at = datetime.now(UTC)
    snapshot = PaperSession(
        id=session_id,
        strategy_id=strategy.id,
        user_id=user_id,
        started_at=started_at,
        ended_at=None,
        candles_processed=0,
    )
    _RECORDS[session_id] = _SessionRecord(session=snapshot, strategy=strategy)
    return snapshot


def process_candle(
    session: PaperSession,
    candle: Candle,
    indicator_values: Mapping[str, float | None],
) -> list[PaperTrade]:
    """Advance the session one bar. Returns trades closed on this bar.

    Order of operations on each call:

        1. If a pending entry is queued from the prior bar, fill at
           ``candle.open`` (Phase 3's locked next-bar-open contract).
        2. Update the open position's high / low watermarks and
           trailing-stop ratchet.
        3. Evaluate exits — close on the most adverse triggered event.
        4. If now flat, evaluate entry — queue a pending entry for the
           next bar's open.
        5. Increment ``candles_processed`` on the session snapshot.
    """
    record = _record_for(session)
    if not record.is_active:
        raise ValueError(
            f"Session {session.id} has ended; call start_session() for a new run."
        )

    closed_this_bar: list[PaperTrade] = []

    # 1. Fill any pending entry from the prior bar at this bar's open.
    if record.pending_entry_side is not None and record.position is None:
        record.position = open_position(
            side=record.pending_entry_side,
            entry_price=candle.open,
            quantity=DEFAULT_PAPER_QUANTITY,
            entry_time=candle.timestamp,
        )
        record.signals_executed += 1
        # Hold onto the reasons — used when the trade eventually closes.
        # ``pending_entry_reasons`` already carries the prior bar's
        # decision text.
        record.pending_entry_side = None

    # 2. Update watermarks + trail (only when a position is open).
    if record.position is not None and record.position.is_open:
        record.position = update_on_candle(
            record.position,
            candle,
            trailing_stop_percent=record.strategy.exit.trailing_stop_percent,
        )

        # 3. Evaluate exits.
        events = evaluate_exit(
            position=record.position,
            current_candle=candle,
            prior_candle=record.last_candle,
            exit_rules=record.strategy.exit,
            indicator_values=indicator_values,
            prior_indicator_values=record.last_indicator_values or None,
        )
        chosen = _pick_exit(events)
        if chosen is not None:
            trade = _close_to_trade(
                record=record,
                exit_event=chosen,
                exit_time=candle.timestamp,
            )
            record.closed_trades.append(trade)
            closed_this_bar.append(trade)
            record.position = close_position(record.position)

    # 4. Evaluate entry exactly once per bar regardless of position
    #    state, so rule_adherence can see signals that fire while a
    #    position is open (a "missed" check) AND fresh signals that
    #    drive a queued entry on a flat book.
    decision = evaluate_entry(
        record.strategy,
        current_candle=candle,
        prior_candle=record.last_candle,
        indicator_values=indicator_values,
        prior_indicator_values=record.last_indicator_values or None,
    )
    is_fresh = decision.should_enter and not record.last_should_enter
    if is_fresh:
        record.signals_fired += 1
        flat = record.position is None or not record.position.is_open
        if flat and decision.side is not None:
            record.pending_entry_side = decision.side
            record.pending_entry_reasons = decision.reasons
        # else: signal was blocked by an open position — adherence will
        # reflect the gap when signals_fired > signals_executed.
    record.last_should_enter = decision.should_enter

    # 5. Update bookkeeping.
    record.last_candle = candle
    record.last_indicator_values = dict(indicator_values)
    new_processed = record.session.candles_processed + 1
    record.session = record.session.model_copy(
        update={"candles_processed": new_processed}
    )

    return closed_this_bar


def end_session(session: PaperSession) -> PaperSession:
    """Mark the session ended; return the finalised snapshot."""
    record = _record_for(session)
    if not record.is_active:
        return record.session  # idempotent
    record.is_active = False
    record.session = record.session.model_copy(
        update={"ended_at": datetime.now(UTC)}
    )
    return record.session


def get_session_trades(session: PaperSession) -> list[PaperTrade]:
    """Return every trade closed during ``session``."""
    record = _record_for(session)
    return list(record.closed_trades)


def compute_readiness(
    strategy: StrategyJSON,
    sessions: list[PaperSession],
) -> PaperReadinessReport:
    """Run the five live-ready gates over the supplied sessions.

    Sessions that have not yet ended are *not* counted toward
    ``completed_sessions`` — only ``ended_at != None`` qualifies. This
    keeps an in-progress session from accidentally tipping the gate.
    """
    completed = [s for s in sessions if s.ended_at is not None]
    completed_sessions = len(completed)

    trades: list[PaperTrade] = []
    signals_fired = 0
    signals_executed = 0
    for sess in completed:
        record = _RECORDS.get(sess.id)
        if record is None:
            continue
        trades.extend(record.closed_trades)
        signals_fired += record.signals_fired
        signals_executed += record.signals_executed

    paper_pnl = sum(t.pnl for t in trades)
    win_rate = (
        sum(1 for t in trades if t.pnl > 0) / len(trades) if trades else 0.0
    )
    rule_adherence = (
        100.0 if signals_fired == 0 else 100.0 * signals_executed / signals_fired
    )

    blocked: list[str] = []
    if completed_sessions < MIN_COMPLETED_SESSIONS:
        blocked.append(
            f"Insufficient completed sessions: {completed_sessions} < "
            f"{MIN_COMPLETED_SESSIONS}."
        )
    if paper_pnl <= 0:
        blocked.append(f"Paper P&L is not positive: {paper_pnl:.2f}.")
    if trades and win_rate < MIN_WIN_RATE:
        blocked.append(
            f"Win rate {win_rate * 100:.1f}% is below the "
            f"{MIN_WIN_RATE * 100:.0f}% minimum."
        )
    if rule_adherence < MIN_RULE_ADHERENCE_PCT:
        blocked.append(
            f"Rule adherence {rule_adherence:.1f}% is below the "
            f"{MIN_RULE_ADHERENCE_PCT:.0f}% minimum."
        )
    if not _strategy_has_stop_loss(strategy):
        blocked.append(
            "Strategy has no stop loss — paper trading cannot graduate "
            "to live without a documented stop."
        )

    return PaperReadinessReport(
        completed_sessions=completed_sessions,
        paper_pnl=paper_pnl,
        paper_win_rate=win_rate,
        rule_adherence_percent=rule_adherence,
        live_ready=not blocked,
        blocked_reasons=tuple(blocked),
    )


def clear_paper_state() -> None:
    """Drop every session from the in-memory store. Tests use this for isolation."""
    _RECORDS.clear()


# ─── Internals ─────────────────────────────────────────────────────────


def _record_for(session: PaperSession) -> _SessionRecord:
    record = _RECORDS.get(session.id)
    if record is None:
        raise ValueError(
            f"Unknown paper session: {session.id}. Has start_session() been called?"
        )
    return record


def _pick_exit(events: list[ExitEvent]) -> ExitEvent | None:
    """Conservative selection — pick the most-adverse triggered event."""
    if not events:
        return None
    return min(events, key=lambda e: _EXIT_PRIORITY[e.exit_type])


def _close_to_trade(
    *,
    record: _SessionRecord,
    exit_event: ExitEvent,
    exit_time: datetime,
) -> PaperTrade:
    """Build a :class:`PaperTrade` from the position + chosen exit event."""
    if record.position is None:  # pragma: no cover — guarded by caller
        raise RuntimeError("close requested with no open position.")
    pos = record.position
    if pos.side is Side.BUY:
        pnl = (exit_event.price - pos.entry_price) * pos.quantity
    else:
        pnl = (pos.entry_price - exit_event.price) * pos.quantity
    return PaperTrade(
        session_id=record.session.id,
        entry_time=pos.entry_time,
        exit_time=exit_time,
        side=pos.side,
        entry_price=pos.entry_price,
        exit_price=exit_event.price,
        qty=pos.quantity,
        pnl=pnl,
        exit_reason=exit_event.exit_type.value,
        entry_reasons=record.pending_entry_reasons,
    )


def _strategy_has_stop_loss(strategy: StrategyJSON) -> bool:
    return (
        strategy.exit.stop_loss_percent is not None
        or strategy.exit.trailing_stop_percent is not None
    )


__all__ = [
    "DEFAULT_PAPER_QUANTITY",
    "MIN_COMPLETED_SESSIONS",
    "MIN_RULE_ADHERENCE_PCT",
    "MIN_WIN_RATE",
    "clear_paper_state",
    "compute_readiness",
    "end_session",
    "get_session_trades",
    "process_candle",
    "start_session",
]
