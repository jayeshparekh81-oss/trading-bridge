"""Authentication & authorization Pydantic schemas."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """New user sign-up payload."""

    model_config = ConfigDict(frozen=True)

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\+?[0-9\s\-]{7,20}$", v):
            raise ValueError("Invalid phone number format")
        return v


class LoginRequest(BaseModel):
    """Login payload."""

    model_config = ConfigDict(frozen=True)

    email: EmailStr
    password: str


class AuthTokens(BaseModel):
    """JWT token pair returned on login / refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """Public user profile — never exposes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    phone: str | None
    is_active: bool
    is_admin: bool
    telegram_chat_id: str | None = None
    notification_prefs: dict = Field(default_factory=dict)
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    """Change password payload."""

    model_config = ConfigDict(frozen=True)

    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Refresh access token payload."""

    model_config = ConfigDict(frozen=True)

    refresh_token: str


class UpdateProfileRequest(BaseModel):
    """User profile update — only mutable fields."""

    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    notification_prefs: dict | None = None

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\+?[0-9\s\-]{7,20}$", v):
            raise ValueError("Invalid phone number format")
        return v


__all__ = [
    "AuthTokens",
    "ChangePasswordRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "RegisterRequest",
    "UpdateProfileRequest",
    "UserResponse",
]
