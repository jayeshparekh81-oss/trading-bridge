"""Extended security primitives built on top of :mod:`app.core.security`.

Split out to keep the original module focused on cryptographic basics
(Fernet, HMAC, bcrypt, token generation). Everything here is application-
level security policy: brute-force lockouts, session fingerprinting, API
keys, replay protection, suspicious-activity detection, password policy,
and data sanitization.

Each primitive is pure (takes inputs, returns outputs) except for the
Redis-backed state helpers which accept an explicit ``redis`` argument so
tests can pass a fake.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from jose import jwt
from jose.exceptions import JWTError

from app.core import redis_client
from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis


logger = get_logger("app.core.security_ext")


# ═══════════════════════════════════════════════════════════════════════
# Brute-force protection
# ═══════════════════════════════════════════════════════════════════════


DEFAULT_LOGIN_ATTEMPTS = 5
DEFAULT_LOGIN_WINDOW_MINUTES = 15
DEFAULT_LOCK_MINUTES = 60

_LOGIN_PREFIX = "login_attempts"
_LOGIN_LOCK_PREFIX = "login_lock"
_IP_BLOCK_KEY = "blocked_ips"


@dataclass
class LoginStatus:
    """Result of a brute-force lookup.

    ``attempts_remaining`` is clamped ≥ 0 even after overflow, so UIs can
    safely render it.
    """

    is_locked: bool
    attempts_remaining: int
    lock_expires_in: int  # seconds; 0 when not locked.


def _login_attempt_key(identifier: str) -> str:
    return f"{_LOGIN_PREFIX}:{identifier}"


def _login_lock_key(identifier: str) -> str:
    return f"{_LOGIN_LOCK_PREFIX}:{identifier}"


async def check_login_attempts(
    identifier: str,
    *,
    max_attempts: int = DEFAULT_LOGIN_ATTEMPTS,
    window_minutes: int = DEFAULT_LOGIN_WINDOW_MINUTES,
    lock_minutes: int = DEFAULT_LOCK_MINUTES,
    redis_conn: aioredis.Redis | None = None,
) -> LoginStatus:
    """Check if ``identifier`` (email or IP) is currently locked out."""
    client = redis_conn or redis_client.get_redis()
    lock_ttl = await client.ttl(_login_lock_key(identifier))
    if lock_ttl and lock_ttl > 0:
        return LoginStatus(
            is_locked=True, attempts_remaining=0, lock_expires_in=int(lock_ttl)
        )
    raw = await client.get(_login_attempt_key(identifier))
    attempts = int(raw) if raw else 0
    remaining = max(max_attempts - attempts, 0)
    return LoginStatus(
        is_locked=False, attempts_remaining=remaining, lock_expires_in=0
    )


async def record_failed_login(
    identifier: str,
    *,
    max_attempts: int = DEFAULT_LOGIN_ATTEMPTS,
    window_minutes: int = DEFAULT_LOGIN_WINDOW_MINUTES,
    lock_minutes: int = DEFAULT_LOCK_MINUTES,
    redis_conn: aioredis.Redis | None = None,
) -> LoginStatus:
    """Increment the failed-attempt counter and lock if threshold reached."""
    client = redis_conn or redis_client.get_redis()
    pipe = client.pipeline(transaction=False)
    pipe.incr(_login_attempt_key(identifier))
    pipe.expire(_login_attempt_key(identifier), window_minutes * 60)
    count, _ = await pipe.execute()
    count = int(count)
    if count >= max_attempts:
        await client.set(
            _login_lock_key(identifier), "1", ex=lock_minutes * 60
        )
        logger.warning("security.login_locked", identifier=identifier, count=count)
        return LoginStatus(
            is_locked=True,
            attempts_remaining=0,
            lock_expires_in=lock_minutes * 60,
        )
    return LoginStatus(
        is_locked=False,
        attempts_remaining=max(max_attempts - count, 0),
        lock_expires_in=0,
    )


async def reset_login_attempts(
    identifier: str, *, redis_conn: aioredis.Redis | None = None
) -> None:
    """Clear counter + lock on successful auth."""
    client = redis_conn or redis_client.get_redis()
    pipe = client.pipeline(transaction=False)
    pipe.delete(_login_attempt_key(identifier))
    pipe.delete(_login_lock_key(identifier))
    await pipe.execute()


async def is_ip_blocked(
    ip: str, *, redis_conn: aioredis.Redis | None = None
) -> bool:
    """Consult the global IP block list (admin-maintained)."""
    if not ip:
        return False
    client = redis_conn or redis_client.get_redis()
    return bool(await client.sismember(_IP_BLOCK_KEY, ip))


async def block_ip(
    ip: str, *, redis_conn: aioredis.Redis | None = None
) -> None:
    client = redis_conn or redis_client.get_redis()
    await client.sadd(_IP_BLOCK_KEY, ip)


async def unblock_ip(
    ip: str, *, redis_conn: aioredis.Redis | None = None
) -> None:
    client = redis_conn or redis_client.get_redis()
    await client.srem(_IP_BLOCK_KEY, ip)


# ═══════════════════════════════════════════════════════════════════════
# Session fingerprinting + JWT
# ═══════════════════════════════════════════════════════════════════════


_SESSION_BLACKLIST_PREFIX = "session_blacklist"


def generate_session_fingerprint(
    user_agent: str,
    ip: str,
    accept_language: str | None = None,
    accept_encoding: str | None = None,
) -> str:
    """Hash the set of device headers into a stable fingerprint.

    Using the full user-agent string means a browser upgrade will
    invalidate sessions — that's intentional: session bindings should be
    brittle so a stolen cookie in a different browser is worthless.
    """
    parts = [
        user_agent or "",
        ip or "",
        accept_language or "",
        accept_encoding or "",
    ]
    joined = "|".join(parts).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def validate_session_fingerprint(stored: str, current: str) -> bool:
    """Timing-safe comparison."""
    if not stored or not current:
        return False
    try:
        return hmac.compare_digest(stored, current)
    except (TypeError, AttributeError):
        return False


def create_session_token(
    user_id: str,
    fingerprint: str,
    *,
    ttl_seconds: int = 86400,
) -> str:
    """Issue a JWT with the fingerprint + expiry embedded.

    We embed ``fp`` rather than relying on a server-side mapping so
    stateless edges (CDN, reverse proxies) can validate the shape
    cheaply; Redis is only consulted for blacklist lookups.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "fp": fingerprint,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


