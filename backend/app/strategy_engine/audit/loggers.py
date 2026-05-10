"""Convenience wrappers for the most common audit events.

Each wrapper picks the right ``event_type`` / ``actor`` / ``severity``
combination so call sites in the rest of the engine don't have to
re-derive the mapping. The wrappers all funnel through
:func:`emit_event` — so the auto-severity mapping for security-critical
event types still applies (a wrong ``severity`` here can't downgrade a
critical event).
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from app.strategy_engine.audit.emitter import emit_event
from app.strategy_engine.audit.models import AuditEvent

StrategyChangeType = Literal["created", "updated", "deleted"]
PaperTradeAction = Literal["open", "close"]
KillSwitchAction = Literal["triggered", "reset"]


def log_strategy_change(
    strategy_id: UUID,
    user_id: UUID,
    change_type: StrategyChangeType,
    summary: str,
) -> AuditEvent:
    """User-driven strategy create/update/delete."""
    event_type = f"strategy_{change_type}"
    return emit_event(
        event_type=event_type,
        actor="user",
        summary=summary,
        severity="info",
        user_id=user_id,
        strategy_id=strategy_id,
        metadata={"change_type": change_type},
    )


def log_backtest_run(
    strategy_id: UUID,
    user_id: UUID,
    success: bool,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """A backtest was kicked off (and completed or errored).

    ``success=False`` is recorded as a ``warning`` so failed runs
    surface in the warning view without being treated as a security
    incident. The metadata bag is merged in unchanged so callers can
    attach engine-version, candle counts, or error strings.
    """
    summary = (
        f"Backtest succeeded for strategy {strategy_id}"
        if success
        else f"Backtest failed for strategy {strategy_id}"
    )
    payload: dict[str, Any] = {"success": success}
    if metadata:
        payload.update(metadata)
    return emit_event(
        event_type="backtest_run",
        actor="user",
        summary=summary,
        severity="info" if success else "warning",
        user_id=user_id,
        strategy_id=strategy_id,
        metadata=payload,
    )


def log_ai_suggestion(
    strategy_id: UUID,
    user_id: UUID,
    suggestion_type: str,
    accepted: bool | None,
) -> AuditEvent:
    """An AI advisor suggestion was generated, accepted, or rejected.

    ``accepted=None`` records the suggestion itself; ``True`` /
    ``False`` records the user's decision on a previously-shown
    suggestion. The emitter forces ``ai_suggestion_rejected`` to
    ``warning`` automatically.
    """
    if accepted is None:
        event_type: str = "ai_suggestion"
        summary = f"AI suggested {suggestion_type} for strategy {strategy_id}"
    elif accepted:
        event_type = "ai_suggestion_accepted"
        summary = f"User accepted AI {suggestion_type} for strategy {strategy_id}"
    else:
        event_type = "ai_suggestion_rejected"
        summary = f"User rejected AI {suggestion_type} for strategy {strategy_id}"

    return emit_event(
        event_type=event_type,
        actor="ai" if accepted is None else "user",
        summary=summary,
        severity="info",  # rejected is auto-promoted to warning by emitter.
        user_id=user_id,
        strategy_id=strategy_id,
        metadata={"suggestion_type": suggestion_type, "accepted": accepted},
    )


def log_risk_block(
    strategy_id: UUID,
    user_id: UUID,
    reason: str,
) -> AuditEvent:
    """Broker/risk guard blocked an action — always ``critical``."""
    return emit_event(
        event_type="risk_block",
        actor="broker_guard",
        summary=f"Risk block: {reason}",
        severity="critical",
        user_id=user_id,
        strategy_id=strategy_id,
        metadata={"reason": reason},
    )


def log_pine_import(
    user_id: UUID,
    success: bool,
    license_status: str,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """A TradingView Pine Script was imported (or import was attempted)."""
    summary = (
        f"Pine import succeeded ({license_status})"
        if success
        else f"Pine import failed ({license_status})"
    )
    payload: dict[str, Any] = {
        "success": success,
        "license_status": license_status,
    }
    if metadata:
        payload.update(metadata)
    return emit_event(
        event_type="pine_import",
        actor="user",
        summary=summary,
        severity="info" if success else "warning",
        user_id=user_id,
        strategy_id=None,
        metadata=payload,
    )


def log_paper_trade(
    strategy_id: UUID,
    user_id: UUID,
    action: PaperTradeAction,
    pnl: float,
) -> AuditEvent:
    """Paper-trading position opened or closed.

    Per the spec a *closed* trade with negative pnl is recorded as
    ``warning`` so a string of losing trades shows up in the warning
    view. Open events and break-even / positive closes stay at info.
    """
    if action == "open":
        event_type = "paper_trade_opened"
        severity = "info"
        summary = f"Paper trade opened on strategy {strategy_id}"
    else:
        event_type = "paper_trade_closed"
        severity = "warning" if pnl < 0 else "info"
        summary = f"Paper trade closed on strategy {strategy_id} (pnl={pnl})"

    return emit_event(
        event_type=event_type,
        actor="user",
        summary=summary,
        severity=severity,
        user_id=user_id,
        strategy_id=strategy_id,
        metadata={"action": action, "pnl": pnl},
    )


def log_live_order_attempt(
    strategy_id: UUID,
    user_id: UUID,
    allowed: bool,
    blocking_reasons: list[str] | None = None,
) -> AuditEvent:
    """A live order was attempted — record whether it was allowed.

    A blocked order is recorded as ``live_order_blocked`` (auto-mapped
    to ``critical``) and carries the reasons in metadata. An allowed
    order is recorded as ``live_order_attempted`` at info severity.
    """
    reasons: list[str] = list(blocking_reasons) if blocking_reasons else []
    if allowed:
        return emit_event(
            event_type="live_order_attempted",
            actor="user",
            summary=f"Live order attempted on strategy {strategy_id}",
            severity="info",
            user_id=user_id,
            strategy_id=strategy_id,
            metadata={"allowed": True, "blocking_reasons": reasons},
        )
    return emit_event(
        event_type="live_order_blocked",
        actor="broker_guard",
        summary=f"Live order blocked on strategy {strategy_id}",
        severity="critical",
        user_id=user_id,
        strategy_id=strategy_id,
        metadata={"allowed": False, "blocking_reasons": reasons},
    )


def log_kill_switch_event(
    strategy_id: UUID | None,
    user_id: UUID | None,
    action: KillSwitchAction,
    reason: str,
) -> AuditEvent:
    """A kill-switch fired (or was reset). Always ``critical``."""
    return emit_event(
        event_type="kill_switch_triggered",
        actor="kill_switch",
        summary=f"Kill switch {action}: {reason}",
        severity="critical",
        user_id=user_id,
        strategy_id=strategy_id,
        metadata={"action": action, "reason": reason},
    )


__all__ = [
    "KillSwitchAction",
    "PaperTradeAction",
    "StrategyChangeType",
    "log_ai_suggestion",
    "log_backtest_run",
    "log_kill_switch_event",
    "log_live_order_attempt",
    "log_paper_trade",
    "log_pine_import",
    "log_risk_block",
    "log_strategy_change",
]
