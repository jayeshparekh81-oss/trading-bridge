"""Tests for auth service + auth API + FastAPI auth dependencies."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.core import security
from app.core.security_ext import create_session_token, generate_session_fingerprint


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


@pytest.fixture()
def fake_redis():
    """Create a fakeredis instance for tests."""
    import fakeredis.aioredis

    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def mock_db():
    """Mock async DB session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()
    return session


def _make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    password: str = "Test@1234",
    is_active: bool = True,
    is_admin: bool = False,
) -> MagicMock:
    """Create a mock User object."""
    from app.core.security import hash_password

    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.full_name = "Test User"
    user.phone = None
    user.password_hash = hash_password(password)
    user.is_active = is_active
    user.is_admin = is_admin
    user.telegram_chat_id = None
    user.notification_prefs = {"email": True, "telegram": False}
    return user


def _mock_scalar_one_or_none(user):
    """Return a mock result that provides scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    return result


# ═══════════════════════════════════════════════════════════════════════
# Auth Service: Register
# ═══════════════════════════════════════════════════════════════════════


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, mock_db: AsyncMock, fake_redis: Any) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        # No existing user
        mock_db.execute.return_value = _mock_scalar_one_or_none(None)

        # Make refresh set attributes
        async def _refresh(obj: Any) -> None:
            obj.id = uuid.uuid4()

        mock_db.refresh = _refresh

        with patch("app.services.auth_service.check_login_attempts"):
            user = await svc.register(
                email="new@example.com",
                password="StrongP@ss1",
                full_name="New User",
                phone=None,
                db=mock_db,
            )
        # Should have called add at least twice (user + kill_switch_config + audit)
        assert mock_db.add.call_count >= 2
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService, EmailAlreadyRegisteredError

        svc = AuthService()
        existing = _make_user(email="dup@example.com")
        mock_db.execute.return_value = _mock_scalar_one_or_none(existing)

        with pytest.raises(EmailAlreadyRegisteredError):
            await svc.register(
                email="dup@example.com",
                password="StrongP@ss1",
                full_name="User",
                phone=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_register_weak_password(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        mock_db.execute.return_value = _mock_scalar_one_or_none(None)

        with pytest.raises(ValueError, match="Weak password"):
            await svc.register(
                email="new@example.com",
                password="weak",
                full_name="User",
                phone=None,
                db=mock_db,
            )


# ═══════════════════════════════════════════════════════════════════════
# Auth Service: Login
# ═══════════════════════════════════════════════════════════════════════


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, mock_db: AsyncMock, fake_redis: Any) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        user = _make_user(password="Test@1234")
        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        with (
            patch("app.services.auth_service.check_login_attempts") as mock_check,
            patch("app.services.auth_service.reset_login_attempts") as mock_reset,
            patch("app.services.auth_service.record_failed_login"),
        ):
            mock_check.return_value = MagicMock(is_locked=False, attempts_remaining=5)
            mock_reset.return_value = None

            tokens = await svc.login(
                email="test@example.com",
                password="Test@1234",
                request_metadata={"ip": "127.0.0.1", "user_agent": "test"},
                db=mock_db,
            )
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.expires_in == 3600

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, mock_db: AsyncMock, fake_redis: Any) -> None:
        from app.services.auth_service import AuthService, InvalidCredentialsError

        svc = AuthService()
        user = _make_user(password="Test@1234")
        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        with (
            patch("app.services.auth_service.check_login_attempts") as mock_check,
            patch("app.services.auth_service.record_failed_login") as mock_record,
        ):
            mock_check.return_value = MagicMock(is_locked=False, attempts_remaining=5)
            mock_record.return_value = MagicMock(is_locked=False, attempts_remaining=4)

            with pytest.raises(InvalidCredentialsError):
                await svc.login(
                    email="test@example.com",
                    password="WrongPass1!",
                    request_metadata={"ip": "127.0.0.1", "user_agent": "test"},
                    db=mock_db,
                )

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, mock_db: AsyncMock, fake_redis: Any) -> None:
        from app.services.auth_service import AuthService, InvalidCredentialsError

        svc = AuthService()
        mock_db.execute.return_value = _mock_scalar_one_or_none(None)

        with (
            patch("app.services.auth_service.check_login_attempts") as mock_check,
            patch("app.services.auth_service.record_failed_login") as mock_record,
        ):
            mock_check.return_value = MagicMock(is_locked=False, attempts_remaining=5)
            mock_record.return_value = MagicMock(is_locked=False, attempts_remaining=4)

            with pytest.raises(InvalidCredentialsError):
                await svc.login(
                    email="noone@example.com",
                    password="Test@1234",
                    request_metadata={"ip": "127.0.0.1", "user_agent": "test"},
                    db=mock_db,
                )

    @pytest.mark.asyncio
    async def test_login_account_locked(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AccountLockedError, AuthService

        svc = AuthService()
        with patch("app.services.auth_service.check_login_attempts") as mock_check:
            mock_check.return_value = MagicMock(
                is_locked=True, attempts_remaining=0, lock_expires_in=3600
            )
            with pytest.raises(AccountLockedError):
                await svc.login(
                    email="test@example.com",
                    password="Test@1234",
                    request_metadata={"ip": "127.0.0.1", "user_agent": "test"},
                    db=mock_db,
                )

    @pytest.mark.asyncio
    async def test_login_inactive_account(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AccountInactiveError, AuthService

        svc = AuthService()
        user = _make_user(password="Test@1234", is_active=False)
        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        with (
            patch("app.services.auth_service.check_login_attempts") as mock_check,
            patch("app.services.auth_service.reset_login_attempts"),
        ):
            mock_check.return_value = MagicMock(is_locked=False, attempts_remaining=5)

            with pytest.raises(AccountInactiveError):
                await svc.login(
                    email="test@example.com",
                    password="Test@1234",
                    request_metadata={"ip": "127.0.0.1", "user_agent": "test"},
                    db=mock_db,
                )


# ═══════════════════════════════════════════════════════════════════════
# Auth Service: Refresh / Logout / Change password
# ═══════════════════════════════════════════════════════════════════════


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_success(self, mock_db: AsyncMock, fake_redis: Any) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        user = _make_user()
        fp = generate_session_fingerprint("agent", "127.0.0.1")
        token = create_session_token(str(user.id), fp, ttl_seconds=86400)

        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        with (
            patch("app.services.auth_service.validate_session_token") as mock_validate,
            patch("app.services.auth_service.revoke_session_token") as mock_revoke,
        ):
            mock_validate.return_value = {"sub": str(user.id), "fp": fp}
            mock_revoke.return_value = True

            tokens = await svc.refresh_token(token, fp, mock_db)
        assert tokens.access_token
        assert tokens.refresh_token

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService, InvalidTokenError

        svc = AuthService()
        with patch("app.services.auth_service.validate_session_token") as mock_validate:
            mock_validate.return_value = None
            with pytest.raises(InvalidTokenError):
                await svc.refresh_token("bad-token", "fp", mock_db)

    @pytest.mark.asyncio
    async def test_refresh_inactive_user(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService, InvalidTokenError

        svc = AuthService()
        user = _make_user(is_active=False)
        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        with patch("app.services.auth_service.validate_session_token") as mock_validate:
            mock_validate.return_value = {"sub": str(user.id), "fp": "fp"}
            with pytest.raises(InvalidTokenError):
                await svc.refresh_token("token", "fp", mock_db)


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_success(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        user_id = str(uuid.uuid4())

        with (
            patch("app.services.auth_service.validate_session_token") as mock_validate,
            patch("app.services.auth_service.revoke_session_token") as mock_revoke,
        ):
            mock_validate.return_value = {"sub": user_id, "jti": "abc"}
            mock_revoke.return_value = True
            await svc.logout("some-token", mock_db)
            mock_revoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_invalid_token(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        with patch("app.services.auth_service.validate_session_token") as mock_validate:
            mock_validate.return_value = None
            # Should not raise — just no-op
            await svc.logout("invalid", mock_db)


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_change_password_success(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        user = _make_user(password="OldP@ss123")
        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        result = await svc.change_password(
            user.id, "OldP@ss123", "NewP@ss456!", mock_db
        )
        assert result is True
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService, InvalidCredentialsError

        svc = AuthService()
        user = _make_user(password="OldP@ss123")
        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        with pytest.raises(InvalidCredentialsError):
            await svc.change_password(user.id, "WrongPass1!", "NewP@ss456!", mock_db)

    @pytest.mark.asyncio
    async def test_change_password_weak_new(self, mock_db: AsyncMock) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        user = _make_user(password="OldP@ss123")
        mock_db.execute.return_value = _mock_scalar_one_or_none(user)

        with pytest.raises(ValueError, match="Weak password"):
            await svc.change_password(user.id, "OldP@ss123", "weak", mock_db)


# ═══════════════════════════════════════════════════════════════════════
# Auth Service: get_current_user
# ═══════════════════════════════════════════════════════════════════════


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_token_returns_claims(self) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        with patch("app.services.auth_service.validate_session_token") as mock_validate:
            mock_validate.return_value = {"sub": "user-id", "fp": "fp"}
            claims = await svc.get_current_user("token", "fp")
            assert claims is not None
            assert claims["sub"] == "user-id"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self) -> None:
        from app.services.auth_service import AuthService

        svc = AuthService()
        with patch("app.services.auth_service.validate_session_token") as mock_validate:
            mock_validate.return_value = None
            claims = await svc.get_current_user("bad-token")
            assert claims is None


# ═══════════════════════════════════════════════════════════════════════
# Auth Schemas
# ═══════════════════════════════════════════════════════════════════════


class TestAuthSchemas:
    def test_register_request_valid(self) -> None:
        from app.schemas.auth import RegisterRequest

        req = RegisterRequest(
            email="test@example.com",
            password="StrongP@ss1",
            full_name="Test User",
            phone="+91-9876543210",
        )
        assert req.email == "test@example.com"

    def test_register_request_short_password(self) -> None:
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="short",
                full_name="Test User",
            )

    def test_register_request_invalid_phone(self) -> None:
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="StrongP@ss1",
                full_name="Test User",
                phone="not-a-phone!!!",
            )

    def test_login_request_valid(self) -> None:
        from app.schemas.auth import LoginRequest

        req = LoginRequest(email="test@example.com", password="pass")
        assert req.email == "test@example.com"

    def test_auth_tokens(self) -> None:
        from app.schemas.auth import AuthTokens

        tokens = AuthTokens(
            access_token="at", refresh_token="rt", expires_in=3600
        )
        assert tokens.token_type == "bearer"

    def test_user_response_from_attributes(self) -> None:
        from datetime import UTC, datetime

        from app.schemas.auth import UserResponse

        data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "full_name": "Test",
            "phone": None,
            "is_active": True,
            "is_admin": False,
            "created_at": datetime.now(UTC),
        }
        resp = UserResponse(**data)
        assert resp.email == "test@example.com"
        assert resp.is_admin is False

    def test_change_password_request(self) -> None:
        from app.schemas.auth import ChangePasswordRequest

        req = ChangePasswordRequest(
            old_password="OldP@ss1", new_password="NewP@ss123!"
        )
        assert req.old_password == "OldP@ss1"


# ═══════════════════════════════════════════════════════════════════════
# FastAPI Dependencies
# ═══════════════════════════════════════════════════════════════════════


class TestDependencies:
    def test_extract_token_missing(self) -> None:
        from fastapi import HTTPException

        from app.api.deps import _extract_token

        request = MagicMock()
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            _extract_token(request)
        assert exc_info.value.status_code == 401

    def test_extract_token_valid(self) -> None:
        from app.api.deps import _extract_token

        request = MagicMock()
        request.headers = {"Authorization": "Bearer mytoken123"}
        assert _extract_token(request) == "mytoken123"

    def test_extract_token_no_bearer(self) -> None:
        from fastapi import HTTPException

        from app.api.deps import _extract_token

        request = MagicMock()
        request.headers = {"Authorization": "Basic abc"}
        with pytest.raises(HTTPException):
            _extract_token(request)

    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self) -> None:
        from fastapi import HTTPException

        from app.api.deps import get_current_active_user

        user = _make_user(is_active=False)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_current_active_user_active(self) -> None:
        from app.api.deps import get_current_active_user

        user = _make_user(is_active=True)
        result = await get_current_active_user(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_get_current_admin_not_admin(self) -> None:
        from fastapi import HTTPException

        from app.api.deps import get_current_admin

        user = _make_user(is_admin=False)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_current_admin_is_admin(self) -> None:
        from app.api.deps import get_current_admin

        user = _make_user(is_admin=True)
        result = await get_current_admin(user)
        assert result == user
