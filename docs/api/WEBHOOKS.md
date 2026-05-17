# Webhooks — API reference

Source: `backend/app/api/webhook.py` + `backend/app/api/strategy_webhook.py`

Webhook ingestion for TradingView signals.

---

### `POST /api/webhook/{webhook_token}`

**Summary:** Legacy single-order webhook (Phase 1 path).

**Auth:** Token-only (no JWT). 43-char URL token.

**Request body:** `WebhookPayload` — `{symbol, side, quantity, ...}`.

**Responses:**
- `200` — Order placed
- `400` — Malformed payload
- `403` — HMAC signature invalid (when `webhook_require_hmac=True`)
- `404` — Unknown token
- `429` — Rate limit (60 req/60s per user)

---

### `POST /api/webhook/strategy/{webhook_token}`

**Summary:** Phase 5 strategy-engine webhook with AI gate.

**Auth:** Token-only. Optional HMAC via `X-Signature` header.

**Request body:** `StrategySignalIn`
```json
{
  "symbol": "NIFTY",
  "side": "BUY",
  "quantity": 75,
  "entry_price": 22000.0,
  "exchange": "NSE",
  ...
}
```

Pipeline:
1. Token lookup (Redis cache + DB fallback)
2. Rate limit (60/60s)
3. HMAC verify (when enabled)
4. Idempotency check (signal-hash dedup)
5. Kill-switch gate
6. AI gate (Phase 5 — calls AlgoMitra)
7. Persist `StrategySignal` row with status="received"
8. Dispatch to executor

**Responses:**
- `200` — Signal accepted (may not have placed an order yet — async path)
- `400` — Malformed payload
- `403` — HMAC or kill-switch
- `404` — Unknown token
- `409` — Duplicate signal (idempotency hit)
- `429` — Rate limit

---

### Cross-references

- HMAC verification: `backend/app/api/webhook.py:_verify_hmac`
- Kill-switch gate: `backend/app/api/kill_switch.py`
- Idempotency: `backend/app/core/redis_client.py` (signal-hash key namespace)
- Strategy signal model: `backend/app/db/models/strategy_signal.py`
