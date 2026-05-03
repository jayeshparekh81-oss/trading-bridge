# Monday Morning Runbook — TRADETRI hybrid observation (2026-05-04)

Single page. Print or keep open in a tab. Times are IST.

State going in: paper mode ON (`STRATEGY_PAPER_MODE=true`),
TRADETRI observing alongside `server_final30mar.py`. No real Dhan orders
fire; all signals/AI/positions are simulated end-to-end.

> **Live-mode blocker exists.** A scrip-master parser bug means F&O
> symbol resolution is broken in live mode (paper mode is unaffected).
> Do NOT flip `STRATEGY_PAPER_MODE=false` until the Dhan segment fix
> ships. Details in `docs/tradingview_alert_setup.md` §6.

## ARCHITECTURE MISMATCH IDENTIFIED — work pending

User strategy uses **DIRECT-EXIT model**: Pine Script sends explicit
webhook actions and owns all exit decisions itself.

- `"action": "ENTRY"` — open position
- `"action": "PARTIAL"` with `"closePct": 50` — Pine decides when partial
  fires (its own ATR-based logic)
- `"action": "EXIT"` — Pine decides when full exit fires
  (Brahmastra gear-shifting trail, dynamic stops)

`server_final30mar.py` is a thin forwarder — it just translates the
incoming action into a Dhan order and stays out of the way.

TRADETRI uses **INTERNAL-EXIT model**: the position_loop calculates
target / SL / trail internally from `Strategy.partial_profit_target_pct`
/ `hard_sl_pct` / `trail_offset_pct` and triggers exits autonomously.

These two models are incompatible for direct merge — TRADETRI would
double-act on Pine's signals (Pine fires PARTIAL, TRADETRI's internal
logic also tries to fire one). **Cannot reconcile tonight.**

**Status for Monday 2026-05-04:** TRADETRI = paper observation only.
Real trades continue on `server_final30mar.py` (proven 4-month income).

**Next work (Tuesday-Wednesday refactor):**
- Webhook handler: accept `"action": "PARTIAL"` with `closePct` →
  exit `closePct%` of the open position
- Webhook handler: accept `"action": "EXIT"` → close full position
- New `Strategy.exit_strategy_type` flag with values `internal_exit`
  (current) and `direct_exit` (Pine-driven) — `direct_exit` skips the
  position_loop's autonomous target/SL/trail logic
- Tests for ENTRY → PARTIAL → EXIT flow end-to-end
- AWS E2E with full Pine action sequence

Until that refactor lands, keep `STRATEGY_PAPER_MODE=true` for TRADETRI.

## 08:30 IST — Auto-login (system cron, hands-off)

Cron runs automatically; this step is **verification only**.

- **Where**: ubuntu user crontab on EC2.
- **Schedule**: `30 8 * * 1-5`
- **Command**: `/home/ubuntu/trading-bridge/venv/bin/python3 /home/ubuntu/trading-bridge/scripts/auto_login.py`
- **Log**: `/home/ubuntu/trading-bridge/logs/auto_login.log`

Verify it fired:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  'tail -n 50 /home/ubuntu/trading-bridge/logs/auto_login.log'
```

Look for today's date and a success line near 08:30:xx. If absent, see
**Auto-login failure** under Emergency procedures.

## 09:00 IST — TradingView alert config check

15-minute window before market open. Confirm the alert is armed.

1. Open TradingView → Alerts panel.
2. Confirm the TRADETRI alert is **Active** (green dot).
3. Webhook URL ends in `_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ`.
4. Message body matches `docs/tradingview_alert_setup.md` §2 — in
   particular the `symbol` field is the hardcoded dated contract
   (e.g. `NIFTY-May2026-FUT`), **not** `{{ticker}}`.
5. Expiration is in the future.

If the alert is paused or expired, re-enable / extend.

## 09:15 IST — Market open observation

Backend should already be healthy from overnight uptime; sanity-check:

```bash
curl -sf https://api.tradeforge.in/health && echo OK
```

Watch for the first signal (may take minutes — depends on Pine
strategy). When one fires, a Telegram alert lands within ~5 s.

Live tail of strategy signals:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  'docker logs -f --tail=50 trading_bridge_backend \
    | grep -E "strategy_webhook|strategy_executor|kill_switch"'
```

