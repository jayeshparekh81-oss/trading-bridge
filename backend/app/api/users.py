"""User API — profile, broker management, webhooks, strategies, trades."""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.core.security import (
    encrypt_credential,
    generate_webhook_token,
)
from app.db.models.broker_credential import BrokerCredential
from app.schemas.broker import BrokerName
from app.db.models.strategy import Strategy
from app.db.models.trade import Trade
from app.db.models.user import User
from app.db.models.webhook_token import WebhookToken
from app.db.session import get_session
from app.schemas.auth import UpdateProfileRequest, UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])
logger = get_logger("app.api.users")


# ═══════════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════════


@router.get("/me", response_model=UserResponse)
async def get_profile(user: User = Depends(get_current_active_user)) -> User:
    """Current user profile."""
    return user


@router.put("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Update profile (name, phone, notification_prefs, telegram_chat_id)."""
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.phone is not None:
        user.phone = body.phone
    if body.telegram_chat_id is not None:
        user.telegram_chat_id = body.telegram_chat_id
    if body.notification_prefs is not None:
        user.notification_prefs = body.notification_prefs
    await db.commit()
    await db.refresh(user)
    return user


# ═══════════════════════════════════════════════════════════════════════
# Broker management
# ═══════════════════════════════════════════════════════════════════════


# Manually-pasted access tokens carry no expiry metadata. These defaults
# are CONSERVATIVE so the UI nudges a reconnect *before* the token dies
# rather than confidently lying about a stale one. Callers who know the
# real expiry should pass `token_expires_at` (ISO 8601) in the body and
# bypass the estimate.
def _estimate_token_expiry(broker: BrokerName) -> datetime | None:
    now = datetime.now(tz=UTC)
    if broker is BrokerName.FYERS:
        # Fyers session tokens die at next market open (~6 AM IST). 12 h
        # under-estimates on purpose. The OAuth callback uses Fyers'
        # reported `expires_in` (~24 h) since that path has real data.
        return now + timedelta(hours=12)
    if broker is BrokerName.DHAN:
        # Dhan PATs are user-configurable from 1 day to 1 year at
        # generation time. Default to the most common (1 day); callers
        # who picked a longer expiry should override via the body.
        return now + timedelta(hours=24)
    return None


def _parse_optional_expiry(raw: object) -> datetime | None:
    """Parse caller-supplied `token_expires_at`. Raise 400 on garbage or past."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token_expires_at must be an ISO 8601 string.",
        )
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"token_expires_at is not valid ISO 8601: {exc}",
        ) from exc
    if parsed.tzinfo is None:
        # Naive timestamps are ambiguous — refuse rather than guess UTC.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token_expires_at must include a timezone offset (e.g. +05:30 or Z).",
        )
    if parsed <= datetime.now(tz=UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token_expires_at must be in the future.",
        )
    return parsed


@router.get("/me/brokers")
async def list_brokers(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List connected broker accounts."""
    stmt = select(BrokerCredential).where(BrokerCredential.user_id == user.id)
    result = await db.execute(stmt)
    creds = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "broker_name": c.broker_name.value if hasattr(c.broker_name, "value") else c.broker_name,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "token_expires_at": c.token_expires_at.isoformat() if c.token_expires_at else None,
        }
        for c in creds
    ]


