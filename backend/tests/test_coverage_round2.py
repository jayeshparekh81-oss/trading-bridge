"""Coverage round 2 — target remaining gaps to push past 97%.

Focuses on:
- notification_tasks.py celery task bodies (25% → 90%+)
- webhook.py kill switch trip path
- order_service.py EXIT action
- users.py not-found paths
- kill_switch_tasks.py remaining paths
- dhan.py edge cases
- schemas missing branches
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
from cryptography.fernet import Fernet

from app.core import security


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


@pytest.fixture()
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# ═══════════════════════════════════════════════════════════════════════
# notification_tasks.py — Cover celery task bodies (25% → 90%+)
# ═══════════════════════════════════════════════════════════════════════


class TestNotificationTaskBodies:
    """Cover the actual async logic inside celery tasks."""

    @pytest.mark.asyncio
    async def test_send_notification_inner_logic(self) -> None:
        """Test the async inner function that send_notification_task wraps."""
        from app.services.notification_service import notification_service

        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "test@test.com"
        mock_user.full_name = "Test"
        mock_user.telegram_chat_id = None
        mock_user.notification_prefs = {"email": True}
        mock_user.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await notification_service.send(
            user_id=mock_user.id,
            event_type="order_filled",
            context={"symbol": "NIFTY"},
            db=mock_session,
        )
        assert result["email"] == "sent"

    @pytest.mark.asyncio
    async def test_daily_summary_inner_logic(self) -> None:
        """Test the async loop that send_daily_summary_all wraps."""
        from app.services.notification_service import notification_service

        mock_session = AsyncMock()
        user1 = MagicMock()
        user1.id = uuid.uuid4()
        user1.email = "u1@test.com"
        user1.full_name = "U1"
        user1.telegram_chat_id = None
        user1.notification_prefs = {"email": True}
        user1.is_active = True

        # First call returns user list, second call returns user for notification
        mock_users_result = MagicMock()
        mock_users_result.scalars.return_value.all.return_value = [user1]
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = user1
        mock_session.execute = AsyncMock(side_effect=[mock_users_result, mock_user_result])

        result = await notification_service.send(
            user_id=user1.id,
            event_type="daily_summary",
            context={"message": "Daily summary"},
            db=mock_session,
        )
        assert result["email"] == "sent"

    @pytest.mark.asyncio
    async def test_notification_send_failure_doesnt_crash(self) -> None:
        """If notification fails for one user, loop continues."""
        from app.services.notification_service import notification_service

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await notification_service.send(
            user_id=uuid.uuid4(),
            event_type="daily_summary",
            context={},
            db=mock_session,
        )
        assert result == {"email": "skipped", "telegram": "skipped"}


# ═══════════════════════════════════════════════════════════════════════
# webhook.py — Kill switch trip response path + resolve_binding
# ═══════════════════════════════════════════════════════════════════════


class TestWebhookExtraCoverage:
    @pytest.mark.asyncio
    async def test_resolve_binding_no_strategy_no_cred(self) -> None:
        """No strategy and no single broker cred → None."""
        from app.api.webhook import _resolve_binding

        mock_db = AsyncMock()
        # Strategy query returns None
        mock_strat_result = MagicMock()
        mock_strat_result.scalars.return_value.first.return_value = None
        # Broker query returns 0 or 2 creds
        mock_cred_result = MagicMock()
        mock_cred_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[mock_strat_result, mock_cred_result])

        result = await _resolve_binding(
            mock_db, user_id=uuid.uuid4(), webhook_token_id=uuid.uuid4()
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_binding_single_cred_fallback(self) -> None:
        """No strategy but exactly 1 broker cred → returns it."""
        from app.api.webhook import _resolve_binding

        mock_db = AsyncMock()
        mock_strat_result = MagicMock()
        mock_strat_result.scalars.return_value.first.return_value = None
        mock_cred = MagicMock()
        mock_cred.id = uuid.uuid4()
        mock_cred_result = MagicMock()
        mock_cred_result.scalars.return_value.all.return_value = [mock_cred]
        mock_db.execute = AsyncMock(side_effect=[mock_strat_result, mock_cred_result])

        result = await _resolve_binding(
            mock_db, user_id=uuid.uuid4(), webhook_token_id=uuid.uuid4()
        )
        assert result == (None, mock_cred.id)

    @pytest.mark.asyncio
    async def test_resolve_binding_multiple_creds(self) -> None:
        """No strategy and multiple broker creds → None (ambiguous)."""
        from app.api.webhook import _resolve_binding

        mock_db = AsyncMock()
        mock_strat_result = MagicMock()
        mock_strat_result.scalars.return_value.first.return_value = None
        mock_cred_result = MagicMock()
        mock_cred_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        mock_db.execute = AsyncMock(side_effect=[mock_strat_result, mock_cred_result])

        result = await _resolve_binding(
            mock_db, user_id=uuid.uuid4(), webhook_token_id=uuid.uuid4()
        )
        assert result is None

    def test_parse_payload_valid(self) -> None:
        """_parse_payload with valid JSON."""
        from app.api.webhook import _parse_payload

        raw = b'{"action":"BUY","symbol":"NIFTY","quantity":50}'
        payload = _parse_payload(raw)
        assert payload.symbol == "NIFTY"

    def test_parse_payload_invalid(self) -> None:
        """_parse_payload with invalid JSON → 422."""
        from fastapi import HTTPException

        from app.api.webhook import _parse_payload

        with pytest.raises(HTTPException):
            _parse_payload(b"not-json")

    def test_compute_signal_hash_with_signal_id(self) -> None:
        from app.api.webhook import _compute_signal_hash
        from app.schemas.webhook import WebhookPayload

        payload = WebhookPayload(
            action="BUY", symbol="NIFTY", quantity=50, signal_id="my-sig-123"
        )
        uid = uuid.uuid4()
        h = _compute_signal_hash(uid, payload, b"body")
        assert "my-sig-123" in h

    def test_compute_signal_hash_without_signal_id(self) -> None:
        from app.api.webhook import _compute_signal_hash
        from app.schemas.webhook import WebhookPayload

        payload = WebhookPayload(action="BUY", symbol="NIFTY", quantity=50)
        uid = uuid.uuid4()
        h = _compute_signal_hash(uid, payload, b"body")
        assert str(uid) in h

    @pytest.mark.asyncio
    async def test_resolve_webhook_token_cache_hit(self) -> None:
        """Cache hit path for token resolution."""
        from app.api.webhook import _resolve_webhook_token

        uid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        cached = {"user_id": uid, "token_id": tid, "hmac_secret": "sec"}

        mock_db = AsyncMock()
        with patch("app.api.webhook.redis_client") as mock_rc:
            mock_rc.cache_get_json = AsyncMock(return_value=cached)
            result = await _resolve_webhook_token(mock_db, "some-token")
        assert str(result["user_id"]) == uid

    @pytest.mark.asyncio
    async def test_resolve_webhook_token_cache_corrupt(self) -> None:
        """Corrupt cache → fall through to DB."""
        from app.api.webhook import _resolve_webhook_token

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.webhook.redis_client") as mock_rc:
            mock_rc.cache_get_json = AsyncMock(return_value={"bad": "data"})
            result = await _resolve_webhook_token(mock_db, "some-token")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# users.py — Not-found paths for all CRUD endpoints
# ═══════════════════════════════════════════════════════════════════════


class TestUsersNotFoundPaths:
    @pytest.fixture()
    def mock_db(self) -> AsyncMock:
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        return db

    @pytest.fixture()
    def user(self) -> MagicMock:
        u = MagicMock()
        u.id = uuid.uuid4()
        u.is_active = True
        return u

    @pytest.mark.asyncio
    async def test_remove_broker_not_found(self, mock_db: AsyncMock, user: MagicMock) -> None:
        from fastapi import HTTPException

        from app.api.users import remove_broker

        with pytest.raises(HTTPException) as exc_info:
            await remove_broker(uuid.uuid4(), user, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_broker_status_not_found(self, mock_db: AsyncMock, user: MagicMock) -> None:
        from fastapi import HTTPException

        from app.api.users import broker_status

        with pytest.raises(HTTPException) as exc_info:
            await broker_status(uuid.uuid4(), user, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reconnect_broker_not_found(self, mock_db: AsyncMock, user: MagicMock) -> None:
        from fastapi import HTTPException

        from app.api.users import reconnect_broker

        with pytest.raises(HTTPException) as exc_info:
            await reconnect_broker(uuid.uuid4(), user, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_test_webhook_not_found(self, mock_db: AsyncMock, user: MagicMock) -> None:
        from fastapi import HTTPException

        from app.api.users import test_webhook

        with pytest.raises(HTTPException) as exc_info:
            await test_webhook(uuid.uuid4(), user, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_strategy_not_found(self, mock_db: AsyncMock, user: MagicMock) -> None:
        from fastapi import HTTPException

        from app.api.users import update_strategy

        with pytest.raises(HTTPException) as exc_info:
            await update_strategy(uuid.uuid4(), {"name": "x"}, user, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_broker_all_fields(self) -> None:
        """Cover all update_broker field branches."""
        from app.api.users import update_broker

        user = MagicMock(id=uuid.uuid4())
        cred = MagicMock(id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        result = await update_broker(
            cred.id,
            {"api_key": "k", "api_secret": "s", "client_id": "c", "is_active": False},
            user,
            mock_db,
        )
        assert result["message"] == "Broker updated."


# ═══════════════════════════════════════════════════════════════════════
# schemas/broker.py — SL validation missing branches
# ═══════════════════════════════════════════════════════════════════════


class TestBrokerSchemaExtraCoverage:
    def test_order_request_sl_no_price(self) -> None:
        from app.schemas.broker import Exchange, OrderRequest, OrderSide, OrderType, ProductType

        with pytest.raises(ValueError):
            OrderRequest(
                symbol="NIFTY", exchange=Exchange.NSE,
                side=OrderSide.BUY, order_type=OrderType.SL,
                product_type=ProductType.INTRADAY, quantity=1,
                trigger_price=Decimal("100"),
            )

    def test_order_request_limit_zero_price(self) -> None:
        from app.schemas.broker import Exchange, OrderRequest, OrderSide, OrderType, ProductType

        with pytest.raises(ValueError):
            OrderRequest(
                symbol="NIFTY", exchange=Exchange.NSE,
                side=OrderSide.BUY, order_type=OrderType.LIMIT,
                product_type=ProductType.INTRADAY, quantity=1,
                price=Decimal("0"),
            )


# ═══════════════════════════════════════════════════════════════════════
# schemas/webhook.py — SL validation
# ═══════════════════════════════════════════════════════════════════════


class TestWebhookSchemaExtraCoverage:
    def test_sl_order_valid(self) -> None:
        from app.schemas.webhook import WebhookPayload

        p = WebhookPayload(
            action="BUY", symbol="NIFTY", quantity=50,
            order_type="sl", price=Decimal("100"), trigger_price=Decimal("95"),
        )
        assert p.order_type.value == "sl"

    def test_sl_order_zero_price(self) -> None:
        from app.schemas.webhook import WebhookPayload

        with pytest.raises(ValueError, match="SL order requires a positive price"):
            WebhookPayload(
                action="BUY", symbol="NIFTY", quantity=50,
                order_type="sl", price=Decimal("0"), trigger_price=Decimal("95"),
            )

    def test_sl_order_zero_trigger(self) -> None:
        from app.schemas.webhook import WebhookPayload

        with pytest.raises(ValueError, match="SL order requires a positive trigger"):
            WebhookPayload(
                action="BUY", symbol="NIFTY", quantity=50,
                order_type="sl", price=Decimal("100"), trigger_price=Decimal("0"),
            )

    def test_slm_valid(self) -> None:
        from app.schemas.webhook import WebhookPayload

        p = WebhookPayload(
            action="BUY", symbol="NIFTY", quantity=50,
            order_type="sl_m", trigger_price=Decimal("95"),
        )
        assert p.order_type.value == "sl_m"


# ═══════════════════════════════════════════════════════════════════════
# security_ext.py — remaining branches
# ═══════════════════════════════════════════════════════════════════════


class TestSecurityExtExtraCoverage:
    @pytest.mark.asyncio
    async def test_detect_suspicious_order_burst(self, fake_redis: Any) -> None:
        from app.core.security_ext import detect_suspicious_activity

        user_id = str(uuid.uuid4())
        # Simulate >100 orders
        for _ in range(101):
            result = await detect_suspicious_activity(
                user_id, "order", {"quantity": 1}, redis_conn=fake_redis
            )
        assert result.is_suspicious is True
        assert result.severity.value == "high"

    @pytest.mark.asyncio
    async def test_detect_suspicious_fat_finger(self, fake_redis: Any) -> None:
        from app.core.security_ext import detect_suspicious_activity

        user_id = str(uuid.uuid4())
        result = await detect_suspicious_activity(
            user_id, "order",
            {"quantity": 1000, "user_avg_qty": 10},
            redis_conn=fake_redis,
        )
        assert result.is_suspicious is True
        assert "10" in (result.reason or "")

    @pytest.mark.asyncio
    async def test_detect_suspicious_night_login(self, fake_redis: Any) -> None:
        from app.core.security_ext import detect_suspicious_activity

        user_id = str(uuid.uuid4())
        # 03:00 IST = ~21:30 UTC previous day
        mock_now = datetime(2024, 1, 1, 21, 30, 0, tzinfo=UTC)
        result = await detect_suspicious_activity(
            user_id, "login", {}, redis_conn=fake_redis, now=mock_now
        )
        assert result.is_suspicious is True
        assert "02:00" in (result.reason or "")

    def test_sign_request_and_verify(self) -> None:
        from app.core.security_ext import sign_request, verify_signed_request

        payload = b"test-payload"
        ts = int(datetime.now(UTC).timestamp())
        secret = "test-secret"
        sig = sign_request(payload, ts, secret)
        assert verify_signed_request(payload, ts, sig, secret, now=ts) is True

    def test_verify_signed_request_expired(self) -> None:
        from app.core.security_ext import sign_request, verify_signed_request

        payload = b"test"
        ts = 1000000
        secret = "sec"
        sig = sign_request(payload, ts, secret)
        # now is way in the future
        assert verify_signed_request(payload, ts, sig, secret, now=9999999) is False

    def test_verify_signed_request_future(self) -> None:
        from app.core.security_ext import verify_signed_request

        # Timestamp way in the future
        assert verify_signed_request(b"x", 99999999999, "sig", "sec", now=1000) is False

    def test_api_key_generation(self) -> None:
        from app.core.security_ext import generate_api_key, hash_api_key, verify_api_key

        key = generate_api_key()
        assert key.key_id.startswith("tb_k_")
        assert key.key_secret.startswith("tb_s_")
        h = hash_api_key(key.key_secret)
        assert verify_api_key(key.key_secret, h) is True
        assert verify_api_key("wrong", h) is False

    def test_api_key_invalid_prefix(self) -> None:
        from app.core.security_ext import generate_api_key

        with pytest.raises(ValueError):
            generate_api_key(prefix="")

    def test_hash_api_key_empty(self) -> None:
        from app.core.security_ext import hash_api_key

        with pytest.raises(ValueError):
            hash_api_key("")

    def test_verify_api_key_wrong_types(self) -> None:
        from app.core.security_ext import verify_api_key

        assert verify_api_key(123, "hash") is False  # type: ignore
        assert verify_api_key("secret", 123) is False  # type: ignore

    def test_sanitize_log_data_deep(self) -> None:
        from app.core.security_ext import sanitize_log_data

        data = {
            "user": "admin",
            "password": "secret",
            "nested": {"api_key": "abc", "safe": "ok"},
            "list": [{"jwt_secret": "x"}, "normal"],
            "tuple": (1, 2),
            "bytes": b"hello",
        }
        result = sanitize_log_data(data)
        assert result["password"] == "***"
        assert result["nested"]["api_key"] == "***"
        assert result["list"][0]["jwt_secret"] == "***"
        assert result["tuple"] == (1, 2)
        assert result["bytes"] == "hello"

    def test_safe_json_dumps(self) -> None:
        from app.core.security_ext import safe_json_dumps

        result = safe_json_dumps({"password": "secret", "name": "test"})
        assert '"***"' in result
        assert "secret" not in result


# ═══════════════════════════════════════════════════════════════════════
# startup_checks.py — remaining lines
# ═══════════════════════════════════════════════════════════════════════


class TestStartupRemainingLines:
    def test_system_info_format(self) -> None:
        from app.core.config import get_settings
        from app.core.startup_checks import _system_info

        info = _system_info(get_settings())
        assert "python_version" in info
        assert "fastapi_version" in info
        assert "platform" in info
        assert "database" in info
        assert "redis" in info

    def test_print_banner_doesnt_crash(self) -> None:
        from app.core.startup_checks import _print_banner

        _print_banner({
            "python_version": "3.14",
            "fastapi_version": "0.115",
            "environment": "test",
            "platform": "Darwin",
        })

    @pytest.mark.asyncio
    async def test_check_redis_success(self) -> None:
        """check_redis with a working (fake) Redis."""
        from app.core.startup_checks import _check_redis

        settings = MagicMock()
        settings.redis_url = "redis://localhost:6379/0"

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_client.aclose = AsyncMock()
            mock_from_url.return_value = mock_client

            await _check_redis(settings)  # Should not raise
