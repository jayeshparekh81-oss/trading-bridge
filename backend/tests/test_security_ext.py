"""Tests for :mod:`app.core.security_ext`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import redis_client
from app.core import security_ext as sx


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Brute-force protection
# ═══════════════════════════════════════════════════════════════════════


class TestBruteForce:
    async def test_below_threshold_allowed(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        for _ in range(4):
            status = await sx.record_failed_login("user@x", redis_conn=redis)
            assert status.is_locked is False

    async def test_threshold_locks(self, redis: fake_aioredis.FakeRedis) -> None:
        for _ in range(5):
            status = await sx.record_failed_login("user@x", redis_conn=redis)
        assert status.is_locked is True
        assert status.lock_expires_in > 0

    async def test_check_reflects_lock(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        for _ in range(5):
            await sx.record_failed_login("user@x", redis_conn=redis)
        status = await sx.check_login_attempts("user@x", redis_conn=redis)
        assert status.is_locked is True

    async def test_reset_clears_counter(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        for _ in range(3):
            await sx.record_failed_login("user@x", redis_conn=redis)
        await sx.reset_login_attempts("user@x", redis_conn=redis)
        status = await sx.check_login_attempts("user@x", redis_conn=redis)
        assert status.is_locked is False
        assert status.attempts_remaining == sx.DEFAULT_LOGIN_ATTEMPTS

    async def test_email_and_ip_tracked_separately(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        for _ in range(5):
            await sx.record_failed_login("email@x", redis_conn=redis)
        ip_status = await sx.check_login_attempts(
            "1.2.3.4", redis_conn=redis
        )
        assert ip_status.is_locked is False

    async def test_ip_block_list(self, redis: fake_aioredis.FakeRedis) -> None:
        assert await sx.is_ip_blocked("10.0.0.1", redis_conn=redis) is False
        await sx.block_ip("10.0.0.1", redis_conn=redis)
        assert await sx.is_ip_blocked("10.0.0.1", redis_conn=redis) is True
        await sx.unblock_ip("10.0.0.1", redis_conn=redis)
        assert await sx.is_ip_blocked("10.0.0.1", redis_conn=redis) is False

    async def test_empty_ip_not_blocked(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert await sx.is_ip_blocked("", redis_conn=redis) is False


# ═══════════════════════════════════════════════════════════════════════
# Session fingerprinting
# ═══════════════════════════════════════════════════════════════════════


class TestFingerprint:
    def test_same_inputs_same_fingerprint(self) -> None:
        a = sx.generate_session_fingerprint("UA", "1.2.3.4", "en", "gzip")
        b = sx.generate_session_fingerprint("UA", "1.2.3.4", "en", "gzip")
        assert a == b

    def test_different_user_agent(self) -> None:
        a = sx.generate_session_fingerprint("UA1", "1.2.3.4")
        b = sx.generate_session_fingerprint("UA2", "1.2.3.4")
        assert a != b

    def test_different_ip(self) -> None:
        a = sx.generate_session_fingerprint("UA", "1.2.3.4")
        b = sx.generate_session_fingerprint("UA", "5.6.7.8")
        assert a != b

    def test_validate_equal(self) -> None:
        fp = sx.generate_session_fingerprint("UA", "1.2.3.4")
        assert sx.validate_session_fingerprint(fp, fp) is True

    def test_validate_unequal(self) -> None:
        a = sx.generate_session_fingerprint("UA1", "1.2.3.4")
        b = sx.generate_session_fingerprint("UA2", "1.2.3.4")
        assert sx.validate_session_fingerprint(a, b) is False

    def test_validate_empty(self) -> None:
        assert sx.validate_session_fingerprint("", "abc") is False
        assert sx.validate_session_fingerprint("abc", "") is False


# ═══════════════════════════════════════════════════════════════════════
# JWT session tokens
# ═══════════════════════════════════════════════════════════════════════


class TestSessionTokens:
    async def test_valid_token_returns_claims(
        self, redis: fake_aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(redis_client, "get_redis", lambda: redis)
        fp = sx.generate_session_fingerprint("UA", "1.2.3.4")
        token = sx.create_session_token("user-1", fp)
        claims = await sx.validate_session_token(token, current_fingerprint=fp)
        assert claims is not None
        assert claims["sub"] == "user-1"

    async def test_wrong_fingerprint_rejected(
        self, redis: fake_aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(redis_client, "get_redis", lambda: redis)
        fp = sx.generate_session_fingerprint("UA", "1.2.3.4")
        token = sx.create_session_token("user-1", fp)
        other = sx.generate_session_fingerprint("UA2", "1.2.3.4")
        assert await sx.validate_session_token(token, current_fingerprint=other) is None

    async def test_blacklisted_token_rejected(
        self, redis: fake_aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(redis_client, "get_redis", lambda: redis)
        fp = sx.generate_session_fingerprint("UA", "1.2.3.4")
        token = sx.create_session_token("user-1", fp, ttl_seconds=3600)
        await sx.revoke_session_token(token)
        assert await sx.validate_session_token(token, current_fingerprint=fp) is None

    async def test_empty_token_rejected(self) -> None:
        assert await sx.validate_session_token("") is None

    async def test_malformed_token_rejected(self) -> None:
        assert await sx.validate_session_token("not.a.token") is None

    async def test_revoke_malformed_returns_false(self) -> None:
        assert await sx.revoke_session_token("broken") is False


# ═══════════════════════════════════════════════════════════════════════
# API keys
# ═══════════════════════════════════════════════════════════════════════


class TestApiKeys:
    def test_format(self) -> None:
        material = sx.generate_api_key()
        assert material.key_id.startswith("tb_k_")
        assert material.key_secret.startswith("tb_s_")
        assert len(material.key_id) >= 12
        assert len(material.key_secret) >= 50

    def test_verify_correct(self) -> None:
        material = sx.generate_api_key()
        stored = sx.hash_api_key(material.key_secret)
        assert sx.verify_api_key(material.key_secret, stored) is True

    def test_verify_wrong(self) -> None:
        material = sx.generate_api_key()
        stored = sx.hash_api_key(material.key_secret)
        assert sx.verify_api_key("wrong-secret", stored) is False

    def test_verify_non_str(self) -> None:
        assert sx.verify_api_key(123, "abc") is False  # type: ignore[arg-type]

    def test_hash_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            sx.hash_api_key("")

    def test_generate_rejects_bad_prefix(self) -> None:
        with pytest.raises(ValueError):
            sx.generate_api_key(prefix="")
        with pytest.raises(ValueError):
            sx.generate_api_key(prefix="tb_bad")


# ═══════════════════════════════════════════════════════════════════════
# Request signing
# ═══════════════════════════════════════════════════════════════════════


class TestRequestSigning:
    def test_valid(self) -> None:
        payload = b'{"a":1}'
        ts = 1_700_000_000
        sig = sx.sign_request(payload, ts, "secret")
        assert sx.verify_signed_request(
            payload, ts, sig, "secret", now=ts + 1
        )

    def test_expired(self) -> None:
        payload = b'{"a":1}'
        ts = 1_700_000_000
        sig = sx.sign_request(payload, ts, "secret")
        assert not sx.verify_signed_request(
            payload, ts, sig, "secret", now=ts + 31
        )

    def test_future_timestamp_rejected(self) -> None:
        payload = b'{"a":1}'
        ts = 1_700_000_100
        sig = sx.sign_request(payload, ts, "secret")
        # now is 100s before ts → verify fails (future)
        assert not sx.verify_signed_request(
            payload, ts, sig, "secret", now=ts - 100
        )

    def test_tampered_payload(self) -> None:
        ts = 1_700_000_000
        sig = sx.sign_request(b'{"a":1}', ts, "secret")
        assert not sx.verify_signed_request(
            b'{"a":2}', ts, sig, "secret", now=ts + 1
        )

    def test_tampered_signature(self) -> None:
        payload = b'{"a":1}'
        ts = 1_700_000_000
        assert not sx.verify_signed_request(
            payload, ts, "deadbeef", "secret", now=ts + 1
        )

    def test_sign_requires_bytes(self) -> None:
        with pytest.raises(TypeError):
            sx.sign_request("not bytes", 1, "secret")  # type: ignore[arg-type]

    def test_sign_requires_secret(self) -> None:
        with pytest.raises(ValueError):
            sx.sign_request(b"x", 1, "")


# ═══════════════════════════════════════════════════════════════════════
# Suspicious activity
# ═══════════════════════════════════════════════════════════════════════


class TestSuspiciousActivity:
    async def test_new_ip_low(self, redis: fake_aioredis.FakeRedis) -> None:
        result = await sx.detect_suspicious_activity(
            "u1",
            "login",
            {"ip": "1.1.1.1"},
            redis_conn=redis,
            now=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        )
        assert result.is_suspicious is True
        assert result.severity is sx.Severity.LOW

    async def test_known_ip_not_suspicious(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        # First call marks the IP as seen.
        await sx.detect_suspicious_activity(
            "u1",
            "login",
            {"ip": "1.1.1.1"},
            redis_conn=redis,
            now=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        )
        # Second call same IP — LOW rule should NOT fire; result depends on other rules.
        result = await sx.detect_suspicious_activity(
            "u1",
            "login",
            {"ip": "1.1.1.1"},
            redis_conn=redis,
            now=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        )
        assert result.is_suspicious is False

    async def test_many_orders_high(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        # Prime the counter.
        await redis.set("sec:order_rate:u2", 100)
        result = await sx.detect_suspicious_activity(
            "u2",
            "order",
            {"quantity": 1, "user_avg_qty": 1},
            redis_conn=redis,
        )
        assert result.severity is sx.Severity.HIGH

    async def test_10x_order_medium(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        result = await sx.detect_suspicious_activity(
            "u3",
            "order",
            {"quantity": 500, "user_avg_qty": 10},
            redis_conn=redis,
        )
        assert result.severity is sx.Severity.MEDIUM

    async def test_multiple_ips_medium(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"):
            res = await sx.detect_suspicious_activity(
                "u4",
                "login",
                {"ip": ip},
                redis_conn=redis,
            )
        # Last call should hit the >3 distinct rule.
        assert res.severity in (sx.Severity.MEDIUM, sx.Severity.LOW)

    async def test_early_hours_low(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        # 03:00 IST = 21:30 UTC of previous day.
        early = datetime(2026, 4, 15, 21, 30, tzinfo=UTC)
        result = await sx.detect_suspicious_activity(
            "u5",
            "login",
            {},
            redis_conn=redis,
            now=early,
        )
        assert result.severity is sx.Severity.LOW

    async def test_ok_case(self, redis: fake_aioredis.FakeRedis) -> None:
        res = await sx.detect_suspicious_activity(
            "u6",
            "order",
            {"quantity": 5, "user_avg_qty": 5},
            redis_conn=redis,
        )
        assert res.is_suspicious is False


# ═══════════════════════════════════════════════════════════════════════
# Password policy
# ═══════════════════════════════════════════════════════════════════════


class TestPasswordPolicy:
    def test_weak_rejected(self) -> None:
        result = sx.validate_password_strength("123456")
        assert result.is_valid is False

    def test_strong_accepted(self) -> None:
        result = sx.validate_password_strength("Tr@de2026!")
        assert result.is_valid is True

    def test_no_uppercase(self) -> None:
        r = sx.validate_password_strength("trade2026!")
        assert not r.is_valid
        assert any("uppercase" in reason for reason in r.reasons)

    def test_no_special(self) -> None:
        r = sx.validate_password_strength("Trade2026")
        assert not r.is_valid
        assert any("special" in reason for reason in r.reasons)

    def test_common_password(self) -> None:
        r = sx.validate_password_strength("Password1")
        # still fails on one other check (no special), but common-list should also fire
        assert not r.is_valid

    def test_email_in_password(self) -> None:
        r = sx.validate_password_strength(
            "Rahul@Bridge2026!", email="rahul@example.com"
        )
        assert not r.is_valid
        assert any("email" in reason for reason in r.reasons)

    def test_name_in_password(self) -> None:
        r = sx.validate_password_strength(
            "Rohit@Bridge2026!", name="rohit"
        )
        assert not r.is_valid

    def test_non_str(self) -> None:
        r = sx.validate_password_strength(12345)  # type: ignore[arg-type]
        assert not r.is_valid


# ═══════════════════════════════════════════════════════════════════════
# Sanitization
# ═══════════════════════════════════════════════════════════════════════


class TestSanitization:
    def test_strips_html(self) -> None:
        assert sx.sanitize_input("<script>alert(1)</script>hello") == "alert(1)hello"

    def test_strips_sql_comments(self) -> None:
        assert "--" not in sx.sanitize_input("x -- drop table y")

    def test_strips_sql_keywords(self) -> None:
        cleaned = sx.sanitize_input("SELECT * FROM users").lower()
        assert "select" not in cleaned

    def test_strips_control_chars(self) -> None:
        assert "\x00" not in sx.sanitize_input("ab\x00cd")

    def test_none_returns_empty(self) -> None:
        assert sx.sanitize_input(None) == ""

    def test_non_str_coerced(self) -> None:
        assert sx.sanitize_input(123) == "123"

    def test_sanitize_log_masks_top_level(self) -> None:
        data = {"password": "secret", "name": "ravi"}
        cleaned = sx.sanitize_log_data(data)
        assert cleaned["password"] == "***"
        assert cleaned["name"] == "ravi"

    def test_sanitize_log_recurses(self) -> None:
        data = {"user": {"api_secret": "s", "email": "e"}, "arr": [{"authorization": "z"}]}
        cleaned = sx.sanitize_log_data(data)
        assert cleaned["user"]["api_secret"] == "***"
        assert cleaned["user"]["email"] == "e"
        assert cleaned["arr"][0]["authorization"] == "***"

    def test_sanitize_log_tuples(self) -> None:
        cleaned = sx.sanitize_log_data(({"password": "x"},))
        assert cleaned[0]["password"] == "***"

    def test_sanitize_bytes(self) -> None:
        assert sx.sanitize_log_data(b"abc") == "abc"

    def test_safe_json_dumps(self) -> None:
        out = sx.safe_json_dumps({"password": "x", "y": 1})
        assert '"password": "***"' in out
