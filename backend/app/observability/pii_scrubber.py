"""Shared PII scrubbing utilities.

Used by :mod:`analytics` (and the Sentry hook in :mod:`sentry`
already has its own equivalent) to keep emails / phones / names /
broker tokens out of every outbound observability stream.

Pure functions — no I/O, no module-level state. Easy to unit-
test, easy to compose.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

#: User-supplied properties that contain identifying or
#: business-sensitive information. Stripped from every analytics
#: payload regardless of which event fires.
_PII_PROPERTY_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "email_address",
        "phone",
        "phone_number",
        "telephone",
        "mobile",
        "full_name",
        "first_name",
        "last_name",
        "name",
        "password",
        "password_hash",
        "api_key",
        "secret",
        "secret_key",
        "access_token",
        "refresh_token",
        "jwt",
        "ip_address",
        "remote_addr",
        "broker_token",
        "broker_secret",
        "session_token",
    }
)

#: Keys whose name suggests a free-form business amount we don't
#: want in analytics (P&L magnitudes, individual trade sizes).
#: Aggregate-percentage variants (``win_rate``,
#: ``avg_pnl_percent``) stay opaque to this filter and pass.
_AMOUNT_PROPERTY_KEYS: frozenset[str] = frozenset(
    {
        "pnl_inr",
        "pnl",
        "amount_paid_inr",
        "trade_amount_inr",
        "capital_inr",
    }
)


def _hash_with_salt(value: str, salt: str) -> str:
    """SHA-256 of ``salt + ":" + value``, hex-encoded.

    The salt scopes a hash to a particular id family so a hashed
    user id can't be cross-referenced against a hashed listing
    id even if both happen to share the underlying UUID string
    by accident.
    """
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()
    return digest


def hash_user_id(user_id: str) -> str:
    """Stable, anonymised identifier for a user.

    Same input always produces the same output (so PostHog can
    de-duplicate events from the same user across sessions). The
    salt is the application-wide ``ANALYTICS_SALT`` env var when
    set; otherwise a hardcoded baseline so hashing still works in
    dev / test environments.
    """
    salt = os.environ.get("ANALYTICS_SALT") or "tradetri-analytics-v1"
    return _hash_with_salt(user_id, f"{salt}:user")


def hash_resource_id(resource: str, resource_id: str) -> str:
    """Anonymised identifier for a non-user resource (listing,
    strategy, ticket, etc.).

    Salted with ``resource`` so a hashed listing id and a hashed
    strategy id never collide even if the underlying UUIDs
    coincidentally match.
    """
    salt = os.environ.get("ANALYTICS_SALT") or "tradetri-analytics-v1"
    return _hash_with_salt(resource_id, f"{salt}:{resource}")


def scrub_properties_dict(properties: dict[str, Any]) -> dict[str, Any]:
    """Return a defensive copy of ``properties`` with every PII /
    amount key dropped.

    Only **direct** keys are scrubbed; nested dicts are not
    recursed because event properties should be flat by analytics-
    schema convention. If a future event needs nested structure,
    flatten it at the call site rather than nesting + relying on
    deep scrubbing here.
    """
    cleaned: dict[str, Any] = {}
    for key, value in properties.items():
        lower = key.lower()
        if lower in _PII_PROPERTY_KEYS or lower in _AMOUNT_PROPERTY_KEYS:
            continue
        cleaned[key] = value
    return cleaned


__all__ = [
    "hash_resource_id",
    "hash_user_id",
    "scrub_properties_dict",
]
