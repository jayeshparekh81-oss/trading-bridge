# API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

## Authentication Flow

```
1. POST /api/auth/register   → Create account
2. POST /api/auth/login      → Get JWT tokens
3. Use Authorization: Bearer <access_token> for all requests
4. POST /api/auth/refresh    → Refresh expired access token
5. POST /api/auth/logout     → Invalidate token
```

## Endpoints by Tag

### Auth (`/api/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | No | Register new user |
| POST | `/api/auth/login` | No | Login, get JWT tokens |
| POST | `/api/auth/refresh` | No | Refresh access token |
| POST | `/api/auth/logout` | Bearer | Blacklist current token |
| POST | `/api/auth/change-password` | Bearer | Change password |
| GET | `/api/auth/me` | Bearer | Get current user profile |

### Users (`/api/users`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/users/me` | Get profile |
| PUT | `/api/users/me` | Update profile |
| GET | `/api/users/me/brokers` | List broker connections |
| POST | `/api/users/me/brokers` | Add broker credentials |
| PUT | `/api/users/me/brokers/{id}` | Update broker |
| DELETE | `/api/users/me/brokers/{id}` | Remove broker |
| GET | `/api/users/me/brokers/{id}/status` | Check session health |
| POST | `/api/users/me/brokers/{id}/reconnect` | Force re-login |
| GET | `/api/users/me/webhooks` | List webhook tokens |
| POST | `/api/users/me/webhooks` | Generate webhook + HMAC |
| DELETE | `/api/users/me/webhooks/{id}` | Revoke webhook |
| GET | `/api/users/me/webhooks/{id}/test` | Test webhook |
| GET | `/api/users/me/strategies` | List strategies |
| POST | `/api/users/me/strategies` | Create strategy |
| PUT | `/api/users/me/strategies/{id}` | Update strategy |
| DELETE | `/api/users/me/strategies/{id}` | Deactivate strategy |
| GET | `/api/users/me/trades` | Trade history (paginated) |
| GET | `/api/users/me/trades/export` | Export CSV |
| GET | `/api/users/me/trades/stats` | Win rate, P&L stats |

### Webhook (`/api/webhook`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/webhook/{token}` | HMAC | Receive TradingView alert |

### Kill Switch (`/api/kill-switch`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/kill-switch/status` | Live status (ACTIVE/TRIPPED) |
| GET | `/api/kill-switch/config` | Current thresholds |
| PUT | `/api/kill-switch/config` | Update thresholds |
| POST | `/api/kill-switch/reset-token` | Request reset token |
| POST | `/api/kill-switch/reset` | Manual reset |
| GET | `/api/kill-switch/history` | Trip history |
| POST | `/api/kill-switch/test` | Dry-run simulation |
| GET | `/api/kill-switch/daily-summary` | P&L summary |

### Admin (`/api/admin`) — requires admin role

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/users` | List all users |
| GET | `/api/admin/users/{id}` | User detail + stats |
| POST | `/api/admin/users` | Create user |
| PUT | `/api/admin/users/{id}/activate` | Activate/deactivate |
| PUT | `/api/admin/users/{id}/admin` | Grant/revoke admin |
| POST | `/api/admin/users/{id}/reset-kill-switch` | Admin reset |
| GET | `/api/admin/audit-logs` | Audit log viewer |
| GET | `/api/admin/system-health` | System metrics |
| GET | `/api/admin/broker-health` | Per-broker stats |
| GET | `/api/admin/kill-switch-events` | All trip events |
| POST | `/api/admin/announcements` | Send announcement |

### Health (`/health`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/health/ready` | Readiness (DB + Redis) |
| GET | `/health/detailed` | Full diagnostics |

## Webhook Setup Guide

### Step 1: Create Webhook Token

```bash
curl -X POST http://localhost:8000/api/users/me/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label": "nifty-strategy"}'
```

Response:
```json
{
  "id": "uuid",
  "webhook_token": "abc123...",
  "hmac_secret": "xyz789...",
  "webhook_url": "/api/webhook/abc123..."
}
```

### Step 2: Configure TradingView Alert

- **Webhook URL**: `https://your-domain.com/api/webhook/abc123...`
- **HTTP Header**: `X-Signature: <HMAC-SHA256 of body with hmac_secret>`
- **Body**:
```json
{
  "action": "BUY",
  "symbol": "NIFTY25000CE",
  "exchange": "NSE",
  "quantity": 50,
  "order_type": "MARKET",
  "product_type": "INTRADAY"
}
```

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Webhook | 60 requests/minute per user |
| Login | 5 attempts → 1 hour lockout |
| General API | No hard limit (fair use) |

## Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

Broker errors include additional fields:
```json
{
  "error": "BrokerOrderRejectedError",
  "broker": "FYERS",
  "message": "Insufficient margin",
  "reason": "margin_check_failed"
}
```
