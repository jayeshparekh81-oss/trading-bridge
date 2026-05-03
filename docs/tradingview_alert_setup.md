# TradingView → TRADETRI Strategy Alert (Monday hybrid observation)

Operational config for the TRADETRI strategy webhook. This file complements
`tradingview-setup.md` (architectural reference) and is the copy-paste
source-of-truth for adding/updating the alert in TradingView.

> **Read §6 before going live.** Live-mode F&O orders will fail with the
> current symbol-resolution path; paper-mode observation (Monday plan) is
> unaffected.

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

## 2. Alert message body (Pine v4.8.1 compatible)

Paste exactly into the TradingView alert **Message** field. **Do NOT use
`{{ticker}}`** for the symbol field — see §6. Hardcode the active dated
contract instead.

```json
{
  "symbol": "NIFTY-May2026-FUT",
  "action": "{{strategy.order.action}}",
  "quantity": "{{strategy.order.contracts}}",
  "order_type": "market",
  "price": "{{close}}",
  "timestamp": "{{timenow}}"
}
```

Replace `NIFTY-May2026-FUT` each expiry cycle with the new front-month
contract (see §6 for how to query the canonical name).

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

## 6. CRITICAL — symbol format & live-mode blocker

### What we found (Sun 2026-05-03 probe)

A probe of the live Dhan scrip master (221 206 entries) showed that
none of TradingView's default `{{ticker}}` formats resolve:

| Probed symbol | Result |
|---------------|--------|
| `NIFTY1!` (TV continuous front-month) | **MISS** |
| `NIFTY!`, `NSE:NIFTY`                 | **MISS** |
| `BANKNIFTY1!`, `BANKNIFTY!`           | **MISS** |
| `NIFTY` (bare)                        | hits `NSE_EQ → 13` — this is the **index**, not tradable |
| `BANKNIFTY` (bare)                    | hits `NSE_EQ → 25` — also the index |
| `NIFTY-May2026-FUT`                   | hits `NSE_EQ → 66071` (a future, see segment caveat below) |

### Why this matters

The strategy executor calls `DhanBroker.get_security_id(symbol, NFO)`
without any TV→Dhan format translation (`backend/app/brokers/dhan.py:660`,
`normalize_symbol` is a pass-through `.strip().upper()`). The symbol the
TV alert sends must literally match Dhan's `SEM_TRADING_SYMBOL` column
or the executor raises `BrokerInvalidSymbolError`.

In **paper mode** the broker call is skipped, so today's observation is
unaffected. In **live mode** any signal carrying `NIFTY1!` / `BANKNIFTY1!`
will hard-fail.

### What to put in the TV alert

Hardcode the dated contract (e.g. `NIFTY-May2026-FUT`). Refresh on each
expiry. Find the active contract by querying the scrip master:

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
    pattern = re.compile(r"^(NIFTY|BANKNIFTY)-[A-Za-z]{3}\d{4}-FUT$")
    rows = sorted(
        ((sym, sid) for (sym, _seg), sid in _SCRIP_MASTER._by_symbol.items()
         if pattern.match(sym)),
        key=lambda x: x[0],
    )
    for sym, sid in rows[:20]:
        print(f"  {sym!r:30} -> {sid}")
asyncio.run(main())
PY
```

The earliest dated contract in the output is the front-month — that's
what TradingView should fire signals for.

### Live-mode blocker (Tuesday+ scope, NOT today)

There is also a parser bug to address before the live cutover. The Dhan
scrip-master CSV has a separate `SEM_SEGMENT` (or `SEM_INSTRUMENT_NAME`)
column that the current parser does NOT read
(`backend/app/brokers/dhan.py:240-265`). It only reads `SEM_EXM_EXCH_ID`
(values `NSE`/`BSE`/`MCX`), so every NSE row — equity AND F&O — gets
collapsed into segment `NSE_EQ`. The lookup path
`get_security_id(symbol, Exchange.NFO)` maps to segment `NSE_FNO` which
is therefore **empty**, and every live F&O order will MISS.

**Fix plan (do before flipping `STRATEGY_PAPER_MODE=false`):**
1. Probe Dhan's CSV for the actual segment column name (probable:
   `SEM_SEGMENT` taking values like `E`/`D`/`I`/`M`).
2. Update `_parse` in `app/brokers/dhan.py` to combine exchange + that
   column into the canonical segment.
3. Update tests/test_dhan_broker.py (the existing test fixture
   bypasses this column, so unit tests pass today even though prod is
   broken — fix the fixture too).
4. Re-run probe; expect non-empty `NSE_FNO` sample.

Don't ship this in the same commit as the docs — it needs the AWS
schema probe first.
