"""Tests for notification service + notification tasks."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.core import security


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


@pytest.fixture()
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_user_obj(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    has_telegram: bool = False,
    email_pref: bool = True,
    telegram_pref: bool = False,
    is_active: bool = True,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.full_name = "Test Trader"
    user.is_active = is_active
    user.telegram_chat_id = "12345" if has_telegram else None
    user.notification_prefs = {"email": email_pref, "telegram": telegram_pref}
    return user


def _mock_user_query(user):
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    return result


# ═══════════════════════════════════════════════════════════════════════
# NotificationService: send
# ═══════════════════════════════════════════════════════════════════════


class TestNotificationSend:
    @pytest.mark.asyncio
    async def test_send_email_only(self, mock_db: AsyncMock) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        user = _make_user_obj(email_pref=True, telegram_pref=False)
        mock_db.execute.return_value = _mock_user_query(user)

        result = await svc.send(user.id, "order_filled", {"symbol": "NIFTY"}, mock_db)
        assert result["email"] == "sent"
        assert result["telegram"] == "skipped"

    @pytest.mark.asyncio
    async def test_send_telegram_only(self, mock_db: AsyncMock) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        user = _make_user_obj(
            email_pref=False, telegram_pref=True, has_telegram=True
        )
        mock_db.execute.return_value = _mock_user_query(user)

        with patch.object(svc, "send_telegram", return_value=True):
            result = await svc.send(user.id, "order_filled", {"symbol": "NIFTY"}, mock_db)
        assert result["email"] == "skipped"
        assert result["telegram"] == "sent"

    @pytest.mark.asyncio
    async def test_send_both_channels(self, mock_db: AsyncMock) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        user = _make_user_obj(
            email_pref=True, telegram_pref=True, has_telegram=True
        )
        mock_db.execute.return_value = _mock_user_query(user)

        with patch.object(svc, "send_telegram", return_value=True):
            result = await svc.send(user.id, "order_filled", {"symbol": "NIFTY"}, mock_db)
        assert result["email"] == "sent"
        assert result["telegram"] == "sent"

    @pytest.mark.asyncio
    async def test_urgent_event_overrides_prefs(self, mock_db: AsyncMock) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        # User has email=False, telegram=False, but kill_switch is urgent
        user = _make_user_obj(
            email_pref=False, telegram_pref=False, has_telegram=True
        )
        mock_db.execute.return_value = _mock_user_query(user)

        with patch.object(svc, "send_telegram", return_value=True):
            result = await svc.send(
                user.id, "kill_switch_triggered", {"reason": "loss"}, mock_db
            )
        # Urgent events override preferences
        assert result["email"] == "sent"
        assert result["telegram"] == "sent"

    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_db: AsyncMock) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        mock_db.execute.return_value = _mock_user_query(None)

        result = await svc.send(uuid.uuid4(), "order_filled", {}, mock_db)
        assert result["email"] == "skipped"
        assert result["telegram"] == "skipped"

    @pytest.mark.asyncio
    async def test_no_telegram_chat_id_skips(self, mock_db: AsyncMock) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        user = _make_user_obj(
            email_pref=True, telegram_pref=True, has_telegram=False
        )
        mock_db.execute.return_value = _mock_user_query(user)

        result = await svc.send(user.id, "order_filled", {}, mock_db)
        assert result["telegram"] == "skipped"


# ═══════════════════════════════════════════════════════════════════════
# NotificationService: send_email
# ═══════════════════════════════════════════════════════════════════════


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_dev_mode_logs(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        # ENVIRONMENT=test → dev mode → just logs
        result = await svc.send_email("test@test.com", "subject", "<p>Hi</p>", "Hi")
        assert result is True

    @pytest.mark.asyncio
    async def test_prod_mode_ses_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        monkeypatch.setenv("ENVIRONMENT", "production")

        # Clear settings cache
        from app.core.config import get_settings

        get_settings.cache_clear()

        try:
            mock_boto = MagicMock()
            mock_ses = MagicMock()
            mock_boto.client.return_value = mock_ses
            mock_ses.send_email.return_value = {"MessageId": "test"}

            with patch.dict("sys.modules", {"boto3": mock_boto}):
                result = await svc.send_email("to@test.com", "subj", "<p>Hi</p>", "Hi")
            assert result is True
        finally:
            monkeypatch.setenv("ENVIRONMENT", "test")
            get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_prod_mode_ses_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        monkeypatch.setenv("ENVIRONMENT", "production")

        from app.core.config import get_settings

        get_settings.cache_clear()

        try:
            mock_boto = MagicMock()
            mock_ses = MagicMock()
            mock_boto.client.return_value = mock_ses
            mock_ses.send_email.side_effect = Exception("SES error")

            with patch.dict("sys.modules", {"boto3": mock_boto}):
                result = await svc.send_email("to@test.com", "subj", "<p>Hi</p>", "Hi")
            assert result is False
        finally:
            monkeypatch.setenv("ENVIRONMENT", "test")
            get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════════
# NotificationService: send_telegram
# ═══════════════════════════════════════════════════════════════════════


class TestSendTelegram:
    @pytest.mark.asyncio
    async def test_telegram_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import get_settings

        from app.services.notification_service import NotificationService

        svc = NotificationService()
        # Default telegram_bot_token is empty
        result = await svc.send_telegram("12345", "Hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_dev_mode_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")

        try:
            get_settings.cache_clear()
            from app.services.notification_service import NotificationService

            svc = NotificationService()
            result = await svc.send_telegram("12345", "Hello")
            assert result is True
        finally:
            monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
            get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════════
# Template rendering
# ═══════════════════════════════════════════════════════════════════════


class TestTemplateRendering:
    def test_render_email_template(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        html, text = svc.render_template("kill_switch_triggered", {
            "reason": "Daily loss breached",
            "daily_pnl": "-5000",
            "triggered_at": "2024-01-01 10:00",
            "positions_closed": 3,
        })
        assert "Kill Switch" in html
        assert "Daily loss" in html

    def test_render_order_filled_template(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        html, text = svc.render_template("order_filled", {
            "side": "BUY",
            "symbol": "NIFTY25000CE",
            "quantity": 50,
            "price": "125.00",
            "order_id": "ORD123",
        })
        assert "NIFTY25000CE" in html
        assert "BUY" in html

    def test_render_welcome_template(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        html, text = svc.render_template("welcome", {"user_name": "Jayesh"})
        assert "Welcome" in html
        assert "Jayesh" in html

    def test_render_daily_summary_template(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        html, text = svc.render_template("daily_summary", {
            "total_pnl": 4500,
            "total_trades": 12,
            "win_rate": "67",
        })
        assert "4500" in html
        assert "12" in html

    def test_render_nonexistent_template(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        html, text = svc.render_template("nonexistent_template", {})
        # Should not raise, just return empty strings
        assert html == ""
        assert text == ""

    def test_telegram_template_render(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        msg = svc._render_telegram("kill_switch_triggered", {
            "reason": "Loss limit",
            "daily_pnl": "-5000",
        })
        assert "KILL SWITCH" in msg

    def test_email_subjects(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        subject, html, text = svc._render_email("welcome", {"user_name": "Test"})
        assert "Welcome" in subject

    def test_email_unknown_event(self) -> None:
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        subject, html, text = svc._render_email("unknown_event", {})
        assert "unknown_event" in subject


# ═══════════════════════════════════════════════════════════════════════
# Notification Celery tasks
# ═══════════════════════════════════════════════════════════════════════


class TestNotificationTasks:
    def test_send_notification_task_exists(self) -> None:
        from app.tasks.notification_tasks import send_notification_task

        assert callable(send_notification_task)

    def test_send_daily_summary_all_exists(self) -> None:
        from app.tasks.notification_tasks import send_daily_summary_all

        assert callable(send_daily_summary_all)

    def test_send_weekly_report_all_exists(self) -> None:
        from app.tasks.notification_tasks import send_weekly_report_all

        assert callable(send_weekly_report_all)
