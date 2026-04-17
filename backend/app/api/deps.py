"""FastAPI dependencies — authentication and authorisation gates.

Every protected endpoint depends on one of these extractors. The chain is:
    get_current_user → get_current_active_user → get_current_admin
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_ext import (
    generate_session_fingerprint,
    validate_session_token,
)
from app.db.models.user import User
from app.db.session import get_session


def _extract_token(request: Request) -> str:
    """Pull the Bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth[7:]


def _build_fingerprint(request: Request) -> str:
    """Build a session fingerprint from request headers."""
    return generate_session_fingerprint(
        user_agent=request.headers.get("User-Agent", ""),
        ip=request.client.host if request.client else "",
    )


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> User:
    """Extract and validate JWT from Authorization header. Return User or 401."""
    token = _extract_token(request)
    fingerprint = _build_fingerprint(request)

    claims = await validate_session_token(token, current_fingerprint=fingerprint)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = claims.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        ) from exc

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Ensure user is active. 403 if inactive."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )
    return user


async def get_current_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    """Ensure user is admin. 403 if not."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


__all__ = [
    "get_current_active_user",
    "get_current_admin",
    "get_current_user",
]
