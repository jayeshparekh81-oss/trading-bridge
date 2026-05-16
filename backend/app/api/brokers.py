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


# ═══════════════════════════════════════════════════════════════════════
# Dhan paste-token update flow — Phase 1 (2026-05-16)
#
# Dhan PATs are user-generated (no OAuth). Customers click "Update Token"
# on /brokers, paste a fresh 24h token, we validate it against Dhan,
# encrypt + persist, and bust the per-user session cache so chart /
# backtest / paper-trading start working without a container restart.
#
# Scope rules for this block:
#   * Additions only — no edits to the Fyers code above.
#   * Reuses ``encrypt_credential`` (no new crypto).
#   * Reuses ``redis_client.cache_delete`` (no new cache layer).
#   * Reuses ``relink_strategies_to_new_credential`` (no new write path).
#   * Does NOT modify ``app.brokers.dhan`` — only invokes httpx for the
#     pre-flight probe, mirroring the headers that adapter uses.
#   * ``label`` field is accepted in the request body for forward UI
#     compatibility but NOT persisted (broker_credentials has no label
#     column and migrations are out of scope for Phase 1). The response
#     echoes the supplied / default label so the modal can render it
#     without a re-fetch.
# ═══════════════════════════════════════════════════════════════════════


import httpx as _httpx
from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict as _ConfigDict
from pydantic import Field as _Field
from sqlalchemy.exc import IntegrityError as _IntegrityError

from app.core import redis_client as _redis_client
from app.core.logging import get_logger as _get_logger
from app.services.cred_relink_service import (
    relink_strategies_to_new_credential as _relink_strategies_to_new_credential,
)

_dhan_logger = _get_logger("api.brokers.dhan")


#: Dhan tokens are JWTs; a real one is several hundred chars. 100 is a
#: cheap garbage filter — Pydantic ``min_length`` rejects shorter input
#: with a 422 before we pay the round-trip.
_DHAN_TOKEN_MIN_LENGTH = 100

#: Probe path Dhan exposes for any valid token (HTTP GET, no body).
#: ``/fundlimit`` matches what ``app.brokers.dhan.DhanBroker.login`` uses
#: so we exercise the same auth surface.
_DHAN_PROBE_PATH = "/fundlimit"

#: Probe network timeout. Fast enough that an unreachable Dhan doesn't
#: hold the user's submit button hostage for the full 30s default.
_DHAN_PROBE_TIMEOUT_S = 10.0

#: UI-only token-expiry estimate. Dhan PATs are user-configurable from
#: 1 day to 1 year at generation time; 24h is the common default and
#: what existing ``users.py:_estimate_token_expiry`` uses for Dhan.
_DHAN_DEFAULT_TOKEN_TTL_S = 24 * 60 * 60

_DHAN_DEFAULT_LABEL = "Dhan – Primary"


def _dhan_session_cache_key(user_id: str) -> str:
    """Mirror ``DhanBroker._session_cache_key`` so the update endpoint
    busts the same Redis key the broker reads from."""
    return f"dhan_session:{user_id}"


class UpdateDhanTokenRequest(_BaseModel):
    """Body schema for ``POST /api/brokers/dhan/update-token``.

    ``dhan_client_id`` is optional — when omitted on a rotation, we
    reuse the client id from the user's existing Dhan credential. A
    first-time setup (no prior Dhan cred) without an explicit
    ``dhan_client_id`` is rejected with 400.
    """

    model_config = _ConfigDict(extra="forbid")

    access_token: str = _Field(
        ..., min_length=_DHAN_TOKEN_MIN_LENGTH, max_length=4096
    )
    dhan_client_id: str | None = _Field(default=None, min_length=4, max_length=64)
    label: str | None = _Field(default=None, max_length=64)


class UpdateDhanTokenResponse(_BaseModel):
    """Success response — drives the modal's success state."""

    model_config = _ConfigDict(extra="forbid")

    success: bool
    connection_status: str
    message: str
    token_label: str
    updated_at: datetime


