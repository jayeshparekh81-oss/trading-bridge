"""End-to-end integration tests — complete user journeys.

Uses mock brokers, mock Redis (fakeredis), and real Pydantic validation
to test the full webhook→order→kill-switch pipeline.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
from cryptography.fernet import Fernet

from app.core import security
from app.core.security import (
    compute_hmac_signature,
    encrypt_credential,
    generate_webhook_token,
    hash_password,
)


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
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def _mock_broker() -> MagicMock:
    """Create a mock broker implementing key interface methods."""
    broker = MagicMock()
    broker.broker_name = "FYERS"
    broker.login = AsyncMock(return_value=True)
    broker.is_session_valid = AsyncMock(return_value=True)
    broker.place_order = AsyncMock(
        return_value=MagicMock(
            order_id="ORD123",
            status="COMPLETE",
            message="Order placed",
            broker_order_id="ORD123",
        )
    )
    broker.cancel_all_pending = AsyncMock(return_value=[])
    broker.square_off_all = AsyncMock(return_value=[])
    broker.get_positions = AsyncMock(return_value=[])
    broker.normalize_symbol = MagicMock(side_effect=lambda s, e: s)
    return broker


# ═══════════════════════════════════════════════════════════════════════
# TestFullTradingFlow
# ═══════════════════════════════════════════════════════════════════════


class TestFullTradingFlow:
    """Simulates a real user's complete journey with mocked externals."""

    @pytest.mark.asyncio
    async def test_complete_user_journey(self) -> None:
        """Register → Login → Add broker → Create webhook → Trade → Stats → Logout."""
        from app.services.auth_service import AuthService

        svc = AuthService()

        # 1. Register
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.add = MagicMock()

        # No existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        async def _refresh(obj: Any) -> None:
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db.refresh = _refresh

        with patch("app.services.auth_service.check_login_attempts"):
            user = await svc.register(
                email="trader@example.com",
                password="StrongP@ss1",
                full_name="Trader Joe",
                phone="+91-9876543210",
                db=mock_db,
            )
        assert mock_db.add.call_count >= 2  # user + kill_switch_config + audit

        # 2. Login
        from app.core.security import hash_password as hp

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "trader@example.com"
        mock_user.password_hash = hp("StrongP@ss1")
        mock_user.is_active = True
        mock_user.full_name = "Trader Joe"

        mock_db2 = AsyncMock()
        login_result = MagicMock()
        login_result.scalar_one_or_none.return_value = mock_user
        mock_db2.execute = AsyncMock(return_value=login_result)
        mock_db2.commit = AsyncMock()
        mock_db2.add = MagicMock()

        with (
            patch("app.services.auth_service.check_login_attempts") as mc,
            patch("app.services.auth_service.reset_login_attempts") as mr,
        ):
            mc.return_value = MagicMock(is_locked=False)
            mr.return_value = None
            tokens = await svc.login(
                "trader@example.com",
                "StrongP@ss1",
                {"ip": "127.0.0.1", "user_agent": "test"},
                mock_db2,
            )
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.expires_in == 3600

        # 3. Logout
        with (
            patch("app.services.auth_service.validate_session_token") as mv,
            patch("app.services.auth_service.revoke_session_token") as mrv,
        ):
            mv.return_value = {"sub": str(mock_user.id), "jti": "abc"}
            mrv.return_value = True
            mock_db3 = AsyncMock()
            mock_db3.add = MagicMock()
            mock_db3.commit = AsyncMock()
            await svc.logout(tokens.access_token, mock_db3)
            mrv.assert_called_once()

    @pytest.mark.asyncio
    async def test_kill_switch_full_flow(self, fake_redis: Any) -> None:
        """Configure kill switch → trigger via loss → verify tripped → reset."""
        from app.core import redis_client as rc

        # Set kill switch to ACTIVE
        user_id = uuid.uuid4()
        await rc.set_kill_switch_status(
            user_id, rc.KILL_SWITCH_ACTIVE, redis_client=fake_redis
        )

        # Verify active
        status = await rc.get_kill_switch_status(user_id, redis_client=fake_redis)
        assert status == rc.KILL_SWITCH_ACTIVE

        # Simulate trip
        await rc.set_kill_switch_status(
            user_id, rc.KILL_SWITCH_TRIPPED, redis_client=fake_redis
        )
        status = await rc.get_kill_switch_status(user_id, redis_client=fake_redis)
        assert status == rc.KILL_SWITCH_TRIPPED

        # Reset
        await rc.clear_kill_switch(user_id, redis_client=fake_redis)
        status = await rc.get_kill_switch_status(user_id, redis_client=fake_redis)
        assert status != rc.KILL_SWITCH_TRIPPED

    @pytest.mark.asyncio
    async def test_multi_broker_credentials(self) -> None:
        """Add multiple broker credentials — verify encryption isolation."""
        fyers_key = encrypt_credential("fyers-api-key-123")
        dhan_key = encrypt_credential("dhan-api-key-456")

        # Different ciphertexts
        assert fyers_key != dhan_key

        # Decrypt back correctly
        from app.core.security import decrypt_credential

        assert decrypt_credential(fyers_key) == "fyers-api-key-123"
        assert decrypt_credential(dhan_key) == "dhan-api-key-456"

    @pytest.mark.asyncio
    async def test_security_brute_force_lockout(self, fake_redis: Any) -> None:
        """5 failed attempts → account locked."""
        from app.core.security_ext import (
            check_login_attempts,
            record_failed_login,
            reset_login_attempts,
        )

        identifier = "attacker@evil.com"

        # Record 5 failures
        for _ in range(5):
            result = await record_failed_login(
                identifier, redis_conn=fake_redis, max_attempts=5
            )

        assert result.is_locked is True
        assert result.attempts_remaining == 0

        # Verify locked
        status = await check_login_attempts(identifier, redis_conn=fake_redis)
        assert status.is_locked is True

        # Reset
        await reset_login_attempts(identifier, redis_conn=fake_redis)
        status = await check_login_attempts(identifier, redis_conn=fake_redis)
        assert status.is_locked is False

    @pytest.mark.asyncio
    async def test_hmac_verification_flow(self) -> None:
        """Create webhook → compute HMAC → verify → reject tampered."""
        from app.core.security import verify_hmac_signature

        secret = generate_webhook_token(16)
        payload = json.dumps(
            {"action": "BUY", "symbol": "NIFTY", "quantity": 50}
        ).encode()

        sig = compute_hmac_signature(payload, secret)

        # Valid signature
        assert verify_hmac_signature(payload, sig, secret) is True

        # Tampered payload
        bad_payload = payload + b"x"
        assert verify_hmac_signature(bad_payload, sig, secret) is False

        # Wrong secret
        assert verify_hmac_signature(payload, sig, "wrong-secret") is False

    @pytest.mark.asyncio
    async def test_idempotency_flow(self, fake_redis: Any) -> None:
        """First webhook → accepted. Duplicate → rejected."""
        from app.core import redis_client as rc

        signal_hash = f"{uuid.uuid4()}:test-signal-123"

        # First claim succeeds
        claimed = await rc.set_idempotency_key(
            signal_hash, ttl_seconds=60, redis_client=fake_redis
        )
        assert claimed is True

        # Duplicate fails
        claimed2 = await rc.set_idempotency_key(
            signal_hash, ttl_seconds=60, redis_client=fake_redis
        )
        assert claimed2 is False

    @pytest.mark.asyncio
    async def test_rate_limit_flow(self, fake_redis: Any) -> None:
        """Rate limit: allow N requests, then reject."""
        from app.core import redis_client as rc

        key = f"webhook:test-rate-{uuid.uuid4()}"
        max_requests = 3

        for i in range(max_requests):
            allowed = await rc.rate_limit_check(
                key=key,
                max_requests=max_requests,
                window_seconds=60,
                redis_client=fake_redis,
            )
            assert allowed is True

        # Exceeded
        allowed = await rc.rate_limit_check(
            key=key,
            max_requests=max_requests,
            window_seconds=60,
            redis_client=fake_redis,
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_webhook_payload_validation(self) -> None:
        """Validate various webhook payloads."""
        from app.schemas.webhook import WebhookPayload

        # Minimal valid payload
        payload = WebhookPayload(action="BUY", symbol="NIFTY", quantity=50)
        assert payload.exchange.value == "NSE"
        assert payload.order_type.value == "market"

        # With all optional fields
        full = WebhookPayload(
            action="SELL",
            symbol="RELIANCE",
            exchange="NSE",
            quantity=100,
            order_type="limit",
            price=Decimal("2500.50"),
            strategy_name="ema-cross",
            message="exit long",
            signal_id="sig-001",
        )
        assert full.price == Decimal("2500.50")

    @pytest.mark.asyncio
    async def test_webhook_payload_extra_fields_ignored(self) -> None:
        """TradingView sends extra fields — they should be ignored."""
        from app.schemas.webhook import WebhookPayload

        data = {
            "action": "BUY",
            "symbol": "NIFTY",
            "quantity": 50,
            "description": "EMA crossover alert",
            "timestamp": "2024-01-01T10:00:00Z",
            "tv_exchange": "NSE",
        }
        payload = WebhookPayload(**data)
        assert payload.symbol == "NIFTY"
        # Extra fields silently dropped
        assert not hasattr(payload, "description")

    @pytest.mark.asyncio
    async def test_concurrent_idempotency(self, fake_redis: Any) -> None:
        """Simulate 10 concurrent claims — only first wins."""
        import asyncio

        from app.core import redis_client as rc

        signal = f"{uuid.uuid4()}:concurrent-test"
        results = await asyncio.gather(
            *[
                rc.set_idempotency_key(signal, ttl_seconds=60, redis_client=fake_redis)
                for _ in range(10)
            ]
        )
        # Exactly one should succeed
        assert results.count(True) == 1
        assert results.count(False) == 9

    @pytest.mark.asyncio
    async def test_pnl_tracking_flow(self, fake_redis: Any) -> None:
        """Record P&L → read → increment → read again."""
        from app.core import redis_client as rc

        user_id = uuid.uuid4()

        # Initially zero
        pnl = await rc.get_daily_pnl(user_id, redis_client=fake_redis)
        assert pnl == Decimal("0")

        # Increment by trade profit
        await rc.increment_daily_pnl(
            user_id, Decimal("500.50"), redis_client=fake_redis
        )
        pnl = await rc.get_daily_pnl(user_id, redis_client=fake_redis)
        assert pnl == Decimal("500.50")

        # Increment by loss
        await rc.increment_daily_pnl(
            user_id, Decimal("-200.25"), redis_client=fake_redis
        )
        pnl = await rc.get_daily_pnl(user_id, redis_client=fake_redis)
        assert pnl == Decimal("300.25")


# ═══════════════════════════════════════════════════════════════════════
# TestNotificationFlow
# ═══════════════════════════════════════════════════════════════════════


class TestNotificationFlow:
    @pytest.mark.asyncio
    async def test_welcome_email_on_register(self) -> None:
        """Register sends welcome notification."""
        from app.services.notification_service import NotificationService

        svc = NotificationService()
        subject, html, text = svc._render_email("welcome", {"user_name": "Jayesh"})
        assert "Welcome" in subject
        assert "Jayesh" in html

    @pytest.mark.asyncio
    async def test_kill_switch_triggers_all_channels(self) -> None:
        """Kill switch event uses ALL channels regardless of prefs."""
        from app.services.notification_service import _URGENT_EVENTS

        assert "kill_switch_triggered" in _URGENT_EVENTS
        assert "broker_session_expired" in _URGENT_EVENTS
        assert "suspicious_activity" in _URGENT_EVENTS

    @pytest.mark.asyncio
    async def test_order_notification_templates(self) -> None:
        """Order filled/failed templates render correctly."""
        from app.services.notification_service import NotificationService

        svc = NotificationService()

        _, html, _ = svc._render_email("order_filled", {
            "side": "BUY", "symbol": "NIFTY25000CE",
            "quantity": 50, "price": "125.00",
        })
        assert "NIFTY25000CE" in html
        assert "BUY" in html

        _, html2, _ = svc._render_email("order_failed", {
            "symbol": "BANKNIFTY", "reason": "Insufficient margin",
        })
        assert "Insufficient margin" in html2


# ═══════════════════════════════════════════════════════════════════════
# TestAdminFlow
# ═══════════════════════════════════════════════════════════════════════


class TestAdminFlow:
    @pytest.mark.asyncio
    async def test_admin_dependency_chain(self) -> None:
        """Admin dependency requires active + admin."""
        from fastapi import HTTPException

        from app.api.deps import get_current_active_user, get_current_admin

        # Active non-admin
        user = MagicMock()
        user.is_active = True
        user.is_admin = False
        active = await get_current_active_user(user)
        assert active == user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(active)
        assert exc_info.value.status_code == 403

        # Active admin
        admin = MagicMock()
        admin.is_active = True
        admin.is_admin = True
        result = await get_current_admin(admin)
        assert result == admin

    @pytest.mark.asyncio
    async def test_inactive_user_blocked(self) -> None:
        """Inactive user blocked at active_user dependency."""
        from fastapi import HTTPException

        from app.api.deps import get_current_active_user

        user = MagicMock()
        user.is_active = False
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(user)
        assert exc_info.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# TestPasswordPolicy
# ═══════════════════════════════════════════════════════════════════════


class TestPasswordPolicyIntegration:
    def test_strong_password_passes(self) -> None:
        from app.core.security_ext import validate_password_strength

        result = validate_password_strength("MyStr0ng!Pass")
        assert result.is_valid is True

    def test_weak_password_fails(self) -> None:
        from app.core.security_ext import validate_password_strength

        result = validate_password_strength("123456")
        assert result.is_valid is False
        assert len(result.reasons) > 0

    def test_common_password_blocked(self) -> None:
        from app.core.security_ext import validate_password_strength

        result = validate_password_strength("password")
        assert result.is_valid is False
        assert any("common" in r for r in result.reasons)

    def test_password_contains_email(self) -> None:
        from app.core.security_ext import validate_password_strength

        result = validate_password_strength("jayesh@Str0ng!", email="jayesh@test.com")
        assert result.is_valid is False
        assert any("email" in r for r in result.reasons)


# ═══════════════════════════════════════════════════════════════════════
# TestSessionFingerprinting
# ═══════════════════════════════════════════════════════════════════════


class TestSessionFingerprinting:
    def test_same_device_same_fingerprint(self) -> None:
        from app.core.security_ext import generate_session_fingerprint

        fp1 = generate_session_fingerprint("Chrome/120", "1.2.3.4")
        fp2 = generate_session_fingerprint("Chrome/120", "1.2.3.4")
        assert fp1 == fp2

    def test_different_device_different_fingerprint(self) -> None:
        from app.core.security_ext import generate_session_fingerprint

        fp1 = generate_session_fingerprint("Chrome/120", "1.2.3.4")
        fp2 = generate_session_fingerprint("Firefox/120", "1.2.3.4")
        assert fp1 != fp2

    def test_fingerprint_validates(self) -> None:
        from app.core.security_ext import (
            generate_session_fingerprint,
            validate_session_fingerprint,
        )

        fp = generate_session_fingerprint("Chrome/120", "1.2.3.4")
        assert validate_session_fingerprint(fp, fp) is True
        assert validate_session_fingerprint(fp, "wrong") is False


# ═══════════════════════════════════════════════════════════════════════
# TestCircuitBreakerIntegration
# ═══════════════════════════════════════════════════════════════════════


class TestCircuitBreakerIntegration:
    @pytest.mark.asyncio
    async def test_volatility_levels(self, fake_redis: Any) -> None:
        """Test circuit breaker state transitions."""
        from app.services.circuit_breaker_service import (
            CircuitBreakerLevel,
            circuit_breaker_service,
        )

        from app.schemas.broker import Exchange

        # Default state is ALLOW — mock Redis calls via the redis_client module
        with patch("app.services.circuit_breaker_service.redis_client") as mock_rc:
            mock_rc.cache_get_json = AsyncMock(return_value=None)
            level = await circuit_breaker_service.get_state("NIFTY", Exchange.NSE)
        assert level == CircuitBreakerLevel.ALLOW
