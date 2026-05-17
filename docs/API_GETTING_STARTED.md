# API Getting Started

This guide is for external developers integrating with the TradeTri / Trading Bridge API. If you only want to use TradeTri from the web UI, you don't need this guide.

## What the API gives you

- Webhook receiver for TradingView alerts → orders routed to your broker
- Programmatic access to your own paper-trading and (later) live-trading accounts
- Audit log access for compliance and reconciliation
- Health and status endpoints for monitoring

What it does NOT give you:

- Access to other users' data (hard isolation per-user)
- Bulk-data exports of NSE prices (that's your broker's data, not ours)
- Mutating actions without explicit user authorization

## Authentication summary

Three auth modes:

| Endpoint family | Auth mode | Where the secret lives |
|---|---|---|
| `/api/auth/*` | Email + password → JWT | User provides per session |
| `/api/users/*`, `/api/kill-switch/*` | Bearer JWT (from login) | `Authorization: Bearer <token>` |
| `/api/webhook/tradingview/*` | HMAC-SHA256 signature | Per-strategy webhook secret |
| `/api/admin/*` | Admin JWT (separate scope) | Issued only to admin accounts |
| `/api/health/*` | None | Public |

JWT tokens are short-lived (15 min) and refreshed via a long-lived refresh token (7 days). Store refresh tokens securely; treat them like passwords.

## Webhook integration (the most common use)

Most external integrations are TradingView alerts → Trading Bridge → broker. The flow:

1. In TradeTri, create a strategy, which gives you a webhook URL + secret.
2. In TradingView, set up an alert with body matching our schema (see below).
3. TradingView calls our webhook; we verify HMAC; we run the 7 safety gates; we route the order.

### Webhook request shape

```http
POST https://api.tradetri.com/api/webhook/tradingview/<webhook_uuid>
Content-Type: application/json
X-Signature: sha256=<hex-hmac of body using your strategy secret>

{
  "strategy_id": "abc123",
  "symbol": "NIFTY24DEC22500CE",
  "side": "BUY",
  "qty": 50,
  "order_type": "MARKET",
  "price": null,
  "tag": "tv_alert_2026_05_18_0915"
}
```

### Response shapes

Success:

```json
{
  "accepted": true,
  "order_id": "ord_8f4a2c1b",
  "broker_order_id": "240412ABC1234",
  "queued_at": "2026-05-18T03:45:12.301Z"
}
```

Rejected (gate failure):

```json
{
  "accepted": false,
  "reason": "kill_switch_active",
  "gate_failed": "kill_switch_check",
  "queued_at": null
}
```

The seven safety gates run in order: HMAC signature → idempotency → kill switch → circuit breaker → broker availability → rate limit → margin check. The first to fail returns a specific `gate_failed` value so you can debug.

## Idempotency

Every webhook should include a `tag` field that uniquely identifies the alert. We dedupe on `(webhook_uuid, tag)` for 24 hours. TradingView retries are common during their infra hiccups; without idempotency you'd double-fire.

A good tag: `tv_alert_<strategy>_<timestamp>` or `tv_alert_<bar_iso>_<signal_id>`. Avoid using only the timestamp — multiple strategies can fire on the same bar.

## Rate limits

| Bucket | Limit | Reset |
|---|---|---|
| Per-IP unauthenticated | 60 req / 1 min | sliding 1 min |
| Per-user authenticated | 600 req / 1 min | sliding 1 min |
| Per-webhook | 30 alerts / 5 min | sliding 5 min |
| Per-strategy order placement | 10 orders / 1 min | sliding 1 min |

Hitting a rate limit returns HTTP 429 with a `Retry-After` header. Respect it; we don't penalize accounts that back off but we will throttle ones that keep hammering.

## Error model

Errors are typed JSON:

```json
{
  "error": {
    "code": "INVALID_SYMBOL",
    "message": "Symbol NIFTY24XYZ not in NSE F&O master",
    "request_id": "req_2026_05_18_03_45_12_abc"
  }
}
```

`request_id` is the only thing support needs to find your call in our logs. Include it in every bug report.

## Sample integrations

### Python (httpx + hmac)

```python
import hmac, hashlib, json, httpx

WEBHOOK_URL = "https://api.tradetri.com/api/webhook/tradingview/<uuid>"
SECRET = b"your_strategy_webhook_secret"

body = json.dumps({
    "strategy_id": "abc123",
    "symbol": "NIFTY24DEC22500CE",
    "side": "BUY",
    "qty": 50,
    "order_type": "MARKET",
    "tag": "tv_alert_2026_05_18_0915",
}).encode("utf-8")

sig = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()

resp = httpx.post(
    WEBHOOK_URL,
    headers={"Content-Type": "application/json", "X-Signature": sig},
    content=body,
    timeout=5.0,
)
print(resp.status_code, resp.json())
```

### Node.js (fetch + crypto)

```js
import crypto from "crypto";

const url = "https://api.tradetri.com/api/webhook/tradingview/<uuid>";
const secret = "your_strategy_webhook_secret";

const body = JSON.stringify({
  strategy_id: "abc123",
  symbol: "NIFTY24DEC22500CE",
  side: "BUY",
  qty: 50,
  order_type: "MARKET",
  tag: "tv_alert_2026_05_18_0915",
});

const sig = "sha256=" + crypto.createHmac("sha256", secret).update(body).digest("hex");

const r = await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Signature": sig },
  body,
});
console.log(r.status, await r.json());
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| 401 on webhook | Wrong HMAC. Confirm secret matches the one in TradeTri UI. |
| 401 on user endpoint | Expired access token. Refresh via `/api/auth/refresh`. |
| 403 with `gate_failed: kill_switch_active` | Daily loss limit hit; not a bug. |
| 503 with `gate_failed: broker_unavailable` | Broker session expired. Reauthorize from TradeTri UI. |
| 422 schema error | Body doesn't match our Pydantic models. Check the field that's listed. |

## Compliance notes

- We never proxy market data — your broker provides that. We just route orders.
- We're not an RIA (Registered Investment Advisor). We don't issue tips or guarantees.
- Funds stay with your broker at all times. We have no custody.
- If you build a product on top of our API and resell to end users, you need your own SEBI compliance posture — we can't extend ours to you.

## Where to look next

- [API_REFERENCE](api-reference.md) — Full endpoint list with request/response shapes
- [ARCHITECTURE_OVERVIEW](ARCHITECTURE_OVERVIEW.md) — How the system is wired
- [TradingView setup guide](tradingview-setup.md) — Step-by-step alert configuration

Questions? Open a GitHub issue or email developers@tradetri.com.