class DhanStatusResponse(_BaseModel):
    """``GET /api/brokers/dhan/status`` payload — drives the broker card
    badge. ``expires_estimate`` mirrors the UI badge that the existing
    list endpoint exposes via ``token_expires_at``."""

    model_config = _ConfigDict(extra="forbid")

    connected: bool
    label: str | None
    last_updated: datetime | None
    expires_estimate: datetime | None


async def _probe_dhan_token(access_token: str, client_id: str | None) -> None:
    """Call Dhan ``/v2/fundlimit`` to confirm the token authenticates.

    Raises:
        HTTPException 400: token rejected by Dhan (401/403 upstream) or
            otherwise unusable — error wording mirrors the in-app
            Hinglish message style. The caller never sees a vague
            "internal error" for a bad paste.
        HTTPException 502: Dhan upstream unreachable / non-JSON. The
            update is refused so we never persist an unverified token.
    """
    base_url = get_settings().dhan_api_base_url
    headers = {
        "access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with _httpx.AsyncClient(
            base_url=base_url,
            timeout=_httpx.Timeout(_DHAN_PROBE_TIMEOUT_S, connect=5.0),
            headers=headers,
        ) as client:
            response = await client.get(_DHAN_PROBE_PATH)
    except (_httpx.TimeoutException, _httpx.NetworkError) as exc:
        _dhan_logger.warning(
            "brokers.dhan.probe_network_failure",
            error=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Dhan se connect nahi ho paaya — internet check karo "
                "aur thodi der baad try karo."
            ),
        ) from exc

    if response.status_code in (401, 403):
        _dhan_logger.info(
            "brokers.dhan.token_rejected",
            status_code=response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid Dhan token — generate a fresh token from your "
                "Dhan dashboard (web.dhan.co → Profile → API Access)."
            ),
        )
    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Dhan service error ({response.status_code}). "
                "Thodi der baad try karo."
            ),
        )
    if response.status_code >= 400:
        # 4xx other than auth → typically a malformed header. Treat as
        # bad-token rather than upstream failure so the user knows to
        # re-paste from DhanHQ.
        _dhan_logger.warning(
            "brokers.dhan.probe_unexpected_4xx",
            status_code=response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Dhan rejected the token (HTTP {response.status_code}). "
                "Confirm both the token and Client ID and retry."
            ),
        )


async def _existing_dhan_client_id(
    db: AsyncSession, user_id
) -> str | None:
    """Return the decrypted Dhan client_id from the user's most recent
    Dhan credential, or None if they've never connected before. Used
    so a re-paste of just the access token doesn't force the user to
    re-type the client id."""
    from app.core.security import decrypt_credential

    stmt = (
        select(BrokerCredential)
        .where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.broker_name == BrokerName.DHAN,
        )
        .order_by(BrokerCredential.created_at.desc())
        .limit(1)
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if cred is None:
        return None
    try:
        return decrypt_credential(cred.client_id_enc)
    except Exception:  # noqa: BLE001
        # A corrupt prior row is surprising but not fatal here — caller
        # will fall back to the "client_id required" 400 path.
        return None


