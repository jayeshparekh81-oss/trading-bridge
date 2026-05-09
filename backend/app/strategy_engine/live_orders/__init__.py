"""Live broker order placement — Phase 8B.

Wraps the existing broker adapters with the safety chain
(Auto Kill Switch, paper-readiness, trust/truth scores, per-user
live-trading flag, broker-execution guard) and the audit emitter.

Phase 8B-1 ships discovery + design (see :file:`DESIGN.md`) plus the
helper boundary needed by SafetyChain. The full router and order
placement implementation lands in Phase 8B-2.
"""

from __future__ import annotations

from app.strategy_engine.live_orders.user_flags import (
    is_live_trading_enabled_for_user,
)

__all__ = [
    "is_live_trading_enabled_for_user",
]
