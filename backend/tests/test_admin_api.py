"""Tests for admin API endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core import security


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


def _admin_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.full_name = "Admin"
    user.is_active = True
    user.is_admin = True
    return user


def _regular_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.full_name = "User"
    user.is_active = True
    user.is_admin = False
    return user


@pytest.fixture()
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


# ═══════════════════════════════════════════════════════════════════════
# Admin dependency check
# ═══════════════════════════════════════════════════════════════════════


class TestAdminAccess:
    @pytest.mark.asyncio
    async def test_non_admin_blocked(self) -> None:
        from app.api.deps import get_current_admin

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(_regular_user())
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_allowed(self) -> None:
        from app.api.deps import get_current_admin

        admin = _admin_user()
        result = await get_current_admin(admin)
        assert result.is_admin is True


# ═══════════════════════════════════════════════════════════════════════
# List users
# ═══════════════════════════════════════════════════════════════════════


class TestListUsers:
    @pytest.mark.asyncio
    async def test_list_users_paginated(self, mock_db: AsyncMock) -> None:
        from app.api.admin import list_users

        # Mock count + users
        mock_count = MagicMock()
        mock_count.scalar.return_value = 2

        user1 = _regular_user()
        user1.created_at = None
        user2 = _admin_user()
        user2.created_at = None

        mock_users = MagicMock()
        mock_users.scalars.return_value.all.return_value = [user1, user2]

        mock_db.execute.side_effect = [mock_count, mock_users]

        result = await list_users(
            _admin=_admin_user(), db=mock_db, skip=0, limit=50, search=None
        )
        assert result["total"] == 2
        assert len(result["users"]) == 2

    @pytest.mark.asyncio
    async def test_list_users_search(self, mock_db: AsyncMock) -> None:
        from app.api.admin import list_users

        mock_count = MagicMock()
        mock_count.scalar.return_value = 1

        user1 = _regular_user()
        user1.created_at = None
        mock_users = MagicMock()
        mock_users.scalars.return_value.all.return_value = [user1]

        mock_db.execute.side_effect = [mock_count, mock_users]

        result = await list_users(
            _admin=_admin_user(), db=mock_db, skip=0, limit=50, search="user@"
        )
        assert result["total"] == 1


# ═══════════════════════════════════════════════════════════════════════
# User detail
# ═══════════════════════════════════════════════════════════════════════


class TestUserDetail:
    @pytest.mark.asyncio
    async def test_get_user_detail(self, mock_db: AsyncMock) -> None:
        from app.api.admin import get_user_detail

        user = _regular_user()
        user.phone = None
        user.telegram_chat_id = None
        user.created_at = None

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = user

        mock_broker_count = MagicMock()
        mock_broker_count.scalar.return_value = 2

        mock_trade_count = MagicMock()
        mock_trade_count.scalar.return_value = 10

        mock_pnl = MagicMock()
        mock_pnl.scalar.return_value = Decimal("5000")

        mock_db.execute.side_effect = [
            mock_user_result, mock_broker_count, mock_trade_count, mock_pnl
        ]

        result = await get_user_detail(user.id, _admin=_admin_user(), db=mock_db)
        assert result["email"] == "user@example.com"
        assert result["broker_connections"] == 2
        assert result["total_trades"] == 10

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_db: AsyncMock) -> None:
        from app.api.admin import get_user_detail

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_user_detail(uuid.uuid4(), _admin=_admin_user(), db=mock_db)
        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Create user
# ═══════════════════════════════════════════════════════════════════════


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db: AsyncMock) -> None:
        from app.api.admin import create_user

        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_existing

        async def _refresh(obj: Any) -> None:
            obj.id = uuid.uuid4()
            obj.email = "new@example.com"

        mock_db.refresh = _refresh

        result = await create_user(
            body={
                "email": "new@example.com",
                "password": "StrongP@ss1",
                "full_name": "New User",
            },
            _admin=_admin_user(),
            db=mock_db,
        )
        assert "id" in result
        assert result["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_create_user_duplicate(self, mock_db: AsyncMock) -> None:
        from app.api.admin import create_user

        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = _regular_user()
        mock_db.execute.return_value = mock_existing

        with pytest.raises(HTTPException) as exc_info:
            await create_user(
                body={
                    "email": "dup@example.com",
                    "password": "StrongP@ss1",
                    "full_name": "Dup",
                },
                _admin=_admin_user(),
                db=mock_db,
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_user_missing_fields(self, mock_db: AsyncMock) -> None:
        from app.api.admin import create_user

        with pytest.raises(HTTPException) as exc_info:
            await create_user(
                body={"email": "test@test.com"},
                _admin=_admin_user(),
                db=mock_db,
            )
        assert exc_info.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════
# Activate / Deactivate / Admin toggle
# ═══════════════════════════════════════════════════════════════════════


class TestUserToggle:
    @pytest.mark.asyncio
    async def test_activate_user(self, mock_db: AsyncMock) -> None:
        from app.api.admin import toggle_active

        user = _regular_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        result = await toggle_active(user.id, {"is_active": True}, _admin_user(), mock_db)
        assert "activated" in result["message"]

    @pytest.mark.asyncio
    async def test_deactivate_user(self, mock_db: AsyncMock) -> None:
        from app.api.admin import toggle_active

        user = _regular_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        result = await toggle_active(user.id, {"is_active": False}, _admin_user(), mock_db)
        assert "deactivated" in result["message"]

    @pytest.mark.asyncio
    async def test_grant_admin(self, mock_db: AsyncMock) -> None:
        from app.api.admin import toggle_admin

        user = _regular_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        result = await toggle_admin(user.id, {"is_admin": True}, _admin_user(), mock_db)
        assert "granted" in result["message"]

    @pytest.mark.asyncio
    async def test_toggle_user_not_found(self, mock_db: AsyncMock) -> None:
        from app.api.admin import toggle_active

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await toggle_active(uuid.uuid4(), {"is_active": True}, _admin_user(), mock_db)
        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# System health / Audit logs
# ═══════════════════════════════════════════════════════════════════════


class TestSystemHealth:
    @pytest.mark.asyncio
    async def test_system_health(self, mock_db: AsyncMock) -> None:
        from app.api.admin import system_health

        mock_active = MagicMock()
        mock_active.scalar.return_value = 10
        mock_orders = MagicMock()
        mock_orders.scalar.return_value = 100
        mock_failed = MagicMock()
        mock_failed.scalar.return_value = 5

        mock_db.execute.side_effect = [mock_active, mock_orders, mock_failed]

        result = await system_health(_admin=_admin_user(), db=mock_db)
        assert result["active_users"] == 10
        assert result["orders_today"] == 100
        assert result["error_rate_pct"] == 5.0


class TestAuditLogs:
    @pytest.mark.asyncio
    async def test_list_audit_logs(self, mock_db: AsyncMock) -> None:
        from app.api.admin import list_audit_logs

        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        mock_logs = MagicMock()
        mock_logs.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [mock_count, mock_logs]

        result = await list_audit_logs(
            _admin=_admin_user(), db=mock_db, skip=0, limit=50, action=None, user_id=None
        )
        assert result["total"] == 0
        assert result["logs"] == []


class TestBrokerHealth:
    @pytest.mark.asyncio
    async def test_broker_health_empty(self, mock_db: AsyncMock) -> None:
        from app.api.admin import broker_health

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await broker_health(_admin=_admin_user(), db=mock_db)
        assert result == []


class TestKillSwitchEvents:
    @pytest.mark.asyncio
    async def test_list_events(self, mock_db: AsyncMock) -> None:
        from app.api.admin import list_kill_switch_events

        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        mock_events = MagicMock()
        mock_events.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [mock_count, mock_events]

        result = await list_kill_switch_events(
            _admin=_admin_user(), db=mock_db, skip=0, limit=50
        )
        assert result["total"] == 0


class TestAnnouncement:
    @pytest.mark.asyncio
    async def test_send_announcement(self, mock_db: AsyncMock) -> None:
        from app.api.admin import send_announcement

        mock_users_result = MagicMock()
        mock_users_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_users_result

        result = await send_announcement(
            body={"message": "Test announcement"},
            _admin=_admin_user(),
            db=mock_db,
        )
        assert "Announcement sent" in result["message"]

    @pytest.mark.asyncio
    async def test_send_announcement_empty_message(self, mock_db: AsyncMock) -> None:
        from app.api.admin import send_announcement

        with pytest.raises(HTTPException) as exc_info:
            await send_announcement(
                body={"message": ""},
                _admin=_admin_user(),
                db=mock_db,
            )
        assert exc_info.value.status_code == 400