async def validate_session_token(
    token: str,
    *,
    current_fingerprint: str | None = None,
    redis_conn: aioredis.Redis | None = None,
) -> dict[str, Any] | None:
    """Verify a JWT and return the decoded claims, else ``None``."""
    if not token:
        return None
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

    jti = claims.get("jti")
    if jti:
        client = redis_conn or redis_client.get_redis()
        if await client.exists(f"{_SESSION_BLACKLIST_PREFIX}:{jti}"):
            return None

    if current_fingerprint is not None:
        stored_fp = claims.get("fp", "")
        if not validate_session_fingerprint(stored_fp, current_fingerprint):
            return None
    return claims


async def revoke_session_token(
    token: str, *, redis_conn: aioredis.Redis | None = None
) -> bool:
    """Blacklist a JWT by its ``jti`` until expiry."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
    except JWTError:
        return False
    jti = claims.get("jti")
    exp = claims.get("exp")
    if not jti or not exp:
        return False
    ttl = int(exp) - int(datetime.now(UTC).timestamp())
    if ttl <= 0:
        return True  # already expired — nothing to blacklist
    client = redis_conn or redis_client.get_redis()
    await client.set(f"{_SESSION_BLACKLIST_PREFIX}:{jti}", "1", ex=ttl)
    return True


# ═══════════════════════════════════════════════════════════════════════
# API keys
# ═══════════════════════════════════════════════════════════════════════


API_KEY_PREFIX = "tb"


@dataclass(frozen=True)
class ApiKeyMaterial:
    """One generated API key pair."""

    key_id: str
    key_secret: str


def generate_api_key(prefix: str = API_KEY_PREFIX) -> ApiKeyMaterial:
    """Mint ``(key_id, key_secret)``.

    ``key_id`` is a short public identifier safe to log; ``key_secret``
    is only shown once at creation time. Both are url-safe.
    """
    if not prefix or not prefix.isalnum():
        raise ValueError("prefix must be non-empty alphanumeric")
    key_id = f"{prefix}_k_{secrets.token_hex(4)}"
    key_secret = f"{prefix}_s_{secrets.token_urlsafe(48)}"
    return ApiKeyMaterial(key_id=key_id, key_secret=key_secret)


def hash_api_key(secret: str) -> str:
    """SHA-256 — fast enough for every-request verification."""
    if not isinstance(secret, str) or not secret:
        raise ValueError("secret must be non-empty str")
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_api_key(secret: str, stored_hash: str) -> bool:
    """Timing-safe comparison of a raw secret against its stored hash."""
    if not isinstance(secret, str) or not isinstance(stored_hash, str):
        return False
    try:
        return hmac.compare_digest(hash_api_key(secret), stored_hash)
    except (TypeError, AttributeError, ValueError):
        return False


# ═══════════════════════════════════════════════════════════════════════
# Request signing (replay-resistant)
# ═══════════════════════════════════════════════════════════════════════


DEFAULT_REQUEST_MAX_AGE_SECONDS = 30


def sign_request(payload: bytes, timestamp: int, secret: str) -> str:
    """``HMAC-SHA256(f"{timestamp}.{payload}")`` as lowercase hex."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    if not isinstance(secret, str) or not secret:
        raise ValueError("secret must be non-empty str")
    msg = f"{int(timestamp)}.".encode("utf-8") + bytes(payload)
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_signed_request(
    payload: bytes,
    timestamp: int,
    signature: str,
    secret: str,
    *,
    max_age_seconds: int = DEFAULT_REQUEST_MAX_AGE_SECONDS,
    now: int | None = None,
) -> bool:
    """Timing-safe signature check + freshness window enforcement.

    Rejects both very-old (replay) and future-dated (clock skew attack)
    timestamps. ``now`` is injectable for tests.
    """
    current = now if now is not None else int(datetime.now(UTC).timestamp())
    if not isinstance(timestamp, int) and not str(timestamp).lstrip("-").isdigit():
        return False
    ts = int(timestamp)
    if ts > current + 5:
        return False
    if current - ts > max_age_seconds:
        return False
    expected = sign_request(payload, ts, secret)
    try:
        return hmac.compare_digest(expected, signature)
    except (TypeError, AttributeError):
        return False


