"""Broker connection API — OAuth flow for each broker.

Endpoints (Fyers only for now; Dhan/others follow same pattern):
    GET  /api/brokers/fyers/connect   → returns Fyers OAuth URL
    GET  /api/brokers/fyers/callback  → exchanges auth_code for tokens,
                                         encrypts and persists them,
                                         then redirects user back to
                                         the frontend dashboard.

Security:
    * All tokens Fernet-encrypted via ``encrypt_credential``.
    * Per-user isolation — ``BrokerCredential`` row keyed by ``user_id``.
    * State parameter in the OAuth round-trip prevents CSRF.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.brokers.fyers import FyersBroker
from app.core.config import get_settings

settings = get_settings()
from app.core.security import encrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.broker import BrokerCredentials, BrokerName

router = APIRouter(prefix="/api/brokers", tags=["brokers"])


# In-memory state store for CSRF protection.
# For production with multiple workers, replace with Redis.
_oauth_state: dict[str, str] = {}


def _build_fyers_adapter_for_connect() -> FyersBroker:
    """Build a FyersBroker with platform credentials (for OAuth URL generation only)."""
    creds = BrokerCredentials(
        user_id="platform",
        broker=BrokerName.FYERS,
        client_id=settings.fyers_app_id,
        api_key=settings.fyers_app_id,
        api_secret=settings.fyers_app_secret.get_secret_value(),
        extra={"redirect_uri": settings.fyers_redirect_uri},
    )
    return FyersBroker(credentials=creds)


@router.get("/fyers/connect")
async def fyers_connect(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, str]:
    """Generate Fyers OAuth URL for the authenticated user.

    Frontend calls this, receives ``{"url": "..."}``, and redirects the
    user to that URL in a new tab. Fyers will then redirect back to
    ``/api/brokers/fyers/callback`` with ``auth_code`` + ``state``.
    """
    # CSRF — tie a random state to this user
    state = secrets.token_urlsafe(32)
    _oauth_state[state] = str(current_user.id)

    # Pass state directly to the adapter so the Fyers SDK builds the URL
    # with `state` in the canonical position. Avoids manual query-string
    # surgery — and avoids the bug where Fyers occasionally returns the
    # state truncated when it is appended after the SDK-built URL.
    adapter = _build_fyers_adapter_for_connect()
    url = adapter.generate_auth_url(state=state)

    return {"url": url}


@router.get("/fyers/callback")
async def fyers_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    auth_code: str = Query(..., description="Fyers-supplied authorization code"),
    state: str = Query(..., description="Anti-CSRF token round-tripped from /connect"),
    s: str | None = Query(None, description="Fyers status flag (ignored)"),
) -> RedirectResponse:
    """Exchange the Fyers auth_code for tokens and persist them."""

    # 1. Validate state (CSRF protection)
    user_id_str = _oauth_state.pop(state, None)
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter — please retry Connect.",
        )

    # 2. Exchange auth_code → tokens
    adapter = _build_fyers_adapter_for_connect()
    try:
        tokens = await adapter.exchange_auth_code(auth_code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fyers token exchange failed: {exc}",
        ) from exc
    finally:
        await adapter.aclose()

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    expires_in = int(tokens.get("expires_in", 86400))  # default 24h

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Fyers did not return an access_token.",
        )

    # 3. Upsert BrokerCredential row (one per user+broker)
    import uuid as _uuid
    user_uuid = _uuid.UUID(user_id_str)

    stmt = select(BrokerCredential).where(
        BrokerCredential.user_id == user_uuid,
        BrokerCredential.broker_name == BrokerName.FYERS,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)

    if existing:
        existing.access_token_enc = encrypt_credential(access_token)
        if refresh_token:
            existing.refresh_token_enc = encrypt_credential(refresh_token)
        existing.token_expires_at = expires_at
        existing.is_active = True
    else:
        new_cred = BrokerCredential(
            user_id=user_uuid,
            broker_name=BrokerName.FYERS,
            client_id_enc=encrypt_credential(settings.fyers_app_id),
            api_key_enc=encrypt_credential(settings.fyers_app_id),
            api_secret_enc=encrypt_credential(
                settings.fyers_app_secret.get_secret_value()
            ),
            access_token_enc=encrypt_credential(access_token),
            refresh_token_enc=encrypt_credential(refresh_token) if refresh_token else None,
            token_expires_at=expires_at,
            is_active=True,
        )
        db.add(new_cred)

    await db.commit()

    # 4. Redirect the user back to the broker connections page with a success flag
    frontend_url = "https://tradetri.com/brokers?broker=fyers&status=connected"
    return RedirectResponse(url=frontend_url, status_code=status.HTTP_302_FOUND)
