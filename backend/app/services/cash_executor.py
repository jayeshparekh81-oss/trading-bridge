"""Cash-equity executor — CASH Module A (paper-only, double-locked, unwired).

Per CASH_MODULE_SPEC_LOCKED.md. Executes a LONG-only, DELIVERY(CNC)-only cash
equity trade for a strategy marked ``strategy_json.instrument_type == "cash"``,
entirely in paper. Two independent locks must BOTH open:

    1. ``settings.cash_execution_enabled`` (env CASH_EXECUTION_ENABLED,
       default **False**);
    2. ``strategy.is_paper is True`` — live strategies refused outright.
       No broker is imported, constructed or called anywhere in this module.

Hard rules (structural, not configurable):
  * quantity is SHARES from ``strategy_json.entry_shares`` (default 2) —
    **minimum 2 and even-only, ENFORCED by refusal** (never silently rounded);
  * LONG-only — any short indication (side/type/signal_direction) is refused;
  * DELIVERY only — MIS/INTRADAY in strategy config OR payload is refused;
  * NO mapper / NO resolver — the equity symbol is used exactly as received
    ("RELIANCE" stays "RELIANCE"); exits use the STORED position.symbol.

Wiring into signal_execution's CASH seam is a separate founder-gated module;
nothing imports or calls this file from the live path yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.strategy_position import StrategyPosition

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.strategy import Strategy
    from app.db.models.strategy_signal import StrategySignal

logger = get_logger("services.cash_executor")

#: Spec: default shares when strategy_json carries no entry_shares.
_DEFAULT_ENTRY_SHARES = 2
#: Spec: minimum shares (and even-only) — violations REFUSE, never round.
_MIN_SHARES = 2

#: PARTIAL default when the payload carries no ``closePct``.
_DEFAULT_CLOSE_PCT = Decimal("50")

#: Product spellings accepted as delivery. Anything else (MIS/INTRADAY/BO/CO)
#: is refused — cash module is CNC-only by locked spec.
_DELIVERY_ALIASES = frozenset({"DELIVERY", "CNC"})

#: Payload markers that indicate a short trade (refused — long-only).
_SHORT_PREFIX = "SHORT_"


@dataclass
class CashExecutionResult:
    status: str        # executed | skipped_flag_off | refused_not_paper
    #                  # | refused_shares | refused_short | refused_product
    #                  # | no_open_position | failed
    message: str = ""
    position_id: UUID | None = None
    symbol: str | None = None
    quantity: int = 0
    paper: bool = True  # Module A is paper-only, always True


def _gate(strategy: "Strategy", seam: str) -> CashExecutionResult | None:
    """Double lock. Returns a refusal result, or None when both locks open."""
    if not get_settings().cash_execution_enabled:
        logger.info("cash_executor.skipped_flag_off", seam=seam,
                    strategy_id=str(strategy.id))
        return CashExecutionResult(
            status="skipped_flag_off",
            message="CASH_EXECUTION_ENABLED is False — cash executor dormant")
    if strategy.is_paper is not True:
        logger.warning("cash_executor.refused_not_paper", seam=seam,
                       strategy_id=str(strategy.id), is_paper=strategy.is_paper)
        return CashExecutionResult(
            status="refused_not_paper",
            message="cash execution is paper-only (Module A); strategy is not "
                    "is_paper=True — refusing")
    return None


def _resolve_shares(strategy: "Strategy") -> tuple[int | None, str]:
    """Shares from strategy_json.entry_shares (default 2). min-2 + even-only:
    a violation returns (None, reason) — REFUSED, never rounded."""
    sj = strategy.strategy_json or {}
    raw = sj.get("entry_shares", _DEFAULT_ENTRY_SHARES)
    try:
        shares = int(raw)
    except (TypeError, ValueError):
        return None, f"entry_shares {raw!r} is not an integer"
    if shares < _MIN_SHARES:
        return None, f"entry_shares {shares} below minimum {_MIN_SHARES}"
    if shares % 2 != 0:
        return None, f"entry_shares {shares} is odd — even-only by spec"
    return shares, ""


def _is_short(payload: dict[str, Any]) -> bool:
    if str(payload.get("side") or "").strip().lower() == "short":
        return True
    for key in ("signal_direction", "type", "pine_type"):
        if str(payload.get(key) or "").strip().upper().startswith(_SHORT_PREFIX):
            return True
    return False


def _product_violation(strategy: "Strategy", payload: dict[str, Any]) -> str | None:
    """MIS/INTRADAY (or any non-delivery product) in config OR request."""
    for source, value in (("strategy_json", (strategy.strategy_json or {}).get("product_type")),
                          ("payload", payload.get("product_type"))):
        if value is None:
            continue
        norm = str(value).strip().upper()
        if norm not in _DELIVERY_ALIASES:
            return f"product_type {value!r} in {source} — cash module is DELIVERY(CNC)-only"
    return None


async def execute_cash_entry(
    session: "AsyncSession",
    *,
    signal: "StrategySignal",
    strategy: "Strategy",
) -> CashExecutionResult:
    """Paper-execute a LONG cash-equity ENTRY. Broker is never touched."""
    refused = _gate(strategy, seam="entry")
    if refused is not None:
        return refused

    payload = signal.raw_payload or {}

    if _is_short(payload):
        logger.warning("cash_executor.refused_short",
                       strategy_id=str(strategy.id), signal_id=str(signal.id))
        return CashExecutionResult(
            status="refused_short",
            message="cash module is LONG-only by locked spec — short refused")

    violation = _product_violation(strategy, payload)
    if violation is not None:
        logger.warning("cash_executor.refused_product",
                       strategy_id=str(strategy.id), detail=violation)
        return CashExecutionResult(status="refused_product", message=violation)

    shares, reason = _resolve_shares(strategy)
    if shares is None:
        logger.warning("cash_executor.refused_shares",
                       strategy_id=str(strategy.id), detail=reason)
        return CashExecutionResult(
            status="refused_shares",
            message=f"shares validation failed: {reason} — refusing (spec: "
                    f"min {_MIN_SHARES}, even-only, no silent rounding)")

    if strategy.broker_credential_id is None:
        logger.warning("cash_executor.no_credential_placeholder",
                       strategy_id=str(strategy.id))
        return CashExecutionResult(
            status="failed",
            message="strategy has no broker_credential_id for the paper "
                    "placeholder; cannot persist cash position")

    # Symbol AS-IS — no mapper, no resolver (spec). Owner paper-fill
    # primitive imported; strategy_executor.py is NOT edited.
    from app.services.strategy_executor import _simulate_fill

    symbol = signal.symbol
    sim = _simulate_fill(signal, shares)
    avg_price = sim.get("avg_price")

    position = StrategyPosition(
        user_id=signal.user_id,
        strategy_id=strategy.id,
        broker_credential_id=strategy.broker_credential_id,
        signal_id=signal.id,
        symbol=symbol,
        side="long",                       # long-only module
        total_quantity=shares,             # SHARES, not lots
        remaining_quantity=shares,
        avg_entry_price=avg_price,
        status="open",
    )
    session.add(position)
    await session.commit()

    logger.info("cash_executor.paper_entry",
                strategy_id=str(strategy.id), signal_id=str(signal.id),
                symbol=symbol, shares=shares, product="DELIVERY",
                avg_price=str(avg_price),
                broker_order_id=sim.get("broker_order_id"))
    return CashExecutionResult(
        status="executed",
        message=f"paper cash entry {symbol} x{shares} shares (DELIVERY)",
        position_id=position.id, symbol=symbol, quantity=shares)


async def _find_open_cash_position(
    session: "AsyncSession", strategy_id: UUID
) -> StrategyPosition | None:
    from sqlalchemy import select

    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.strategy_id == strategy_id,
            StrategyPosition.status.in_(("open", "partial")),
        )
        .order_by(StrategyPosition.opened_at.desc())
    )
    return (await session.execute(stmt)).scalars().first()


async def execute_cash_exit(
    session: "AsyncSession",
    *,
    signal: "StrategySignal",
    strategy: "Strategy",
    action_kind: str,
) -> CashExecutionResult:
    """Paper-close (fully or partially) the strategy's open cash position.

    Uses the STORED ``position.symbol`` — never re-resolved.
    """
    refused = _gate(strategy, seam=f"exit:{action_kind}")
    if refused is not None:
        return refused

    position = await _find_open_cash_position(session, strategy.id)
    if position is None:
        logger.info("cash_executor.exit_no_open_position",
                    strategy_id=str(strategy.id), action_kind=action_kind)
        return CashExecutionResult(
            status="no_open_position",
            message="no open cash position for this strategy — exit is a no-op")

    payload = signal.raw_payload or {}
    exit_price = Decimal(str(payload.get("price") or 0))

    if action_kind == "partial":
        pct = Decimal(str(payload.get("closePct") or _DEFAULT_CLOSE_PCT))
        close_qty = int(position.remaining_quantity * pct / Decimal("100"))
        close_qty = max(1, min(close_qty, position.remaining_quantity))
    else:  # exit | sl_hit → full close
        close_qty = position.remaining_quantity

    position.remaining_quantity -= close_qty
    entry_price = Decimal(str(position.avg_entry_price or 0))
    leg_pnl = (exit_price - entry_price) * close_qty   # long-only
    position.final_pnl = Decimal(str(position.final_pnl or 0)) + leg_pnl

    if position.remaining_quantity <= 0:
        position.status = "closed"
        position.closed_at = datetime.now(UTC)
    else:
        position.status = "partial"
    await session.commit()

    logger.info("cash_executor.paper_exit",
                strategy_id=str(strategy.id), signal_id=str(signal.id),
                action_kind=action_kind, symbol=position.symbol,
                closed_shares=close_qty, exit_price=str(exit_price),
                leg_pnl=str(leg_pnl), status=position.status)
    return CashExecutionResult(
        status="executed",
        message=f"paper cash {action_kind}: {position.symbol} x{close_qty} "
                f"shares @ {exit_price}",
        position_id=position.id, symbol=position.symbol, quantity=close_qty)


__all__ = [
    "CashExecutionResult",
    "execute_cash_entry",
    "execute_cash_exit",
]
