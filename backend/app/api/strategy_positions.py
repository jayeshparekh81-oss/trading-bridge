"""Strategy-engine positions API — list + kill switch.

The kill-switch endpoint here is the strategy-engine variant: it closes
every open ``StrategyPosition`` for the calling user and marks any
``received`` / ``validating`` signals as rejected so an in-flight AI
call cannot turn into an order after the user has hit the brake.

This is distinct from :mod:`app.api.kill_switch` which is the platform-
wide circuit breaker — both can coexist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core import redis_client
from app.core.logging import get_logger
from app.db.models.kill_switch import KillSwitchEvent
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.kill_switch import TripReason
from app.services import broker_resting_stops, pnl_service
from app.schemas.strategy_position import (
    KillSwitchResponse,
    StrategyPositionListResponse,
    StrategyPositionRead,
)
from app.services.position_manager import close_position_now

# The trip-meta key helper lives in the kill-switch service. It is imported,
# never modified — app/api/kill_switch.py:manual_trip already imports
# ``_reset_token_key`` from the same module, so this is the established way to
# share the key shape rather than re-spelling it here and letting the two drift.
from app.services.kill_switch_service import _TRIP_META_TTL, _trip_meta_key

logger = get_logger("app.api.strategy_positions")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


@router.get("/positions", response_model=StrategyPositionListResponse)
async def list_positions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
) -> StrategyPositionListResponse:
    """List the current user's OWN positions, newest first.

    Owner-scoped: ``subscription_id IS NULL`` excludes marketplace fan-out
    subscriber (paper) positions, which carry a non-NULL ``subscription_id`` +
    the subscriber's ``user_id``. Without this they would appear UNLABELED in
    the subscriber's own positions view once ``MARKETPLACE_FANOUT_ENABLED``
    flips. This is the user's OWN trading view; per-subscription subscriber
    views are a separate, additive endpoint (later). Mirrors the internal owner
    lookups, which already filter ``subscription_id IS NULL``.
    """
    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.user_id == current_user.id,
            StrategyPosition.subscription_id.is_(None),
        )
        .order_by(StrategyPosition.opened_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(StrategyPosition.status == status_filter)

    rows = (await db.execute(stmt)).scalars().all()
    items = [StrategyPositionRead.model_validate(r) for r in rows]

    # Attach the protective stop that lives at the BROKER.
    #
    # ``stop_loss_price`` is NULL on every direct-exit row: pine_replica owns
    # the trailing stop and re-places it at Dhan on each trail step without
    # telling this platform. The SL column therefore printed "—" over a live
    # short that had a real 3354.85 stop armed — an invisible stop reads as
    # no stop, which is the most dangerous thing this screen can imply.
    #
    # Read from cache only (the reconciliation poll fills it): a page load
    # must never make a broker call. An empty cache means UNKNOWN, so the
    # fields stay None and the UI keeps its dash — it never claims "no stop".
    try:
        stops = await broker_resting_stops.get_for_user(current_user.id)
    except Exception:  # noqa: BLE001 — never fail the list over a decoration.
        logger.warning("positions.resting_stops_unavailable")
        stops = {}
    if stops:
        for item in items:
            # ONLY a position that is still in the market can be protected.
            # The lookup is by symbol, and this account recycles one contract
            # (BSE-SEP2026-FUT) across many rows — so without this guard the
            # OPEN short's stop was attached to every CLOSED row on the same
            # symbol too, advertising protection on positions that ended days
            # ago. Caught in end-to-end verification, 2026-09-09.
            if item.status not in ("open", "partial"):
                continue
            if item.remaining_quantity <= 0:
                continue
            found = stops.get(item.symbol.strip().upper())
            if not found:
                continue
            try:
                item.broker_stop_price = Decimal(str(found["price"]))
            except (InvalidOperation, KeyError, TypeError, ValueError):
                continue
            item.broker_stop_order_id = str(found.get("order_id") or "") or None

    return StrategyPositionListResponse(positions=items, count=len(items))


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def trigger_kill_switch(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> KillSwitchResponse:
    """Stop everything for this user: trip the switch, close, reject.

    This is Simple mode's "Sab band" button, and until 2026-09-06 it was a
    DIFFERENT brake from the one Pro reads. It closed the strategy engine's own
    positions and rejected in-flight signals, but never flipped the platform
    gate, so ``GET /api/kill-switch/status`` still answered ACTIVE. A customer
    tapped "Sab band", was told "Sab band ho gaya", switched to Pro and read
    "Chalu hai — naye signals par order ja sakte hain". Two brakes, one pedal.

    Side effects, in this order:
        * The platform kill-switch gate is flipped to TRIPPED **first**, so a
          webhook arriving mid-close is already rejected. This mirrors the
          ordering in ``KillSwitchService.check_and_trigger``.
        * Every ``open`` / ``partial`` :class:`StrategyPosition` row gets
          a closing ``StrategyExecution`` and is marked ``closed``.
        * Every ``received`` / ``validating`` :class:`StrategySignal` is
          flipped to ``rejected`` with a kill-switch note.
        * A :class:`KillSwitchEvent` row is written so ``/kill-switch/history``
          shows it and ``manual_reset`` has a row to close.

    Deliberately NOT done here: the broker-level emergency square-off chain
    (``_execute_emergency_square_off``). Pro's ``POST /kill-switch/trip`` gates
    that chain behind a confirmation token precisely because it once wiped
    personal Dhan positions alongside system ones (see the Layer 1 comment in
    kill_switch_service.py). "Sab band" is a single unconfirmed tap, so it
    stops what this engine owns and flips the gate — it does not reach into
    the broker. Adding that here would make the one-tap button more dangerous
    than the token-gated one.

    Idempotent — re-calling on a clean state returns 0/0 and writes no second
    event.
    """
    # 0. Flip the gate FIRST so a concurrent webhook rejects while we close.
    already_tripped = (
        await redis_client.get_kill_switch_status(current_user.id)
        == redis_client.KILL_SWITCH_TRIPPED
    )
    await redis_client.set_kill_switch_status(
        current_user.id, redis_client.KILL_SWITCH_TRIPPED
    )
    # 1. Close open positions
    pos_stmt = select(StrategyPosition).where(
        StrategyPosition.user_id == current_user.id,
        StrategyPosition.status.in_(("open", "partial")),
    )
    positions = (await db.execute(pos_stmt)).scalars().all()
    for pos in positions:
        await close_position_now(
            db, position=pos, reason="kill_switch", ltp=None
        )

    # 2. Reject in-flight signals
    sig_stmt = (
        update(StrategySignal)
        .where(
            StrategySignal.user_id == current_user.id,
            StrategySignal.status.in_(("received", "validating")),
        )
        .values(
            status="rejected",
            notes="kill switch invoked",
            processed_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    sig_result = await db.execute(sig_stmt)
    rejected_count = sig_result.rowcount or 0

    # 3. Record the trip so Pro's status, history and reset all see ONE fact.
    #    Guarded on `already_tripped` to keep the endpoint idempotent: tapping
    #    "Sab band" twice must not stack events for one brake.
    if not already_tripped:
        daily_pnl = await pnl_service.calculate_daily_pnl(current_user.id)
        event = KillSwitchEvent(
            user_id=current_user.id,
            reason=TripReason.MANUAL.value,
            daily_pnl_at_trigger=daily_pnl,
            positions_squared_off=[
                {"position_id": str(p.id), "symbol": p.symbol} for p in positions
            ],
        )
        db.add(event)
        await db.flush()
        await redis_client.cache_set_json(
            _trip_meta_key(current_user.id),
            {
                "tripped_at": datetime.now(UTC).isoformat(),
                "reason": TripReason.MANUAL.value,
                "event_id": str(event.id),
            },
            ttl_seconds=_TRIP_META_TTL,
        )

    await db.commit()

    logger.info(
        "strategy_positions.kill_switch_triggered",
        user_id=str(current_user.id),
        positions_closed=len(positions),
        signals_rejected=rejected_count,
        gate_tripped=True,
        already_tripped=already_tripped,
    )

    return KillSwitchResponse(
        positions_closed=len(positions),
        signals_rejected=rejected_count,
        message=(
            f"Closed {len(positions)} position(s); rejected "
            f"{rejected_count} pending signal(s)."
        ),
    )


__all__ = ["router"]
