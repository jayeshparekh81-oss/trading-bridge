"""Broker Execution Guard — pre-trade decision logic.

A pure, deterministic gatekeeper that says "yes, this strategy may go
live" or "no, here is why" by composing the engine's reliability,
truth, and paper-readiness reports.

Wiring the verdict into actual order placement is a separate future
phase — this module touches no broker adapter, no kill switch, no
order code. Tests pin that isolation via AST inspection.

Public boundary::

    GuardCheckResult / GuardDecision / Severity / evaluate_broker_guard
"""

from __future__ import annotations

from app.strategy_engine.broker_guard.guard import evaluate_broker_guard
from app.strategy_engine.broker_guard.models import (
    GuardCheckResult,
    GuardDecision,
    Severity,
)

__all__ = [
    "GuardCheckResult",
    "GuardDecision",
    "Severity",
    "evaluate_broker_guard",
]
