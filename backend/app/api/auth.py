"""Auth API — register, login, refresh, logout, change password, profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.auth import (
    AuthTokens,
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    AuthError,
    auth_service,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _request_metadata(request: Request) -> dict:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent", ""),
    }


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_session),
) -> User:
    """Register a new user."""
    try:
        return await auth_service.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            phone=body.phone,
            db=db,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login", response_model=AuthTokens)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> AuthTokens:
    """Login and receive JWT tokens."""
    try:
        return await auth_service.login(
            email=body.email,
            password=body.password,
            request_metadata=_request_metadata(request),
            db=db,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/refresh", response_model=AuthTokens)
async def refresh(
    body: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> AuthTokens:
    """Refresh access token using refresh token."""
    from app.core.security_ext import generate_session_fingerprint

    fingerprint = generate_session_fingerprint(
        user_agent=request.headers.get("User-Agent", ""),
        ip=request.client.host if request.client else "",
    )
    try:
        return await auth_service.refresh_token(
            refresh_token=body.refresh_token,
            fingerprint=fingerprint,
            db=db,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Logout — blacklist current token."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        await auth_service.logout(token, db)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Change password for the authenticated user."""
    try:
        await auth_service.change_password(
            user_id=user.id,
            old_password=body.old_password,
            new_password=body.new_password,
            db=db,
        )
        return {"message": "Password changed successfully."}
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_active_user),
) -> User:
    """Return current user profile."""
    return user


__all__ = ["router"]
