"""Paper Trading Engine — pure-Python streaming simulator + DB persistence.

This module is the **paper-trading** sibling of Phase 3's batch
backtest engine. The same Phase 2 entry / exit / position primitives
drive both; the difference is the I/O shape:

    Phase 3 backtest    : (full candle list, strategy)  →  BacktestResult
    Paper trading       : (session, candle, indicators) →  closed trades

The paper engine is bar-by-bar so it can be wired to a live data feed
(or a replay of one) without re-running history every tick. State is
held in a module-level record dict keyed by session id; transitions
are deterministic and re-running the same input sequence produces an
identical output sequence.

The engine **never** touches a broker — there is no order-placement
import in this module, and ``test_no_broker_imports`` AST-inspects the
package to keep that property load-bearing.

Public API — streaming engine (sync, in-memory, unchanged):

    start_session(strategy, user_id)                → PaperSession
    process_candle(session, candle, indicator_vals) → list[PaperTrade]
    end_session(session)                            → PaperSession
    get_session_trades(session)                     → list[PaperTrade]
    compute_readiness(strategy, sessions)           → PaperReadinessReport
    clear_paper_state()                             → None  (test isolation)

Public API — DB persistence (async, opt-in, added by migration 010):

    flush_session_to_store(db, session, ...)              → DB row id
    compute_readiness_from_db(db, user_id, strategy_id, strategy) → report

The DB layer is additive — the streaming engine's behaviour is
identical whether or not a caller has bound a DB session. Production
callers (the upcoming live-orders SafetyChain) opt in by calling the
persistence helpers; tests that exercise the engine alone don't need
to.
"""

from __future__ import annotations

from app.strategy_engine.paper_trading.engine import (
    clear_paper_state,
    compute_readiness,
    end_session,
    get_session_trades,
    process_candle,
    start_session,
)
from app.strategy_engine.paper_trading.models import (
    PaperReadinessReport,
    PaperSession,
    PaperTrade,
)
from app.strategy_engine.paper_trading.persistence import (
    compute_readiness_from_db,
    flush_session_to_store,
)
from app.strategy_engine.paper_trading.store import (
    DuplicatePaperSessionError,
    create_session,
    get_completed_sessions_count,
    list_sessions,
    list_trades,
    record_trade,
)

__all__ = [
    "DuplicatePaperSessionError",
    "PaperReadinessReport",
    "PaperSession",
    "PaperTrade",
    "clear_paper_state",
    "compute_readiness",
    "compute_readiness_from_db",
    "create_session",
    "end_session",
    "flush_session_to_store",
    "get_completed_sessions_count",
    "get_session_trades",
    "list_sessions",
    "list_trades",
    "process_candle",
    "record_trade",
    "start_session",
]