@router.post(
    "/dhan/update-token",
    response_model=UpdateDhanTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def update_dhan_token(
    body: UpdateDhanTokenRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UpdateDhanTokenResponse:
    """Validate + rotate the caller's Dhan PAT.

    Flow:
      1. Probe Dhan ``/v2/fundlimit`` with the new token. 4xx → 400.
      2. Resolve ``client_id`` from the request or from the existing
         Dhan credential (rotation without re-typing).
      3. Build an encrypted :class:`BrokerCredential` row.
      4. Atomic rotation via
         :func:`app.services.cred_relink_service.relink_strategies_to_new_credential`
         — deactivates the prior active Dhan cred, inserts new,
         repoints every strategy in a single transaction.
      5. Bust the per-user ``dhan_session:{user_id}`` Redis key so
         :meth:`DhanBroker.is_session_valid` re-probes with the new
         token on the next request.
    """
    access_token = body.access_token.strip()
    requested_client_id = (
        body.dhan_client_id.strip() if body.dhan_client_id else None
    )
    label = (body.label or _DHAN_DEFAULT_LABEL).strip() or _DHAN_DEFAULT_LABEL

    # 1. Pre-flight validation against Dhan. Refuses to persist garbage.
    await _probe_dhan_token(access_token, requested_client_id)

    # 2. Resolve client_id. Caller-supplied wins; otherwise inherit from
    # the prior Dhan credential. First-time setup with neither → 400.
    client_id = requested_client_id or await _existing_dhan_client_id(
        db, current_user.id
    )
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "First-time Dhan setup needs a dhan_client_id — find it "
                "at web.dhan.co → Profile → Client ID."
            ),
        )

    # 3. Build the encrypted credential row. For Dhan the access token
    # doubles as api_key / api_secret — matches the existing
    # /me/brokers POST shape and the frontend BROKER_SCHEMAS Dhan
    # entry so the same DB row format works for both add + update.
    encrypted_token = encrypt_credential(access_token)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(
        seconds=_DHAN_DEFAULT_TOKEN_TTL_S
    )
    new_cred = BrokerCredential(
        user_id=current_user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc=encrypt_credential(client_id),
        api_key_enc=encrypted_token,
        api_secret_enc=encrypted_token,
        access_token_enc=encrypted_token,
        token_expires_at=expires_at,
        is_active=True,
    )

    # 4. Atomic deactivate-old + insert-new + relink-strategies.
    try:
        result = await _relink_strategies_to_new_credential(
            db,
            user_id=current_user.id,
            broker_name=BrokerName.DHAN,
            new_cred=new_cred,
        )
        await db.commit()
    except _IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Another Dhan update is in progress — "
                "retry in a few seconds."
            ),
        ) from exc

    # 5. Bust the per-user session-valid cache. Failure here is
    # non-fatal: worst case is one extra probe on the next request,
    # not a security or correctness bug.
    try:
        await _redis_client.cache_delete(
            _dhan_session_cache_key(str(current_user.id))
        )
    except Exception as exc:  # noqa: BLE001
        _dhan_logger.warning(
            "brokers.dhan.session_cache_bust_failed",
            user_id=str(current_user.id),
            error=type(exc).__name__,
        )

    _dhan_logger.info(
        "brokers.dhan.token_rotated",
        user_id=str(current_user.id),
        new_credential_id=str(result.new_credential_id),
        relinked_strategy_count=result.relinked_strategy_count,
    )

    return UpdateDhanTokenResponse(
        success=True,
        connection_status="active",
        message=(
            "Connected successfully. Chart and trading are now live."
        ),
        token_label=label,
        updated_at=datetime.now(tz=timezone.utc),
    )


@router.get("/dhan/status", response_model=DhanStatusResponse)
async def dhan_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> DhanStatusResponse:
    """Return the caller's Dhan connection state for the UI badge.

    Reports ``connected=true`` only when an active Dhan credential
    exists. ``expires_estimate`` is the stored ``token_expires_at`` —
    UI-only signal, not a security guarantee (the real expiry is set by
    Dhan at PAT-generation time and we don't see it).
    """
    stmt = select(BrokerCredential).where(
        BrokerCredential.user_id == current_user.id,
        BrokerCredential.broker_name == BrokerName.DHAN,
        BrokerCredential.is_active.is_(True),
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if cred is None:
        return DhanStatusResponse(
            connected=False,
            label=None,
            last_updated=None,
            expires_estimate=None,
        )
    return DhanStatusResponse(
        connected=True,
        label=_DHAN_DEFAULT_LABEL,
        last_updated=cred.created_at,
        expires_estimate=cred.token_expires_at,
    )
