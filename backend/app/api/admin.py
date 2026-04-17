"""Admin API — user management, system health, audit logs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.models.audit_log import AuditLog
from app.db.models.broker_credential import BrokerCredential
from app.db.models.kill_switch import KillSwitchConfig, KillSwitchEvent
from app.db.models.trade import Trade
from app.db.models.user import User
from app.db.session import get_session

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ═══════════════════════════════════════════════════════════════════════
# User management
# ═══════════════════════════════════════════════════════════════════════


@router.get("/users")
async def list_users(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = None,
) -> dict[str, Any]:
    """List all users (paginated, search by email/name)."""
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(User.email.ilike(pattern) | User.full_name.ilike(pattern))
        count_stmt = count_stmt.where(
            User.email.ilike(pattern) | User.full_name.ilike(pattern)
        )

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: UUID,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """User detail with broker connections + trade stats."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Broker count
    broker_count = (
        await db.execute(
            select(func.count()).select_from(BrokerCredential).where(
                BrokerCredential.user_id == user_id
            )
        )
    ).scalar() or 0

    # Trade count + P&L
    trade_count = (
        await db.execute(
            select(func.count()).select_from(Trade).where(Trade.user_id == user_id)
        )
    ).scalar() or 0
    total_pnl = (
        await db.execute(
            select(func.sum(Trade.pnl_realized)).where(Trade.user_id == user_id)
        )
    ).scalar() or Decimal(0)

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "telegram_chat_id": user.telegram_chat_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "broker_connections": broker_count,
        "total_trades": trade_count,
        "total_pnl": str(total_pnl),
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: dict[str, Any],
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create user (admin/beta provisioning)."""
    from app.core.security import hash_password

    required = {"email", "password", "full_name"}
    if not required.issubset(body.keys()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Required fields: {required}",
        )

    # Check duplicate
    existing = (
        await db.execute(select(User).where(User.email == body["email"].lower()))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        email=body["email"].lower(),
        password_hash=hash_password(body["password"]),
        full_name=body["full_name"],
        phone=body.get("phone"),
        is_active=True,
        is_admin=body.get("is_admin", False),
        notification_prefs={"email": True, "telegram": False},
    )
    db.add(user)
    await db.flush()

    # Default kill switch config
    ks = KillSwitchConfig(
        user_id=user.id,
        max_daily_loss_inr=Decimal("5000"),
        max_daily_trades=50,
        enabled=True,
        auto_square_off=True,
    )
    db.add(ks)
    await db.commit()
    await db.refresh(user)

    return {"id": str(user.id), "email": user.email, "message": "User created."}


@router.put("/users/{user_id}/activate")
async def toggle_active(
    user_id: UUID,
    body: dict[str, Any],
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Activate/deactivate user."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = bool(body.get("is_active", True))
    await db.commit()
    return {"message": f"User {'activated' if user.is_active else 'deactivated'}."}


@router.put("/users/{user_id}/admin")
async def toggle_admin(
    user_id: UUID,
    body: dict[str, Any],
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Grant/revoke admin."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_admin = bool(body.get("is_admin", False))
    await db.commit()
    return {"message": f"Admin {'granted' if user.is_admin else 'revoked'}."}


@router.post("/users/{user_id}/reset-kill-switch")
async def admin_reset_kill_switch(
    user_id: UUID,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Admin reset kill switch for a user."""
    from app.services.kill_switch_service import kill_switch_service

    await kill_switch_service.manual_reset(
        user_id=user_id,
        reset_token="admin-override",
        admin_user_id=_admin.id,
        db=db,
    )
    return {"message": "Kill switch reset."}


# ═══════════════════════════════════════════════════════════════════════
# Audit & monitoring
# ═══════════════════════════════════════════════════════════════════════


@router.get("/audit-logs")
async def list_audit_logs(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    action: str | None = None,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    """Full audit log viewer (paginated, filtered)."""
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "logs": [
            {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "actor": log.actor.value if hasattr(log.actor, "value") else log.actor,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


@router.get("/system-health")
async def system_health(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """System metrics: active users, orders today, error rate."""
    from datetime import UTC, datetime, timedelta

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    active_users = (
        await db.execute(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
    ).scalar() or 0

    orders_today = (
        await db.execute(
            select(func.count()).select_from(Trade).where(Trade.created_at >= today_start)
        )
    ).scalar() or 0

    failed_today = (
        await db.execute(
            select(func.count())
            .select_from(Trade)
            .where(Trade.created_at >= today_start, Trade.status == "rejected")
        )
    ).scalar() or 0

    error_rate = round((failed_today / orders_today) * 100, 1) if orders_today > 0 else 0

    return {
        "active_users": active_users,
        "orders_today": orders_today,
        "failed_today": failed_today,
        "error_rate_pct": error_rate,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/broker-health")
async def broker_health(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Per-broker: session count, active connections."""
    stmt2 = select(BrokerCredential)
    result = await db.execute(stmt2)
    creds = result.scalars().all()

    broker_map: dict[str, dict[str, int]] = {}
    for c in creds:
        name = c.broker_name.value if hasattr(c.broker_name, "value") else c.broker_name
        if name not in broker_map:
            broker_map[name] = {"total": 0, "active": 0}
        broker_map[name]["total"] += 1
        if c.is_active:
            broker_map[name]["active"] += 1

    return [
        {"broker_name": name, "total_connections": stats["total"], "active_connections": stats["active"]}
        for name, stats in broker_map.items()
    ]


@router.get("/kill-switch-events")
async def list_kill_switch_events(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """All kill switch trip events across all users."""
    count_stmt = select(func.count()).select_from(KillSwitchEvent)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(KillSwitchEvent)
        .order_by(KillSwitchEvent.triggered_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "events": [
            {
                "id": str(e.id),
                "user_id": str(e.user_id),
                "reason": e.reason,
                "daily_pnl_at_trigger": str(e.daily_pnl_at_trigger),
                "triggered_at": e.triggered_at.isoformat() if e.triggered_at else None,
                "reset_at": e.reset_at.isoformat() if e.reset_at else None,
            }
            for e in events
        ],
    }


@router.post("/announcements")
async def send_announcement(
    body: dict[str, Any],
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Send announcement to all active users via notifications."""
    message = body.get("message", "")
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="'message' is required."
        )

    from app.services.notification_service import notification_service

    stmt = select(User).where(User.is_active.is_(True))
    result = await db.execute(stmt)
    users = result.scalars().all()

    sent = 0
    for user in users:
        try:
            await notification_service.send(
                user_id=user.id,
                event_type="announcement",
                context={"message": message},
                db=db,
            )
            sent += 1
        except Exception:  # noqa: BLE001
            pass

    return {"message": f"Announcement sent to {sent} users.", "total_users": len(users)}


__all__ = ["router"]
