"""Paper Trading Engine — pure-Python streaming simulator.

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

Public API:

    start_session(strategy, user_id)                → PaperSession
    process_candle(session, candle, indicator_vals) → list[PaperTrade]
    end_session(session)                            → PaperSession
    get_session_trades(session)                     → list[PaperTrade]
    compute_readiness(strategy, sessions)           → PaperReadinessReport
    clear_paper_state()                             → None  (test isolation)
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

__all__ = [
    "PaperReadinessReport",
    "PaperSession",
    "PaperTrade",
    "clear_paper_state",
    "compute_readiness",
    "end_session",
    "get_session_trades",
    "process_candle",
    "start_session",
]
