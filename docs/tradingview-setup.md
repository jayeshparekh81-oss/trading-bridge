# TradingView → TRADETRI Strategy Engine setup

This guide configures a TradingView alert to fire signals into the
TRADETRI strategy execution engine. Day 1 (2026-04-28) supports paper
mode end-to-end; live trading flips on Thursday after the Wednesday
paper test passes.

## Webhook URL

```
https://tradetri.com/api/webhook/strategy/{webhook_token}
```

Replace `{webhook_token}` with your strategy's webhook token from the
TRADETRI dashboard. The token is a 32-byte URL-safe random string —
never share it; treat it like a password.

The endpoint is distinct from the legacy single-order endpoint
(`/api/webhook/{token}`). The strategy variant runs the AI-validation
gate and the multi-lot execution path.

## Pine Script alert payload

In TradingView, set the alert webhook URL to the address above and the
**Message** to the JSON below. Replace tokens as appropriate; the
`signature` field is required when TradingView's free tier prevents you
from sending the `X-Signature` header (free accounts cannot add custom
HTTP headers, so the in-body fallback is the default).

```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "quantity": "{{strategy.order.contracts}}",
  "order_type": "market",
  "price": "{{close}}",
  "timestamp": "{{timenow}}",
  "signature": "<hmac_sha256(canonical_body, hmac_secret)>"
}
```

* `symbol` — instrument identifier in your broker's vocabulary
  (e.g. `NIFTY24500CE`).
* `action` — `BUY`, `SELL`, or `EXIT`. `EXIT` closes the open position
  for the symbol and is recorded but not auto-executed in Day 1.
* `quantity` — lot count, capped at `4`. Anything above is rejected
  with HTTP 400.
* `order_type` — `market` for now (Day 4+ will support `limit`).
* `price` — optional; in paper mode it seeds the simulated fill price
  and the position-manager's target / SL math.
* `signature` — HMAC-SHA256 hex of the canonicalised body (same body,
  with the `signature` key removed, JSON-dumped with sorted keys and
  no whitespace).

## HMAC verification (header alternative)

If you can send custom headers (TradingView Pro), set the header
`X-Signature` to the HMAC of the raw body. The endpoint prefers the
header when both are present.

## Time-of-day guard

Signals received outside the IST trading window (09:15 — 15:25
weekdays) are rejected with HTTP 403. The AI validator is a second
line of defence; do not rely on either alone for risk control.

## What happens after the webhook fires

1. Signal lands → row in `strategy_signals` with `status='received'`.
2. Background task runs the AI validator (Claude). On `APPROVED`,
   `status='executing'` and the executor places the entry.
3. In paper mode, the executor simulates a fill at the payload `price`
   (or 0 if absent), opens a `strategy_positions` row, and records
   `strategy_executions` rows — one per leg.
4. The position-manager loop polls open positions every 5 s. In paper
   mode it skips broker calls; tests can drive transitions deterministically.

## Verifying a signal landed

```bash
# Replace TOKEN with your access token
curl -H "Authorization: Bearer $TOKEN" \
     https://tradetri.com/api/strategies/signals?limit=10
```

The response includes the AI decision + reasoning when present.

## Wed/Thu test plan

* **Wed paper test** — fire 2-3 alerts during market hours with `STRATEGY_PAPER_MODE=true`.
  Verify signal rows are created, AI validator decides, executor opens
  paper positions.
* **Thu live test** — flip `STRATEGY_PAPER_MODE=false` on the AWS box
  via `~/.bashrc`. Reconnect Dhan via UI (token rotation needed).
  Send one BUY 1-lot signal during market hours. Confirm a real
  broker order id appears.
* **Fri scale-up** — only if Thu was clean: 4-lot multi-leg test.
