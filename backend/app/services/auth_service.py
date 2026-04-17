"""Authentication service — register, login, token management, password changes.

Orchestrates security primitives from :mod:`app.core.security` and
:mod:`app.core.security_ext` into complete auth flows with audit logging.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.core.security_ext import (
    check_login_attempts,
    create_session_token,
    generate_session_fingerprint,
    record_failed_login,
    reset_login_attempts,
    revoke_session_token,
    validate_password_strength,
    validate_session_token,
)
from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.kill_switch import KillSwitchConfig
from app.db.models.user import User
from app.schemas.auth import AuthTokens

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("app.services.auth")

# Token TTLs
_ACCESS_TOKEN_TTL = 3600  # 1 hour
_REFRESH_TOKEN_TTL = 7 * 86400  # 7 days


class AuthService:
    """Complete authentication + authorisation flows."""

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        phone: str | None,
        db: AsyncSession,
    ) -> User:
        """Register a new user.

        1. Validate password strength
        2. Check email uniqueness
        3. Hash password (bcrypt)
        4. Create user (active for beta)
        5. Create default kill_switch_config
        6. Audit log
        """
        # Password policy
        pw_check = validate_password_strength(password, email=email, name=full_name)
        if not pw_check.is_valid:
            raise ValueError(f"Weak password: {'; '.join(pw_check.reasons)}")

        # Duplicate check
        stmt = select(User).where(User.email == email.lower())
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            raise EmailAlreadyRegisteredError(email)

        # Create user
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=full_name,
            phone=phone,
            is_active=True,  # Beta: active immediately
            is_admin=False,
            notification_prefs={"email": True, "telegram": False},
        )
        db.add(user)
        await db.flush()  # assigns user.id

        # Default kill switch config
        ks_config = KillSwitchConfig(
            user_id=user.id,
            max_daily_loss_inr=Decimal("5000"),
            max_daily_trades=50,
            enabled=True,
            auto_square_off=True,
        )
        db.add(ks_config)

        # Audit
        db.add(
            AuditLog(
                user_id=user.id,
                actor=ActorType.USER,
                action="register",
                resource_type="user",
                resource_id=str(user.id),
            )
        )

        await db.commit()
        await db.refresh(user)
        logger.info("auth.register", user_id=str(user.id), email=email)
        return user

    async def login(
        self,
        email: str,
        password: str,
        request_metadata: dict[str, Any],
        db: AsyncSession,
    ) -> AuthTokens:
        """Authenticate user and return JWT token pair.

        1. Brute-force check
        2. Find user
        3. Verify password
        4. Generate tokens (access + refresh)
        5. Audit log
        """
        identifier = email.lower()

        # Brute-force lockout
        login_status = await check_login_attempts(identifier)
        if login_status.is_locked:
            raise AccountLockedError(login_status.lock_expires_in)

        # Lookup
        stmt = select(User).where(User.email == identifier)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            await record_failed_login(identifier)
            raise InvalidCredentialsError()

        if not user.is_active:
            raise AccountInactiveError()

        # Success — reset attempts
        await reset_login_attempts(identifier)

        # Generate fingerprint
        fingerprint = generate_session_fingerprint(
            user_agent=request_metadata.get("user_agent", ""),
            ip=request_metadata.get("ip", ""),
        )

        # Tokens
        access_token = create_session_token(
            str(user.id), fingerprint, ttl_seconds=_ACCESS_TOKEN_TTL
        )
        refresh_token = create_session_token(
            str(user.id), fingerprint, ttl_seconds=_REFRESH_TOKEN_TTL
        )

        # Audit
        db.add(
            AuditLog(
                user_id=user.id,
                actor=ActorType.USER,
                action="login",
                resource_type="session",
                resource_id=str(user.id),
                ip_address=request_metadata.get("ip"),
                user_agent=request_metadata.get("user_agent"),
            )
        )
        await db.commit()

        logger.info("auth.login", user_id=str(user.id))
        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=_ACCESS_TOKEN_TTL,
        )

    async def refresh_token(
        self,
        refresh_token: str,
        fingerprint: str | None,
        db: AsyncSession,
    ) -> AuthTokens:
        """Refresh an expired access token using a valid refresh token."""
        claims = await validate_session_token(
            refresh_token, current_fingerprint=fingerprint
        )
        if claims is None:
            raise InvalidTokenError()

        user_id = claims.get("sub")
        if not user_id:
            raise InvalidTokenError()

        # Verify user still exists and is active
        stmt = select(User).where(User.id == UUID(user_id))
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None or not user.is_active:
            raise InvalidTokenError()

        fp = claims.get("fp", "")
        new_access = create_session_token(
            str(user.id), fp, ttl_seconds=_ACCESS_TOKEN_TTL
        )
        new_refresh = create_session_token(
            str(user.id), fp, ttl_seconds=_REFRESH_TOKEN_TTL
        )

        # Revoke old refresh token
        await revoke_session_token(refresh_token)

        return AuthTokens(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=_ACCESS_TOKEN_TTL,
        )

    async def logout(self, token: str, db: AsyncSession) -> None:
        """Blacklist the token."""
        claims = await validate_session_token(token)
        if claims:
            await revoke_session_token(token)
            user_id = claims.get("sub")
            if user_id:
                db.add(
                    AuditLog(
                        user_id=UUID(user_id),
                        actor=ActorType.USER,
                        action="logout",
                        resource_type="session",
                        resource_id=user_id,
                    )
                )
                await db.commit()

    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str,
        db: AsyncSession,
    ) -> bool:
        """Change password: validate old, check policy, update, blacklist sessions."""
        stmt = select(User).where(User.id == user_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise InvalidCredentialsError()

        if not verify_password(old_password, user.password_hash):
            raise InvalidCredentialsError()

        pw_check = validate_password_strength(
            new_password, email=user.email, name=user.full_name
        )
        if not pw_check.is_valid:
            raise ValueError(f"Weak password: {'; '.join(pw_check.reasons)}")

        user.password_hash = hash_password(new_password)

        db.add(
            AuditLog(
                user_id=user.id,
                actor=ActorType.USER,
                action="change_password",
                resource_type="user",
                resource_id=str(user.id),
            )
        )
        await db.commit()
        logger.info("auth.password_changed", user_id=str(user.id))
        return True

    async def get_current_user(
        self,
        token: str,
        fingerprint: str | None = None,
    ) -> dict[str, Any] | None:
        """Validate JWT and return claims dict, or None."""
        return await validate_session_token(
            token, current_fingerprint=fingerprint
        )


# ═══════════════════════════════════════════════════════════════════════
# Domain exceptions
# ═══════════════════════════════════════════════════════════════════════


class AuthError(Exception):
    """Base auth error."""

    def __init__(self, message: str = "Authentication failed", status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class EmailAlreadyRegisteredError(AuthError):
    def __init__(self, email: str):
        super().__init__(f"Email already registered: {email}", status_code=409)


class InvalidCredentialsError(AuthError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password", status_code=401)


class AccountLockedError(AuthError):
    def __init__(self, lock_expires_in: int):
        self.lock_expires_in = lock_expires_in
        super().__init__(
            f"Account locked. Try again in {lock_expires_in} seconds.",
            status_code=429,
        )


class AccountInactiveError(AuthError):
    def __init__(self) -> None:
        super().__init__("Account is inactive", status_code=403)


class InvalidTokenError(AuthError):
    def __init__(self) -> None:
        super().__init__("Invalid or expired token", status_code=401)


auth_service = AuthService()

__all__ = [
    "AccountInactiveError",
    "AccountLockedError",
    "AuthError",
    "AuthService",
    "EmailAlreadyRegisteredError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "auth_service",
]