# ═══════════════════════════════════════════════════════════════════════
# Suspicious activity detection
# ═══════════════════════════════════════════════════════════════════════


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class SuspicionResult:
    is_suspicious: bool
    reason: str | None
    severity: Severity | None


_KNOWN_IPS_PREFIX = "sec:known_ips"
_ORDER_RATE_PREFIX = "sec:order_rate"
_RECENT_IPS_PREFIX = "sec:recent_ips"


async def detect_suspicious_activity(
    user_id: str,
    action: str,
    metadata: dict[str, Any],
    *,
    redis_conn: aioredis.Redis | None = None,
    now: datetime | None = None,
) -> SuspicionResult:
    """Rule-based scanner — first rule that fires wins.

    Rules are ordered by severity so the worst finding bubbles up.
    """
    now = now or datetime.now(UTC)
    client = redis_conn or redis_client.get_redis()

    # HIGH — abnormal order burst
    if action == "order":
        rate_key = f"{_ORDER_RATE_PREFIX}:{user_id}"
        pipe = client.pipeline(transaction=False)
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60)
        count, _ = await pipe.execute()
        if int(count) > 100:
            return SuspicionResult(
                is_suspicious=True,
                reason="over 100 orders in one minute",
                severity=Severity.HIGH,
            )

    # MEDIUM — fat-finger-sized order
    if action == "order":
        qty = metadata.get("quantity")
        avg = metadata.get("user_avg_qty")
        if (
            isinstance(qty, (int, float))
            and isinstance(avg, (int, float))
            and avg > 0
            and qty > avg * 10
        ):
            return SuspicionResult(
                is_suspicious=True,
                reason="order size exceeds 10× user average",
                severity=Severity.MEDIUM,
            )

    # MEDIUM — too many distinct IPs
    ip = metadata.get("ip")
    if ip:
        recent_key = f"{_RECENT_IPS_PREFIX}:{user_id}"
        await client.sadd(recent_key, ip)
        await client.expire(recent_key, 3600)
        unique = await client.scard(recent_key)
        if int(unique) > 3:
            return SuspicionResult(
                is_suspicious=True,
                reason=f"{unique} distinct IPs in the last hour",
                severity=Severity.MEDIUM,
            )

        # LOW — new IP for this user
        known_key = f"{_KNOWN_IPS_PREFIX}:{user_id}"
        is_known = await client.sismember(known_key, ip)
        await client.sadd(known_key, ip)
        if not is_known:
            return SuspicionResult(
                is_suspicious=True,
                reason="login from new IP",
                severity=Severity.LOW,
            )

    # LOW — night-owl login (2AM – 5AM IST ≈ 20:30 – 23:30 UTC prev day)
    if action == "login":
        ist_hour = (now.hour + 5) % 24  # +5:30 but hour-precision is enough
        if 2 <= ist_hour < 5:
            return SuspicionResult(
                is_suspicious=True,
                reason="login between 02:00 and 05:00 IST",
                severity=Severity.LOW,
            )

    return SuspicionResult(is_suspicious=False, reason=None, severity=None)


# ═══════════════════════════════════════════════════════════════════════
# Password policy
# ═══════════════════════════════════════════════════════════════════════


