"""Audit log — public boundary.

Pure backend audit emitter for security-critical events. Records
strategy changes, backtest runs, AI suggestions, risk blocks, paper
trades, live order attempts, Pine imports, and kill-switch events to a
thread-safe in-memory ring buffer.

The store is intentionally in-memory for now — a future phase will
swap a DB-backed implementation in behind the same public API.

Public surface::

    emit_event / query_events / clear_audit_log /
    AuditEvent / AuditQueryResult /
    log_* convenience wrappers (loggers.py)
"""

from __future__ import annotations

from app.strategy_engine.audit.emitter import (
    clear_audit_log,
    emit_event,
    query_events,
)
from app.strategy_engine.audit.models import (
    AuditEvent,
    AuditQueryResult,
    EventActor,
    EventSeverity,
    EventType,
)

__all__ = [
    "AuditEvent",
    "AuditQueryResult",
    "EventActor",
    "EventSeverity",
    "EventType",
    "clear_audit_log",
    "emit_event",
    "query_events",
]
