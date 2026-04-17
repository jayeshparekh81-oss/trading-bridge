"""OpenAPI documentation enhancements.

Provides the extended description and tag metadata used by the FastAPI
auto-generated docs at ``/docs`` and ``/redoc``.
"""

from __future__ import annotations

APP_TITLE = "Trading Bridge API"
APP_VERSION = "1.0.0"

APP_DESCRIPTION = """
# Trading Bridge API

India's fastest, strongest, most secure algo trading bridge.

## Overview

Trading Bridge receives **TradingView webhook alerts** and routes them as
live orders across multiple Indian brokers (Fyers, Dhan, Shoonya, Zerodha,
Upstox, AngelOne) with built-in risk controls.

## Authentication

All endpoints (except `/api/webhook/{token}` and `/health`) require a JWT
Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Get a token via `POST /api/auth/login`.

## Webhook Setup (TradingView → Trading Bridge)

1. **Register** — `POST /api/auth/register`
2. **Login** — `POST /api/auth/login` → save the `access_token`
3. **Add broker** — `POST /api/users/me/brokers` with encrypted credentials
4. **Create webhook** — `POST /api/users/me/webhooks` → save `webhook_token` + `hmac_secret`
5. **Create strategy** — `POST /api/users/me/strategies` linking webhook → broker
6. **Configure TradingView** — Set webhook URL to `POST /api/webhook/{token}`
   with `X-Signature` header containing HMAC-SHA256 of the payload

## Safety Gates

Every webhook passes through 7 safety gates before execution:
1. Rate limit (60/min per user)
2. HMAC signature verification
3. Idempotency deduplication
4. Kill switch check
5. User active check
6. Max daily trades check
7. Circuit breaker check

## Error Codes

| Code | Meaning |
|------|---------|
| 401 | Invalid/missing auth token or HMAC signature |
| 403 | Kill switch tripped, user inactive, or admin required |
| 404 | Resource not found |
| 409 | Duplicate (email already registered, duplicate signal) |
| 422 | Validation error (bad payload, broker rejection) |
| 429 | Rate limit exceeded or account locked |
| 502 | Broker connection error |
"""

TAGS_METADATA = [
    {
        "name": "auth",
        "description": "User registration, login, token refresh, logout, and password management.",
    },
    {
        "name": "users",
        "description": "User profile, broker credentials, webhooks, strategies, and trade history.",
    },
    {
        "name": "webhook",
        "description": "TradingView webhook receiver. Does NOT require JWT auth — uses webhook token + HMAC.",
    },
    {
        "name": "kill-switch",
        "description": "Per-user kill switch: status, config, reset, history, and dry-run testing.",
    },
    {
        "name": "admin",
        "description": "Admin-only: user management, system health, audit logs, announcements.",
    },
    {
        "name": "health",
        "description": "Liveness, readiness, and detailed health checks for monitoring.",
    },
]

CONTACT = {
    "name": "Trading Bridge Support",
}

LICENSE_INFO = {
    "name": "Proprietary",
}

__all__ = [
    "APP_DESCRIPTION",
    "APP_TITLE",
    "APP_VERSION",
    "CONTACT",
    "LICENSE_INFO",
    "TAGS_METADATA",
]
