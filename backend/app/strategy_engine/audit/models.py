"""Boundary models for the audit log.

All models are frozen + ``extra="forbid"`` so an event, once recorded,
flows through the rest of the engine (query consumers, future DB
persister) as an immutable snapshot. The emitter never mutates an
event after it's been added to the store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "strategy_created",
    "strategy_updated",
    "strategy_deleted",
    "backtest_run",
    "ai_suggestion",
    "ai_suggestion_accepted",
    "ai_suggestion_rejected",
    "risk_block",
    "paper_trade_opened",
    "paper_trade_closed",
    "live_order_attempted",
    "live_order_blocked",
    "pine_import",
    "indicator_approved",
    "kill_switch_triggered",
]

EventSeverity = Literal["info", "warning", "critical"]

EventActor = Literal["user", "system", "ai", "broker_guard", "kill_switch"]


class AuditEvent(BaseModel):
    """One recorded security-relevant action.

    ``user_id`` and ``strategy_id`` are nullable because some events
    (system-level kill-switch trips, scheduler jobs) are not tied to a
    single user or strategy. ``metadata`` is the event-specific bag —
    the emitter does not interpret it; consumers read it by event type.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID
    event_type: EventType
    severity: EventSeverity
    user_id: UUID | None = None
    strategy_id: UUID | None = None
    timestamp: datetime
    actor: EventActor
    summary: str = Field(..., min_length=1, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditQueryResult(BaseModel):
    """Result of :func:`query_events`.

    ``total_count`` is the size of the underlying buffer at query time;
    ``filtered_count`` is the number of events that matched all filters
    *before* the limit was applied. ``events`` is the most recent
    ``min(filtered_count, limit)`` matches in chronological order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    events: tuple[AuditEvent, ...] = Field(default_factory=tuple)
    total_count: int = Field(..., ge=0)
    filtered_count: int = Field(..., ge=0)


__all__ = [
    "AuditEvent",
    "AuditQueryResult",
    "EventActor",
    "EventSeverity",
    "EventType",
]
