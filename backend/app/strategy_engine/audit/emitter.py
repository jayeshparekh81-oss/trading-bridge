"""Audit emitter and query API.

:func:`emit_event` is the single write path. :func:`query_events` is
the single read path. Both go through :mod:`store` so a future DB
backend can swap in without touching call sites.

The emitter is the only place ``uuid4`` and ``datetime.now`` are
read — keeping the rest of the audit module deterministic and easy
to reason about in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, get_args
from uuid import UUID, uuid4

from app.strategy_engine.audit import store
from app.strategy_engine.audit.constants import DEFAULT_QUERY_LIMIT
from app.strategy_engine.audit.models import (
    AuditEvent,
    AuditQueryResult,
    EventActor,
    EventSeverity,
    EventType,
)

_VALID_EVENT_TYPES: frozenset[str] = frozenset(get_args(EventType))
_VALID_SEVERITIES: frozenset[str] = frozenset(get_args(EventSeverity))
_VALID_ACTORS: frozenset[str] = frozenset(get_args(EventActor))

_CRITICAL_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "live_order_blocked",
        "kill_switch_triggered",
        "risk_block",
    }
)
"""Event types whose severity is *forced* to ``critical`` regardless
of what the caller passed. Keeps the security-critical signal honest
even if a wrapper or call site forgets to set it."""

_WARNING_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "ai_suggestion_rejected",
    }
)
"""Event types whose severity is forced to ``warning`` (unless the
event type is already in the critical set, which always wins).
``paper_trade_closed`` is *not* in this set because its severity
depends on the trade pnl — that decision lives in
:func:`audit.loggers.log_paper_trade`."""


def _resolve_severity(event_type: str, requested: str) -> EventSeverity:
    if event_type in _CRITICAL_EVENT_TYPES:
        return "critical"
    if event_type in _WARNING_EVENT_TYPES:
        return "warning"
    if requested not in _VALID_SEVERITIES:
        raise ValueError(
            f"invalid severity {requested!r}; expected one of {sorted(_VALID_SEVERITIES)}"
        )
    return requested  # type: ignore[return-value]


def emit_event(
    event_type: str,
    actor: str,
    summary: str,
    severity: str = "info",
    user_id: UUID | None = None,
    strategy_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Record one audit event and return the persisted snapshot.

    The emitter generates ``event_id`` (uuid4) and ``timestamp`` (UTC
    now) — callers should not pass these. Severity for the
    security-critical event types is auto-mapped: see
    :data:`_CRITICAL_EVENT_TYPES` and :data:`_WARNING_EVENT_TYPES`.

    Raises:
        ValueError: if ``event_type``, ``actor``, or ``severity`` is
            not one of the documented literals.
    """
    if event_type not in _VALID_EVENT_TYPES:
        raise ValueError(
            f"invalid event_type {event_type!r}; expected one of {sorted(_VALID_EVENT_TYPES)}"
        )
    if actor not in _VALID_ACTORS:
        raise ValueError(f"invalid actor {actor!r}; expected one of {sorted(_VALID_ACTORS)}")

    resolved_severity = _resolve_severity(event_type, severity)
    event = AuditEvent(
        event_id=uuid4(),
        event_type=event_type,  # type: ignore[arg-type]
        severity=resolved_severity,
        user_id=user_id,
        strategy_id=strategy_id,
        timestamp=datetime.now(UTC),
        actor=actor,  # type: ignore[arg-type]
        summary=summary,
        metadata=dict(metadata) if metadata is not None else {},
    )
    store.append(event)
    return event


def query_events(
    user_id: UUID | None = None,
    strategy_id: UUID | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> AuditQueryResult:
    """Return events matching the provided filters.

    Filters are AND-combined: an event must satisfy every non-``None``
    filter to be included. ``since`` and ``until`` are inclusive
    bounds. ``limit`` trims the result to the most recent N matches
    after filtering — ``filtered_count`` reports the pre-trim total
    so the caller can detect a truncated window.

    Raises:
        ValueError: if ``event_type``, ``severity``, or ``limit`` is
            not valid.
    """
    if event_type is not None and event_type not in _VALID_EVENT_TYPES:
        raise ValueError(
            f"invalid event_type {event_type!r}; expected one of {sorted(_VALID_EVENT_TYPES)}"
        )
    if severity is not None and severity not in _VALID_SEVERITIES:
        raise ValueError(
            f"invalid severity {severity!r}; expected one of {sorted(_VALID_SEVERITIES)}"
        )
    if limit < 0:
        raise ValueError(f"limit must be non-negative, got {limit}")

    snapshot = store.snapshot()
    matched: list[AuditEvent] = []
    for event in snapshot:
        if user_id is not None and event.user_id != user_id:
            continue
        if strategy_id is not None and event.strategy_id != strategy_id:
            continue
        if event_type is not None and event.event_type != event_type:
            continue
        if severity is not None and event.severity != severity:
            continue
        if since is not None and event.timestamp < since:
            continue
        if until is not None and event.timestamp > until:
            continue
        matched.append(event)

    filtered_count = len(matched)
    # Trim to the most recent ``limit`` matches; events are
    # append-ordered (oldest → newest), so we slice the tail.
    trimmed = matched[filtered_count - limit :] if limit < filtered_count else matched

    return AuditQueryResult(
        events=tuple(trimmed),
        total_count=len(snapshot),
        filtered_count=filtered_count,
    )


def clear_audit_log() -> None:
    """Empty the in-memory buffer. Intended for tests only."""
    store.clear()


__all__ = [
    "clear_audit_log",
    "emit_event",
    "query_events",
]
