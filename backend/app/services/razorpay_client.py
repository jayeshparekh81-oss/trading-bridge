"""Thin Razorpay client wrapper — Phase 2 (Razorpay), Module 1.

Keeps the Razorpay SDK at the edge so the rest of the codebase imports cleanly
even when the SDK isn't installed or keys aren't set (the import is LAZY, inside
:func:`get_razorpay_client`). Tests mock this module — no live calls.

Secrets come from ENV via settings (``razorpay_key_id`` / ``razorpay_key_secret``
/ ``razorpay_webhook_secret``), default EMPTY. Nothing is hardcoded.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import verify_hmac_signature

logger = get_logger("app.services.razorpay_client")


class RazorpayConfigError(RuntimeError):
    """Razorpay is not configured (missing key id / secret)."""


def razorpay_configured() -> bool:
    """True only when BOTH the key id and secret are present (non-empty)."""
    s = get_settings()
    return bool(s.razorpay_key_id.get_secret_value()) and bool(
        s.razorpay_key_secret.get_secret_value()
    )


def get_razorpay_client() -> Any:
    """Build a Razorpay API client from env-supplied keys.

    LAZILY imports the ``razorpay`` SDK so this module imports without it.
    Raises :class:`RazorpayConfigError` when keys are empty (fail-closed — the
    billing endpoints never proceed against an unconfigured gateway).
    """
    s = get_settings()
    key_id = s.razorpay_key_id.get_secret_value()
    key_secret = s.razorpay_key_secret.get_secret_value()
    if not key_id or not key_secret:
        raise RazorpayConfigError(
            "Razorpay keys are not configured (set RAZORPAY_KEY_ID / "
            "RAZORPAY_KEY_SECRET in the environment)."
        )
    import razorpay  # lazy — SDK only needed when actually calling Razorpay

    return razorpay.Client(auth=(key_id, key_secret))


def verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify Razorpay's ``X-Razorpay-Signature`` over the raw body.

    Razorpay signs the EXACT request body with HMAC-SHA256 (hex) keyed by the
    webhook secret — identical to the platform's existing HMAC scheme — so we
    reuse :func:`app.core.security.verify_hmac_signature` (constant-time). A
    missing signature or empty secret is rejected (returns False).
    """
    if not signature or not secret:
        return False
    return verify_hmac_signature(body, signature, secret)


__all__ = [
    "RazorpayConfigError",
    "get_razorpay_client",
    "razorpay_configured",
    "verify_webhook_signature",
]
