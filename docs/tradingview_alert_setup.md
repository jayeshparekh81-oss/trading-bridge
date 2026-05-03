# TradingView → TRADETRI Strategy Alert (BSE Ltd. swing — live)

Operational config for the TRADETRI strategy webhook for the BSE Ltd.
F&O swing strategy. Complements `tradingview-setup.md` (architectural
reference). The Monday rollout runs TRADETRI **live, in parallel with
the proven `server_final30mar.py`** — server keeps earning, TRADETRI
adds AI-validated swing entries.

> Symbol resolution + lot-multiple validation + product_type carry-forward
> all live in code as of the parser fix commit. **Verify each TV alert
> uses the dated front-month contract** (§2) — TV's `{{ticker}}` does not
> resolve.

## 1. Webhook URL

Use the direct backend URL (skips the Vercel rewrite hop and lets the
backend's TradingView-IP allowlist see TV's egress IP via ALB
`X-Forwarded-For`):

```
https://api.tradeforge.in/api/webhook/strategy/_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ
```

Token (paste the whole URL above; this row is for reference only):

```
_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ
```

> Alternative URL `https://tradetri.com/api/webhook/strategy/<token>`
> resolves via the Vercel `/api/*` rewrite to the EC2 backend, but adds
> a hop and lengthens the X-Forwarded-For chain. Prefer the direct URL.

## 2. Alert message body — BSE Ltd. swing (Pine v4.8.1)

Paste exactly into the TradingView alert **Message** field. Hardcode the
dated front-month contract — `{{ticker}}` (`BSE1!`) does NOT resolve in
Dhan's scrip master (see §6).

```json
{
  "symbol": "BSE-May2026-FUT",
  "action": "{{strategy.order.action}}",
  "quantity": 750,
  "instrument_type": "FUTURE",
  "product_type": "MARGIN",
  "order_type": "market",
  "price": {{close}},
  "signal_id": "{{strategy.order.id}}_{{time}}",
  "timestamp": "{{timenow}}"
}
```

Field semantics — important:

| Field | Value | Why |
|---|---|---|
| `symbol` | `BSE-May2026-FUT` | Dhan's canonical name; `BSE1!` MISSes |
| `quantity` | **total contracts** (e.g. `750` = 2 lots × 375) | Dhan API wants contracts, not lots. Webhook validates lot-multiple + even-lot rule for partial-profit strategies |
| `instrument_type` | `FUTURE` | **Informational** — preserved in `raw_payload`, not consumed by the webhook today. Useful in DB for grepping. |
| `product_type` | `MARGIN` (or `NRML`) | Carry-forward — required for swing. Without this, the executor defaults INTRADAY which auto-squares at 15:15 IST |
| `price` | `{{close}}` (no quotes) | Numeric — used as paper-mode fill price |
| `signal_id` | `{{strategy.order.id}}_{{time}}` | **Informational** — preserved in `raw_payload`. Useful for cross-referencing TV alert log with `strategy_signals.id` |

**Quantity rules enforced by the executor** (rejected with executor
error → signal status=`failed`, Telegram alert):

- `quantity > 0` and `<= 10000`
- `quantity % lot_size == 0` (i.e. whole-lot multiples of 375)
- `(quantity / lot_size) % 2 == 0` for any strategy with
  `partial_profit_lots > 0` — i.e. allowed sizes are 750 (2 lots), 1500
  (4 lots), 2250 (6 lots). 1 lot, 3 lots, 5 lots are rejected because
  the half-exit at Target 1 wouldn't be cleanly divisible.

Replace `BSE-May2026-FUT` each expiry cycle (see §6 for the
contract-discovery snippet).

### Running both webhooks in parallel

For Monday's hybrid observation, configure TWO webhook URLs in the
TradingView alert (TradingView allows up to 3 URLs per alert,
comma-separated in the Webhook URL field):

```
https://your-server-final30mar-url/<existing-token>,
https://api.tradeforge.in/api/webhook/strategy/_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ
```

Both receive the same body. The proven `server_final30mar.py` keeps
firing real orders; TRADETRI adds AI validation + Telegram observability.

No `signature` field is required: the backend bypasses HMAC for requests
arriving from TradingView's published egress IPs (the four addresses in
`tradingview_trusted_ips`, `backend/app/core/config.py:154`). All other
gates (rate limit, idempotency, kill-switch, time-of-day, max daily
trades) still apply.