@router.post("/me/brokers", status_code=status.HTTP_201_CREATED)
async def add_broker(
    body: dict[str, Any],
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Add broker credentials (encrypted)."""
    required = {"broker_name", "client_id", "api_key", "api_secret"}
    if not required.issubset(body.keys()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Required fields: {required}",
        )
    broker_name_raw = body["broker_name"].strip().lower()
    try:
        broker_name_val = BrokerName(broker_name_raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown broker: {body['broker_name']}. Supported: {[b.value for b in BrokerName]}",
        )
    expires_at = _parse_optional_expiry(body.get("token_expires_at"))
    if expires_at is None:
        expires_at = _estimate_token_expiry(broker_name_val)

    cred = BrokerCredential(
        user_id=user.id,
        broker_name=broker_name_val,
        client_id_enc=encrypt_credential(body["client_id"]),
        api_key_enc=encrypt_credential(body["api_key"]),
        api_secret_enc=encrypt_credential(body["api_secret"]),
        totp_secret_enc=encrypt_credential(body["totp_secret"]) if body.get("totp_secret") else None,
        access_token_enc=encrypt_credential(body["access_token"]) if body.get("access_token") else None,
        refresh_token_enc=encrypt_credential(body["refresh_token"]) if body.get("refresh_token") else None,
        token_expires_at=expires_at,
        is_active=True,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return {"id": str(cred.id), "broker_name": broker_name_val.value, "message": "Broker added."}


@router.put("/me/brokers/{broker_id}")
async def update_broker(
    broker_id: UUID,
    body: dict[str, Any],
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Update broker credentials."""
    stmt = select(BrokerCredential).where(
        BrokerCredential.id == broker_id, BrokerCredential.user_id == user.id
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker not found.")
    if "api_key" in body:
        cred.api_key_enc = encrypt_credential(body["api_key"])
    if "api_secret" in body:
        cred.api_secret_enc = encrypt_credential(body["api_secret"])
    if "client_id" in body:
        cred.client_id_enc = encrypt_credential(body["client_id"])
    if "access_token" in body:
        cred.access_token_enc = encrypt_credential(body["access_token"])
        cred.is_active = True
    if "refresh_token" in body:
        cred.refresh_token_enc = encrypt_credential(body["refresh_token"])
    # Token expiry: an explicit value in the body always wins. Otherwise,
    # rotating a token-bearing field (api_key / api_secret / access_token)
    # triggers a default estimate. Pure metadata updates (e.g., is_active
    # toggles from the Remove button's soft-delete) leave expiry untouched
    # so tokens don't silently extend themselves.
    explicit_expiry = _parse_optional_expiry(body.get("token_expires_at"))
    rotated = "api_key" in body or "api_secret" in body or "access_token" in body
    if explicit_expiry is not None:
        cred.token_expires_at = explicit_expiry
        if not rotated:
            logger.debug(
                "Explicit token_expires_at provided without rotation — honoring user value",
                broker_id=str(cred.id),
            )
    elif rotated:
        cred.token_expires_at = _estimate_token_expiry(cred.broker_name)
    if "is_active" in body:
        cred.is_active = body["is_active"]
    await db.commit()
    return {"message": "Broker updated."}


@router.delete("/me/brokers/{broker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_broker(
    broker_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Remove broker connection."""
    stmt = select(BrokerCredential).where(
        BrokerCredential.id == broker_id, BrokerCredential.user_id == user.id
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker not found.")
    await db.delete(cred)
    await db.commit()


@router.get("/me/brokers/{broker_id}/status")
async def broker_status(
    broker_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Check broker session health."""
    stmt = select(BrokerCredential).where(
        BrokerCredential.id == broker_id, BrokerCredential.user_id == user.id
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker not found.")
    return {
        "id": str(cred.id),
        "broker_name": cred.broker_name.value if hasattr(cred.broker_name, "value") else cred.broker_name,
        "is_active": cred.is_active,
        "has_session": cred.access_token_enc is not None,
        "token_expires_at": cred.token_expires_at.isoformat() if cred.token_expires_at else None,
    }


@router.post("/me/brokers/{broker_id}/reconnect")
async def reconnect_broker(
    broker_id: UUID,
    body: dict[str, Any] | None = None,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Refresh broker session.

    PAT-based brokers (Dhan): pass {"access_token": "...", optionally
    "refresh_token", "token_expires_at"} in the body to rotate the session.
    OAuth-based brokers (Fyers): the frontend should restart the OAuth flow
    via /api/brokers/fyers/connect; calling this endpoint without a body
    is a no-op for them and just confirms the credential row exists.
    """
    stmt = select(BrokerCredential).where(
        BrokerCredential.id == broker_id, BrokerCredential.user_id == user.id
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker not found.")

    body = body or {}
    if "access_token" in body:
        cred.access_token_enc = encrypt_credential(body["access_token"])
        cred.is_active = True
        if "refresh_token" in body:
            cred.refresh_token_enc = encrypt_credential(body["refresh_token"])
        explicit_expiry = _parse_optional_expiry(body.get("token_expires_at"))
        cred.token_expires_at = explicit_expiry or _estimate_token_expiry(cred.broker_name)
        await db.commit()
        return {"message": "Broker session refreshed."}

    return {"message": "Reconnect initiated. Complete broker OAuth to refresh session."}


# ═══════════════════════════════════════════════════════════════════════
# Webhook tokens
# ═══════════════════════════════════════════════════════════════════════


@router.get("/me/webhooks")
async def list_webhooks(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List webhook tokens."""
    stmt = select(WebhookToken).where(WebhookToken.user_id == user.id)
    result = await db.execute(stmt)
    tokens = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "label": t.label,
            "is_active": t.is_active,
            "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tokens
    ]


@router.post("/me/webhooks", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: dict[str, Any] | None = None,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate new webhook token + HMAC secret."""
    label = (body or {}).get("label", "")
    raw_token = generate_webhook_token()
    hmac_secret = generate_webhook_token(16)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    wt = WebhookToken(
        user_id=user.id,
        token_hash=token_hash,
        hmac_secret_enc=encrypt_credential(hmac_secret),
        label=label or None,
        is_active=True,
    )
    db.add(wt)
    await db.commit()
    await db.refresh(wt)
    return {
        "id": str(wt.id),
        "webhook_token": raw_token,
        "hmac_secret": hmac_secret,
        "webhook_url": f"/api/webhook/{raw_token}",
        "message": "Save the token and HMAC secret — they won't be shown again.",
    }


@router.delete("/me/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_webhook(
    webhook_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Revoke webhook token."""
    stmt = select(WebhookToken).where(
        WebhookToken.id == webhook_id, WebhookToken.user_id == user.id
    )
    wt = (await db.execute(stmt)).scalar_one_or_none()
    if wt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found.")
    wt.is_active = False
    await db.commit()


@router.get("/me/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Test webhook with sample payload."""
    stmt = select(WebhookToken).where(
        WebhookToken.id == webhook_id, WebhookToken.user_id == user.id
    )
    wt = (await db.execute(stmt)).scalar_one_or_none()
    if wt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found.")
    return {
        "status": "ok",
        "webhook_id": str(wt.id),
        "is_active": wt.is_active,
        "sample_payload": {
            "action": "BUY",
            "symbol": "NIFTY25000CE",
            "exchange": "NSE",
            "order_type": "MARKET",
            "product_type": "INTRADAY",
            "quantity": 50,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# Strategies
# ═══════════════════════════════════════════════════════════════════════


@router.get("/me/strategies")
async def list_strategies(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List user's strategies."""
    stmt = select(Strategy).where(Strategy.user_id == user.id)
    result = await db.execute(stmt)
    strategies = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "webhook_token_id": str(s.webhook_token_id) if s.webhook_token_id else None,
            "broker_credential_id": str(s.broker_credential_id) if s.broker_credential_id else None,
            "max_position_size": s.max_position_size,
            "allowed_symbols": s.allowed_symbols,
            "is_active": s.is_active,
        }
        for s in strategies
    ]


@router.post("/me/strategies", status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: dict[str, Any],
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create strategy (link webhook + broker)."""
    if "name" not in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="'name' is required."
        )
    strategy = Strategy(
        user_id=user.id,
        name=body["name"],
        webhook_token_id=body.get("webhook_token_id"),
        broker_credential_id=body.get("broker_credential_id"),
        max_position_size=body.get("max_position_size", 0),
        allowed_symbols=body.get("allowed_symbols", []),
        is_active=True,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return {"id": str(strategy.id), "name": strategy.name, "message": "Strategy created."}


@router.put("/me/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: UUID,
    body: dict[str, Any],
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Update strategy."""
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    strategy = (await db.execute(stmt)).scalar_one_or_none()
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    for field in ("name", "webhook_token_id", "broker_credential_id", "max_position_size", "allowed_symbols", "is_active"):
        if field in body:
            setattr(strategy, field, body[field])
    await db.commit()
    return {"message": "Strategy updated."}


@router.delete("/me/strategies/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_strategy(
    strategy_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate strategy."""
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    strategy = (await db.execute(stmt)).scalar_one_or_none()
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    strategy.is_active = False
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════
# Trades
# ═══════════════════════════════════════════════════════════════════════


@router.get("/me/trades")
async def list_trades(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    symbol: str | None = None,
    broker_name: str | None = None,
) -> dict[str, Any]:
    """Trade history (paginated, filtered)."""
    stmt = select(Trade).where(Trade.user_id == user.id)
    count_stmt = select(func.count()).select_from(Trade).where(Trade.user_id == user.id)

    if symbol:
        stmt = stmt.where(Trade.symbol == symbol)
        count_stmt = count_stmt.where(Trade.symbol == symbol)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(Trade.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    trades = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "trades": [
            {
                "id": str(t.id),
                "symbol": t.symbol,
                "exchange": t.exchange,
                "side": t.side.value if hasattr(t.side, "value") else t.side,
                "order_type": t.order_type.value if hasattr(t.order_type, "value") else t.order_type,
                "product_type": t.product_type.value if hasattr(t.product_type, "value") else t.product_type,
                "quantity": t.quantity,
                "price": str(t.price) if t.price else None,
                "avg_fill_price": str(t.avg_fill_price) if t.avg_fill_price else None,
                "status": t.status.value if hasattr(t.status, "value") else t.status,
                "pnl_realized": str(t.pnl_realized) if t.pnl_realized else None,
                "latency_ms": t.latency_ms,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in trades
        ],
    }


@router.get("/me/trades/export")
async def export_trades(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Export trades as CSV."""
    stmt = (
        select(Trade)
        .where(Trade.user_id == user.id)
        .order_by(Trade.created_at.desc())
    )
    result = await db.execute(stmt)
    trades = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "symbol", "exchange", "side", "order_type", "product_type",
        "quantity", "price", "avg_fill_price", "status", "pnl_realized",
        "latency_ms", "created_at",
    ])
    for t in trades:
        writer.writerow([
            str(t.id), t.symbol, t.exchange,
            t.side.value if hasattr(t.side, "value") else t.side,
            t.order_type.value if hasattr(t.order_type, "value") else t.order_type,
            t.product_type.value if hasattr(t.product_type, "value") else t.product_type,
            t.quantity,
            str(t.price) if t.price else "",
            str(t.avg_fill_price) if t.avg_fill_price else "",
            t.status.value if hasattr(t.status, "value") else t.status,
            str(t.pnl_realized) if t.pnl_realized else "",
            t.latency_ms or "",
            t.created_at.isoformat() if t.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )


@router.get("/me/trades/stats")
async def trade_stats(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Win rate, total P&L, avg trade, best/worst day."""
    stmt = select(Trade).where(Trade.user_id == user.id)
    result = await db.execute(stmt)
    trades = result.scalars().all()

    if not trades:
        return {
            "total_trades": 0,
            "total_pnl": "0",
            "win_rate": 0,
            "avg_pnl_per_trade": "0",
            "best_trade_pnl": "0",
            "worst_trade_pnl": "0",
        }

    pnls = [t.pnl_realized for t in trades if t.pnl_realized is not None]
    total_pnl = sum(pnls, Decimal(0))
    wins = sum(1 for p in pnls if p > 0)
    win_rate = round((wins / len(pnls)) * 100, 1) if pnls else 0
    avg_pnl = total_pnl / len(pnls) if pnls else Decimal(0)
    best = max(pnls, default=Decimal(0))
    worst = min(pnls, default=Decimal(0))

    return {
        "total_trades": len(trades),
        "total_pnl": str(total_pnl),
        "win_rate": win_rate,
        "avg_pnl_per_trade": str(avg_pnl.quantize(Decimal("0.01"))),
        "best_trade_pnl": str(best),
        "worst_trade_pnl": str(worst),
    }


__all__ = ["router"]