_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "123456",
        "12345678",
        "123456789",
        "qwerty",
        "password",
        "password1",
        "password123",
        "111111",
        "letmein",
        "admin",
        "welcome",
        "iloveyou",
        "monkey",
        "dragon",
        "master",
        "abc123",
        "sunshine",
        "princess",
        "trustno1",
        "football",
        "baseball",
        "qwertyuiop",
        "charlie",
        "shadow",
        "freedom",
        "whatever",
        "superman",
        "batman",
        "jordan",
        "liverpool",
        "1234qwer",
        "zxcvbn",
        "zxcvbnm",
        "1q2w3e4r",
        "q1w2e3r4",
    }
)


@dataclass
class PasswordCheck:
    is_valid: bool
    reasons: list[str]


def validate_password_strength(
    password: str,
    *,
    email: str | None = None,
    name: str | None = None,
) -> PasswordCheck:
    reasons: list[str] = []
    if not isinstance(password, str):
        return PasswordCheck(is_valid=False, reasons=["password must be a string"])
    if len(password) < 8:
        reasons.append("minimum 8 characters")
    if not re.search(r"[A-Z]", password):
        reasons.append("at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        reasons.append("at least one lowercase letter")
    if not re.search(r"\d", password):
        reasons.append("at least one digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        reasons.append("at least one special character")
    if password.lower() in _COMMON_PASSWORDS:
        reasons.append("password is in the common-passwords list")
    if email:
        local_part = email.split("@", 1)[0].lower()
        if local_part and local_part in password.lower():
            reasons.append("password must not contain the email local part")
    if name:
        cleaned = name.lower().strip()
        if cleaned and len(cleaned) >= 3 and cleaned in password.lower():
            reasons.append("password must not contain the user's name")
    return PasswordCheck(is_valid=not reasons, reasons=reasons)


# ═══════════════════════════════════════════════════════════════════════
# Data sanitization
# ═══════════════════════════════════════════════════════════════════════


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SQL_COMMENT_RE = re.compile(r"(--|#|/\*|\*/)")
_SQL_KEYWORD_RE = re.compile(
    r"\b(?:drop|union|select|insert|update|delete|truncate|exec|alter)\b",
    re.IGNORECASE,
)
_CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_input(text: Any) -> str:
    """Strip HTML, control chars, and dangerous SQL tokens.

    Intended for free-form text like user-supplied labels and notes; do
    NOT run it over structured fields that legitimately contain SQL
    keywords (e.g. broker payload ``message`` content).
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = _CTRL_CHARS_RE.sub("", cleaned)
    cleaned = _SQL_COMMENT_RE.sub("", cleaned)
    cleaned = _SQL_KEYWORD_RE.sub("", cleaned)
    return cleaned.strip()


_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "old_password",
        "new_password",
        "api_key",
        "api_secret",
        "access_token",
        "refresh_token",
        "hmac_secret",
        "client_secret",
        "totp_secret",
        "jwt_secret",
        "encryption_key",
        "fernet_key",
        "confirmation_token",
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-signature",
    }
)


def sanitize_log_data(data: Any) -> Any:
    """Recursively scrub sensitive keys anywhere in the structure.

    Accepts dicts, lists, tuples — returns structurally identical output
    with sensitive values replaced by ``"***"``. Primitives pass through.
    """
    if isinstance(data, dict):
        return {
            k: (
                "***"
                if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS
                else sanitize_log_data(v)
            )
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [sanitize_log_data(v) for v in data]
    if isinstance(data, tuple):
        return tuple(sanitize_log_data(v) for v in data)
    if isinstance(data, bytes):
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return "<bytes>"
    return data


# ═══════════════════════════════════════════════════════════════════════
# JSON helper for callers that want one-shot log-safe dumps
# ═══════════════════════════════════════════════════════════════════════


def safe_json_dumps(data: Any) -> str:
    return json.dumps(sanitize_log_data(data), default=str, sort_keys=True)


__all__ = [
    "API_KEY_PREFIX",
    "ApiKeyMaterial",
    "DEFAULT_LOCK_MINUTES",
    "DEFAULT_LOGIN_ATTEMPTS",
    "DEFAULT_LOGIN_WINDOW_MINUTES",
    "DEFAULT_REQUEST_MAX_AGE_SECONDS",
    "LoginStatus",
    "PasswordCheck",
    "Severity",
    "SuspicionResult",
    "block_ip",
    "check_login_attempts",
    "create_session_token",
    "detect_suspicious_activity",
    "generate_api_key",
    "generate_session_fingerprint",
    "hash_api_key",
    "is_ip_blocked",
    "record_failed_login",
    "reset_login_attempts",
    "revoke_session_token",
    "safe_json_dumps",
    "sanitize_input",
    "sanitize_log_data",
    "sign_request",
    "unblock_ip",
    "validate_password_strength",
    "validate_session_fingerprint",
    "validate_session_token",
    "verify_api_key",
    "verify_signed_request",
]