If TradingView ever rotates their egress IPs and signals start being
rejected with 401, fall back to signing — see `tradingview-setup.md` §
"HMAC verification".

## 3. Steps to add the alert in TradingView

1. Open the TRADETRI Pine Script chart on the relevant symbol/timeframe.
2. Right-click the chart → **Add Alert** (or `Alt+A`).
3. **Condition**: select the TRADETRI strategy → "Any alert() function call".
4. **Options**: "Once Per Bar Close" (avoid intra-bar dupes; idempotency
   would absorb dupes anyway, but this keeps logs tidy).
5. **Notifications** → **Webhook URL**: paste the URL from §1.
6. **Message**: paste the JSON body from §2 verbatim.
7. **Expiration**: set 6 months out so the alert survives Monday-only
   testing.
8. Click **Create**.

## 4. First-fire smoke check (Monday 09:15 IST onward)

After the first signal lands, verify on AWS:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  'docker exec -i trading_bridge_postgres psql -U trading_bridge -d trading_bridge -c \
   "SELECT id, symbol, action, quantity, status, created_at \
    FROM strategy_signals ORDER BY created_at DESC LIMIT 5;"'
```

Expected: row with `status` advancing `received` → `executed` (paper
mode = simulated fill, no real broker order). A `strategy_executor.success`
log + `telegram_alerts.*` log should follow within ~5 s.

## 5. Changing or rotating the token

The token above is the active strategy webhook token (from
`webhook_tokens` table — stored as SHA256 hash; HMAC secret stored
Fernet-encrypted in `hmac_secret_enc`). Rotate via the TRADETRI dashboard
if it leaks; update both this file and the TradingView alert URL.

Token treatment: like a password. Do not commit alternates to the repo
or paste into Slack/issues.

## 6. Symbol format & monthly contract rollover

### Why TradingView `{{ticker}}` doesn't work

A Sun 2026-05-03 probe of the live Dhan scrip master (221 206 entries):

| Probed symbol | Result |
|---|---|
| `BSE1!`, `NIFTY1!` (TV continuous front-month) | **MISS** |
| `NSE:NIFTY`, `NIFTY!`, `BANKNIFTY!` | **MISS** |
| `NIFTY` bare → hits `NSE_EQ → 13` | the **index**, not tradable |
| `BSE-May2026-FUT` → hits `NSE_FNO → 66109` | ✅ canonical |
| `NIFTY-May2026-FUT` → hits `NSE_FNO → 66071` | ✅ canonical |

The executor's `DhanBroker.normalize_symbol` is a pass-through
(`.strip().upper()`). The TV alert must send the literal Dhan
`SEM_TRADING_SYMBOL` value or the executor raises
`BrokerInvalidSymbolError`.

### Find the current front-month contract (run each expiry)

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  "docker exec -i trading_bridge_backend python -" <<'PY'
import asyncio, httpx, re
from app.brokers.dhan import _SCRIP_MASTER
from app.core.config import get_settings

async def main():
    s = get_settings()
    async with httpx.AsyncClient() as h:
        await _SCRIP_MASTER.ensure_loaded(h, s.dhan_scrip_master_url)
    pattern = re.compile(r"^BSE-[A-Za-z]{3}\d{4}-FUT$")
    rows = sorted(
        ((sym, sid) for (sym, _seg), sid in _SCRIP_MASTER._by_symbol.items()
         if pattern.match(sym)),
        key=lambda x: x[0],
    )
    for sym, sid in rows[:5]:
        lot = _SCRIP_MASTER.lot_size(sid)
        print(f"  {sym!r:30} sid={sid:7} lot_size={lot}")

asyncio.run(main())
PY
```

The earliest dated contract is the front-month. Confirm `lot_size`
matches the `quantity` you intend to send (must be even multiple of
`lot_size` for the partial-profit-enabled strategy).

### Lot-size discrepancy alert

As of 2026-05-03, BSE Ltd. front-month (`BSE-May2026-FUT`) has
`lot_size = 375`. SEBI revisions can change this between expiries (e.g.
`BSE-Jul2026-FUT` is already at 200). **Always re-run the snippet above
when rolling to a new contract — don't assume lot_size is stable.**
