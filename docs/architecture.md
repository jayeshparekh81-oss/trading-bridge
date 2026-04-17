# Architecture

## High-Level Overview

```
TradingView Alert
       │
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   FastAPI     │────▶│    Redis     │     │  PostgreSQL  │
│  Webhook API  │     │  (Cache +    │     │  (Persistent │
│              │     │   Rate Limit) │     │   Storage)   │
└──────┬───────┘     └──────────────┘     └──────────────┘
       │
       ▼
┌──────────────┐     ┌──────────────────────────────────┐
│  Safety Gates │     │         Broker Registry          │
│  (7 layers)  │────▶│  Fyers │ Dhan │ Shoonya │ ...   │
└──────────────┘     └──────────────────────────────────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│ Order Service │────▶│   Celery     │
│ (Execution)  │     │  (Async Jobs)│
└──────────────┘     └──────────────┘
```

## Components

### API Layer (`app/api/`)
| Module | Purpose |
|--------|---------|
| `webhook.py` | TradingView webhook receiver — the heart of the bridge |
| `auth.py` | Registration, login, JWT tokens, password management |
| `users.py` | Profile, broker credentials, webhooks, strategies, trades |
| `admin.py` | User management, system health, audit logs |
| `kill_switch.py` | Kill switch status, config, reset, history |
| `health.py` | Liveness, readiness, detailed health checks |
| `deps.py` | FastAPI dependencies (auth gates) |

### Services Layer (`app/services/`)
| Module | Purpose |
|--------|---------|
| `order_service.py` | Webhook → broker order orchestration |
| `kill_switch_service.py` | Per-user daily loss/trade limits + auto square-off |
| `circuit_breaker_service.py` | Market volatility detection (ALLOW/PAUSE/HALT) |
| `pnl_service.py` | Real-time P&L tracking via Redis |
| `auth_service.py` | Authentication flows (register, login, tokens) |
| `notification_service.py` | Email (SES) + Telegram notifications |

### Broker Integrations (`app/brokers/`)
| Module | Status |
|--------|--------|
| `base.py` | Abstract `BrokerInterface` contract |
| `registry.py` | Broker class lookup by name |
| `fyers.py` | Fyers v3 API (complete) |
| `dhan.py` | Dhan HQ API (complete) |
| `shoonya.py` | Stub |
| `zerodha.py` | Stub |
| `upstox.py` | Stub |
| `angelone.py` | Stub |

### Core (`app/core/`)
| Module | Purpose |
|--------|---------|
| `config.py` | Typed settings from `.env` via pydantic-settings |
| `security.py` | Fernet encryption, bcrypt, HMAC, token generation |
| `security_ext.py` | Brute-force protection, JWT, session fingerprinting, password policy |
| `redis_client.py` | All Redis operations (cache, rate limit, kill switch, P&L) |
| `exceptions.py` | Typed `BrokerError` hierarchy |
| `logging.py` | Structured logging via structlog |
| `startup_checks.py` | Boot-time validation |

## Data Flow: Webhook to Order

```
1. POST /api/webhook/{token}
2. Token lookup (Redis cache → DB fallback)
3. Rate limit check (Redis counter, 60/min)
4. HMAC signature verification (timing-safe)
5. Payload validation (Pydantic)
6. Idempotency claim (Redis SET NX, 60s TTL)
7. Kill switch gate (Redis flag)
8. User active gate (DB check)
9. Max daily trades gate (Redis counter)
10. Circuit breaker gate (Redis state)
11. Strategy → broker credential resolution
12. Order dispatch (broker API call)
13. Trade recorded (DB insert)
14. P&L updated (Redis increment)
15. Kill switch re-evaluation
16. Audit event (background write)
```

## Security Layers

1. **Transport** — HTTPS/TLS (nginx termination)
2. **CORS** — Configurable allowed origins
3. **Request size** — 1MB body limit
4. **Rate limiting** — Per-user Redis counters
5. **HMAC verification** — Timing-safe webhook signatures
6. **JWT authentication** — Session fingerprinting + blacklist
7. **Brute-force protection** — 5 attempts → 1 hour lockout
8. **Password policy** — 8+ chars, mixed case, digits, special, no common
9. **Encryption at rest** — Fernet AES-128-CBC for broker credentials
10. **Input sanitization** — HTML/SQL injection prevention
11. **Kill switch** — Per-user daily loss limit
12. **Circuit breaker** — Market volatility protection
13. **Idempotency** — Duplicate signal prevention
14. **Audit trail** — Append-only security event log
15. **Security headers** — HSTS, CSP, X-Frame-Options

## Database Schema (12 Tables)

| Table | Purpose |
|-------|---------|
| `users` | Platform accounts (email, password_hash, prefs) |
| `broker_credentials` | Encrypted per-user broker sessions |
| `webhook_tokens` | Per-user webhook URLs with HMAC secrets |
| `strategies` | Webhook → broker credential bindings |
| `trades` | Every order placed (immutable audit) |
| `webhook_events` | Inbound webhook audit trail |
| `kill_switch_config` | Per-user thresholds (one row per user) |
| `kill_switch_events` | Trip history (append-only) |
| `audit_logs` | Security/action audit trail |
| `idempotency_keys` | Deduplication (auto-expiring) |
| `copy_trading_groups` | Phase 5 (schema only) |
| `copy_trading_followers` | Phase 5 (schema only) |

## Redis Key Patterns

| Prefix | Purpose | TTL |
|--------|---------|-----|
| `cache:` | General cache | Variable |
| `rate:` | Rate limit counters | 60s window |
| `kill:` | Kill switch status | No expiry |
| `kill_config:` | Cached config | 5 min |
| `kill_meta:` | Trip metadata | 24h |
| `idem:` | Idempotency slots | 60s |
| `pnl:` | Daily P&L counters | 24h |
| `pos:` | Position cache | 5 min |
| `login_attempts:` | Brute-force counter | 15 min |
| `login_lock:` | Account lockout | 1h |
| `session_blacklist:` | Revoked JWT tokens | Until expiry |
| `cb_state:` | Circuit breaker state | Variable |
