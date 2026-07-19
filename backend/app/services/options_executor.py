"""Options executor — Brick #3 Module A (paper-only, double-locked, unwired).

Executes a single-leg long-premium options trade for an OPTIONS-configured
strategy, entirely in paper. Two independent locks must BOTH open before
anything runs:

    1. ``settings.options_execution_enabled`` (env OPTIONS_EXECUTION_ENABLED,
       default **False**) — global master switch;
    2. ``strategy.is_paper is True`` — a LIVE strategy is refused outright,
       even with the flag on. There is NO live path in this module at all:
       no broker is imported, constructed or called.

Entry: ``map_pine_to_option_order`` (Phase 2B/2C — real SEM_EXPIRY_DATE
enumerate-and-pick, NSE_FNO-pinned, NRML hard-guard) resolves the option leg;
the fill is simulated with the owner paper path's own ``_simulate_fill``
primitive (imported — ``strategy_executor.py`` is NOT edited) and persisted
as a ``StrategyPosition`` carrying the **option-leg symbol**.

Exit: PARTIAL reduces quantity by ``closePct`` (default 50); EXIT / SL_HIT
close the row at the payload price. Both operate on the STORED
``position.symbol`` — the leg is never re-resolved, so an expiry-window
re-resolution can never silently no-op an option exit (the 2026-05-26
futures lesson, applied from day one here).

Wiring into signal_execution (Module B) is founder-gated and NOT part of
this module: nothing imports or calls this file from the live path yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.strategy_position import StrategyPosition
from app.services.pine_mapper import (
    PineMapperError,
    map_pine_to_option_order,
    parse_options_config,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.strategy import Strategy
    from app.db.models.strategy_signal import StrategySignal

logger = get_logger("services.options_executor")

#: PARTIAL default when the payload carries no ``closePct``.
_DEFAULT_CLOSE_PCT = Decimal("50")


@dataclass
class OptionsExecutionResult:
    status: str                    # executed | skipped_flag_off | refused_not_paper
    #                              # | no_open_position | failed
    message: str = ""
    position_id: UUID | None = None
    symbol: str | None = None
    quantity: int = 0
    paper: bool = True             # Module A is paper-only, always True


def _gate(strategy: "Strategy", seam: str) -> OptionsExecutionResult | None:
    """Double lock. Returns a refusal result, or None when both locks open."""
    if not get_settings().options_execution_enabled:
        logger.info("options_executor.skipped_flag_off", seam=seam,
                    strategy_id=str(strategy.id))
        return OptionsExecutionResult(
            status="skipped_flag_off",
            message="OPTIONS_EXECUTION_ENABLED is False — options executor dormant")
    if strategy.is_paper is not True:
        logger.warning("options_executor.refused_not_paper", seam=seam,
                       strategy_id=str(strategy.id),
                       is_paper=strategy.is_paper)
        return OptionsExecutionResult(
            status="refused_not_paper",
            message="options execution is paper-only (Module A); strategy is "
                    "not is_paper=True — refusing")
    return None


async def execute_options_entry(
    session: "AsyncSession",
    *,
    signal: "StrategySignal",
    strategy: "Strategy",
    scrip_master: Any | None = None,
    reference_date: date | None = None,
) -> OptionsExecutionResult:
    """Paper-execute an options ENTRY. Broker is never touched."""
    refused = _gate(strategy, seam="entry")
    if refused is not None:
        return refused

    payload = signal.raw_payload or {}
    try:
        parse_options_config(strategy)  # NRML hard-guard etc. — fail loudly first
        order = map_pine_to_option_order(
            payload, strategy,
            scrip_master=scrip_master, reference_date=reference_date)
    except PineMapperError as exc:
        logger.warning("options_executor.mapping_failed",
                       strategy_id=str(strategy.id), error=str(exc))
        return OptionsExecutionResult(status="failed",
                                      message=f"option mapping failed: {exc}")

    if strategy.broker_credential_id is None:
        # Paper placeholder FK (mirrors marketplace_fanout): positions carry a
        # NOT NULL credential FK even though paper never builds a broker.
        logger.warning("options_executor.no_credential_placeholder",
                       strategy_id=str(strategy.id))
        return OptionsExecutionResult(
            status="failed",
            message="strategy has no broker_credential_id for the paper "
                    "placeholder; cannot persist option position")

    # Owner paper path's own fill primitive — imported, not edited.
    from app.services.strategy_executor import _simulate_fill

    sim = _simulate_fill(signal, order.quantity)
    avg_price = sim.get("avg_price")

    position = StrategyPosition(
        user_id=signal.user_id,
        strategy_id=strategy.id,
        broker_credential_id=strategy.broker_credential_id,
        signal_id=signal.id,
        symbol=order.symbol,                    # OPTION leg, not the underlying
        # Stored as 'buy' — the OrderSide spelling every shared lookup
        # (direct_exit.get_open_position, position_lookup) and close path
        # (kill_switch opposite_side, fan-out) filters on. The leg IS a buy:
        # single-leg long premium (CE/PE). Brick #4 slice-① side-vocab fix.
        side="buy",
        total_quantity=order.quantity,
        remaining_quantity=order.quantity,
        avg_entry_price=avg_price,
        status="open",
    )
    session.add(position)
    await session.commit()

    logger.info("options_executor.paper_entry",
                strategy_id=str(strategy.id), signal_id=str(signal.id),
                symbol=order.symbol, quantity=order.quantity,
                avg_price=str(avg_price),
                broker_order_id=sim.get("broker_order_id"))
    return OptionsExecutionResult(
        status="executed",
        message=f"paper option entry {order.symbol} x{order.quantity}",
        position_id=position.id, symbol=order.symbol, quantity=order.quantity)


async def _find_open_option_position(
    session: "AsyncSession", strategy_id: UUID
) -> StrategyPosition | None:
    """Newest open/partial OWNER option-leg position for this strategy.

    Brick #4 slice-① scoping fixes (audit landmines):
      * ``subscription_id IS NULL`` — the OWNER's exit must never grab a
        marketplace subscriber's mirror row once fan-out is enabled (same
        class as the kill-switch credential-scoping fix);
      * option-leg symbol filter (``%-CE`` / ``%-PE``, the shape
        ``map_pine_to_option_order`` stores from the scrip master) — a stale
        futures row (``%-FUT``) for the same strategy can never be picked.
    """
    from sqlalchemy import or_, select

    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.strategy_id == strategy_id,
            StrategyPosition.status.in_(("open", "partial")),
            StrategyPosition.subscription_id.is_(None),
            or_(
                StrategyPosition.symbol.like("%-CE"),
                StrategyPosition.symbol.like("%-PE"),
            ),
        )
        .order_by(StrategyPosition.opened_at.desc())
    )
    return (await session.execute(stmt)).scalars().first()


async def execute_options_exit(
    session: "AsyncSession",
    *,
    signal: "StrategySignal",
    strategy: "Strategy",
    action_kind: str,
) -> OptionsExecutionResult:
    """Paper-close (fully or partially) the strategy's open option position.

    Uses the STORED ``position.symbol`` — the payload's symbol is the
    underlying and is deliberately ignored for leg identity.
    """
    refused = _gate(strategy, seam=f"exit:{action_kind}")
    if refused is not None:
        return refused

    position = await _find_open_option_position(session, strategy.id)
    if position is None:
        logger.info("options_executor.exit_no_open_position",
                    strategy_id=str(strategy.id), action_kind=action_kind)
        return OptionsExecutionResult(
            status="no_open_position",
            message="no open option position for this strategy — exit is a no-op")

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
    leg_pnl = (exit_price - entry_price) * close_qty   # long premium
    position.final_pnl = (Decimal(str(position.final_pnl or 0)) + leg_pnl)

    if position.remaining_quantity <= 0:
        position.status = "closed"
        position.closed_at = datetime.now(UTC)
    else:
        position.status = "partial"
    await session.commit()

    logger.info("options_executor.paper_exit",
                strategy_id=str(strategy.id), signal_id=str(signal.id),
                action_kind=action_kind, symbol=position.symbol,
                closed_qty=close_qty, exit_price=str(exit_price),
                leg_pnl=str(leg_pnl), status=position.status)
    return OptionsExecutionResult(
        status="executed",
        message=f"paper option {action_kind}: {position.symbol} x{close_qty} "
                f"@ {exit_price}",
        position_id=position.id, symbol=position.symbol, quantity=close_qty)


__all__ = [
    "OptionsExecutionResult",
    "execute_options_entry",
    "execute_options_exit",
]