Compare TRADETRI's paper signal stream against `server_final30mar.py`'s
real signal stream (your existing dashboards). Note divergences for
post-mortem; do **not** flip live mode today.

## 15:15 IST — Auto square-off (Celery beat, hands-off)

Auto square-off runs via Celery beat (`auto-square-off` schedule,
`backend/app/tasks/celery_app.py:54`). In paper mode this still walks
the simulated open-position rows and closes them. Confirm in logs:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  'docker logs --since=10m trading_bridge_celery_beat trading_bridge_celery_worker 2>&1 \
    | grep auto_square_off'
```

(Container names may be `trading_bridge_celery_*` — adjust if
`docker ps` shows different names.)

## 15:30 IST — Reconciliation check

Reconciliation loop (`app/workers/reconciliation_loop.py`) runs every
60 s in the FastAPI process. **It is a no-op while paper mode is on**
because there is no broker side to reconcile. Today's check is "no
errors logged":

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  'docker logs --since=8h trading_bridge_backend 2>&1 \
    | grep -E "reconciliation_loop|reconciliation\." | tail -20'
```

Expected: a stream of `reconciliation.skipped_paper_mode` debug lines
(or silence at default log level) and no `reconciliation_loop.tick_failed`
errors. A `tick_failed` here is the only signal worth investigating
today.

## 16:00 IST — Daily summary

Telegram daily-summary task fires at 16:00 IST (Celery beat
`daily-summary-notification`). If it lands, the wire is healthy. If
not, check `celery_beat` and `celery_worker` logs.

## End-of-day — Capture observations

For Tuesday's go/no-go on 1-lot live, jot:

- Total signals received (`SELECT count(*) FROM strategy_signals WHERE created_at::date = CURRENT_DATE;`)
- AI approved vs rejected counts.
- Symbol resolution failures (search backend logs for `symbol_resolution`).
- Any 4xx/5xx on the strategy webhook (search for `strategy_webhook` + `HTTPException`).
- Divergence vs `server_final30mar.py` signal log.
- Status of the Dhan-segment parser fix (live-mode blocker, see
  `docs/tradingview_alert_setup.md` §6).

## Emergency procedures

### Trip kill switch manually

```bash
USER_ID=<your-user-uuid>
curl -X POST https://api.tradeforge.in/api/kill-switch/test \
  -H "X-User-Id: ${USER_ID}"
```

`/api/kill-switch/test` runs the real trip path (square-off + audit log
+ Telegram CRITICAL alert) but is safe to invoke since paper mode is on.
In live mode it would issue real `square_off_all` to every connected
broker. See `backend/app/api/kill_switch.py:132`.

### Reset kill switch after a trip

```bash
# Step 1: get a confirmation token
curl -s -X POST https://api.tradeforge.in/api/kill-switch/reset-token \
  -H "X-User-Id: ${USER_ID}"
# → {"confirmation_token":"..."}

# Step 2: reset using that token
curl -X POST https://api.tradeforge.in/api/kill-switch/reset \
  -H "X-User-Id: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{"confirmation_token":"<paste-token>"}'
```

### Force-stop the backend (last resort)

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  'cd ~/trading-bridge && \
   docker compose stop backend celery_worker celery_beat'
```

This stops new signal acceptance immediately. Restart with `up -d`
when ready.

### Auto-login failure

If `/home/ubuntu/trading-bridge/logs/auto_login.log` shows an error or
no entry for today:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  '/home/ubuntu/trading-bridge/venv/bin/python3 \
   /home/ubuntu/trading-bridge/scripts/auto_login.py 2>&1 | tail -40'
```

If TOTP fails, refresh the broker session manually via the UI
(`https://tradetri.com/brokers`) before market open.

### Telegram alerts silent

Quick connectivity test:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem \
  ubuntu@43.205.195.227 \
  'source ~/trading-bridge/backend/.env && \
   curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="manual ping $(date)"'
```

If the ping arrives but signal-fire alerts don't, the Telegram client is
healthy and the issue is upstream (signal not reaching the executor).

## What is NOT happening today

- No real Dhan orders. `STRATEGY_PAPER_MODE=true` is the live setting;
  any "executed" position is simulated.
- No flip to live mode. Tuesday's decision is data-driven from today,
  AND gated on the Dhan-segment parser fix.
- No reconciliation drift alerts (loop is a no-op in paper mode).
