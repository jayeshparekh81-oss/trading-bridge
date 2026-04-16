"""Cryptographic primitives — the Shield layer.

Centralised so the rest of the codebase never reaches into ``cryptography``,
``bcrypt``, or ``hmac`` directly. That keeps:
    * key-loading logic in one place,
    * algorithm choices auditable,
    * timing-attack-safe comparisons mandatory.

All functions are pure (no I/O beyond reading the encryption key from env
the first time) and safe to call from sync or async contexts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from functools import lru_cache

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

#: Bcrypt cost factor. 12 ≈ 250ms on a 2024 laptop — strong enough for
#: rest-API password verification without DoS-ing the auth endpoint.
_BCRYPT_ROUNDS = 12

_ENCRYPTION_KEY_ENV = "ENCRYPTION_KEY"

_MISSING_KEY_HELP = (
    "ENCRYPTION_KEY environment variable is not set.\n"
    "Generate one with:\n"
    "    python -c \"from cryptography.fernet import Fernet; "
    "print(Fernet.generate_key().decode())\"\n"
    "Then export it (or add to .env): export ENCRYPTION_KEY=<generated-key>"
)


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    """Build the Fernet cipher once per process.

    Reads ``ENCRYPTION_KEY`` directly from ``os.environ`` rather than from
    :func:`app.core.config.get_settings` to keep this module importable
    without spinning up the full settings model — useful for migrations,
    one-off scripts, and the test suite.
    """
    raw = os.environ.get(_ENCRYPTION_KEY_ENV)
    if not raw:
        raise RuntimeError(_MISSING_KEY_HELP)
    try:
        return Fernet(raw.encode("utf-8"))
    except (ValueError, TypeError, InvalidToken) as exc:
        raise RuntimeError(
            f"ENCRYPTION_KEY is not a valid Fernet key ({exc}). "
            "It must be 32 url-safe base64-encoded bytes."
        ) from exc


def reset_cipher_cache() -> None:
    """Drop the cached cipher — for tests that rotate ``ENCRYPTION_KEY``."""
    _get_cipher.cache_clear()


# ═══════════════════════════════════════════════════════════════════════
# Symmetric encryption (Fernet — AES-128-CBC + HMAC-SHA256)
# ═══════════════════════════════════════════════════════════════════════


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential string for at-rest storage.

    Returns a url-safe base64 token containing IV + ciphertext + HMAC.
    Safe to store in a ``TEXT`` column.
    """
    if not isinstance(plaintext, str):
        raise TypeError("encrypt_credential expects str plaintext")
    return _get_cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a token previously produced by :func:`encrypt_credential`.

    Raises:
        InvalidToken: token was tampered with, truncated, or encrypted
            with a different key.
    """
    if not isinstance(ciphertext, str):
        raise TypeError("decrypt_credential expects str ciphertext")
    return _get_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


# ═══════════════════════════════════════════════════════════════════════
# HMAC (webhook signature verification)
# ═══════════════════════════════════════════════════════════════════════


def compute_hmac_signature(payload: bytes, secret: str) -> str:
    """Compute an HMAC-SHA256 signature, returned as lowercase hex.

    Hex output (vs. base64) so it round-trips cleanly through HTTP headers
    without padding ambiguity.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("compute_hmac_signature payload must be bytes")
    return hmac.new(
        secret.encode("utf-8"), bytes(payload), hashlib.sha256
    ).hexdigest()


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Constant-time verification of an HMAC-SHA256 signature.

    Uses :func:`hmac.compare_digest` so failure paths leak no per-byte
    timing — essential for the webhook endpoint where attackers can
    submit thousands of guesses.
    """
    expected = compute_hmac_signature(payload, secret)
    # Wrap in try/except — compare_digest raises on mismatched types,
    # which we treat as "invalid signature" rather than a 500.
    try:
        return hmac.compare_digest(expected, signature)
    except (TypeError, AttributeError):
        return False


# ═══════════════════════════════════════════════════════════════════════
# Password hashing (bcrypt)
# ═══════════════════════════════════════════════════════════════════════


def hash_password(plain: str) -> str:
    """Bcrypt-hash a password. Cost factor 12 — slow on purpose.

    Returns a self-describing ``$2b$12$...`` string safe to store in DB.
    """
    if not isinstance(plain, str):
        raise TypeError("hash_password expects str")
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash. Constant-time inside bcrypt."""
    if not isinstance(plain, str) or not isinstance(hashed, str):
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash string — treat as failed auth, never as 500.
        return False


# ═══════════════════════════════════════════════════════════════════════
# Token generation
# ═══════════════════════════════════════════════════════════════════════


def generate_webhook_token(length: int = 32) -> str:
    """Generate a url-safe random token for per-user webhook URLs.

    Uses :mod:`secrets` (CSPRNG). The default 32 → ~43 char string with
    ~256 bits of entropy.
    """
    if length < 16:
        raise ValueError("webhook token length must be at least 16 bytes")
    return secrets.token_urlsafe(length)


def generate_fernet_key() -> str:
    """Convenience wrapper used by setup scripts and tests."""
    return Fernet.generate_key().decode("utf-8")


def _is_valid_fernet_key(value: str) -> bool:
    """Best-effort shape check — used by config validation, not a hard guarantee."""
    try:
        decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
    except (ValueError, TypeError):
        return False
    return len(decoded) == 32


__all__ = [
    "compute_hmac_signature",
    "decrypt_credential",
    "encrypt_credential",
    "generate_fernet_key",
    "generate_webhook_token",
    "hash_password",
    "reset_cipher_cache",
    "verify_hmac_signature",
    "verify_password",
]
