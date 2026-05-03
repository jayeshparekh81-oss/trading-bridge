# Monday LIVE first-run runbook (2026-05-04)

State going in (set Sun 2026-05-03 evening):

```
STRATEGY_PAPER_MODE = false           ← LIVE
backend                = c9ee99d on AWS, healthy
strategy 89423ecc      = ai_validation_enabled=true,
                          exit_strategy_type=direct_exit,
                          entry_lots=4, partial_profit_lots=2
broker_credential      = Dhan, active, expires 2026-05-04 19:07 IST
                          (auto-login Mon 8:30 IST refreshes)
scrip-master cache     = pre-warmed at backend startup (221k entries)
Telegram alerts        = wired (verified ping 200)
```

## Pre-market — manual checklist (Mon 8:30-9:00 AM IST)

```
[ ] 8:30 AM — Auto-login cron fires automatically.
              Telegram should show "DHAN: ✅ OK" or similar.
              If absent, ssh AWS and run: /home/ubuntu/trading-bridge/venv/bin/python3 \
                /home/ubuntu/trading-bridge/scripts/auto_login.py
[ ] 8:35 AM — Sanity: curl -sf https://api.tradeforge.in/health
              Expect: {"status":"ok"}
[ ] 8:40 AM — TradingView: open the Pine alert, confirm webhook URL is the
              TRADETRI URL only:
              https://tradetri.com/api/webhook/strategy/_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ
              (Remove the server_final30mar URL if still present.)
[ ] 8:50 AM — Manual safety test (see "First live-Dhan order test" below).
[ ] 8:58 AM — Verify Dhan website: zero open positions before market open.
[ ] 9:00 AM — Standby. First Pine signal will be a real order.
[ ] 9:15 AM — MARKET OPEN. Real signals begin flowing.
```

## First live-Dhan order test (8:50 AM)

⚠️ **This places a REAL Dhan order.** Pre-market means it queues to 9:15 open.
The matching EXIT below queues too — both fill at the open. Tiny brokerage cost,
proves the wire works before real Pine signals arrive.

### Step A — fire ENTRY (real money, 2 lots = 750 contracts)

```bash
TS=$(date +%s)
curl -sS -X POST \
  https://tradetri.com/api/webhook/strategy/_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ \
  -H "Content-Type: application/json" \
  -d "{
    \"action\": \"ENTRY\",
    \"type\": \"LONG_ENTRY\",
    \"qty\": 2,
    \"useDhan\": true,
    \"symbol\": \"BSE-May2026-FUT\",
    \"price\": 3800,
    \"lot_size_hint\": 375,
    \"indicators\": {
      \"PriceSpd\": 7.0, \"ATR\": 5.5, \"LongMA\": 738, \"GaussL\": 745,
      \"SlowMA\": 745, \"GaussS\": 745, \"FastMA\": 745, \"VWAPDist\": 1.0,
      \"BullGap\": 200, \"Squeeze\": 6.0, \"BodyPct\": 70, \"Vol\": 400000,
      \"DeltaPwr\": 5.0, \"BearGap\": 80, \"RVOL\": 1.8, \"OFInten\": 2.0,
      \"RSI\": 62, \"ADX\": 25, \"MFI\": 55, \"STDir\": 1, \"OIBuild\": 1.5,
      \"MACDH\": 1.0
    },
    \"signal_id\": \"live_safety_${TS}_entry\"
  }"
```

**Expect:** HTTP 202 + signal_id in response.
**Verify:** Telegram alert "Order filled" within ~10s.
**Verify:** Dhan website → Positions tab → BSE Ltd. May2026 future visible (queued).

### Step B — IMMEDIATELY fire EXIT to close

```bash
curl -sS -X POST \
  https://tradetri.com/api/webhook/strategy/_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ \
  -H "Content-Type: application/json" \
  -d "{
    \"action\": \"EXIT\",
    \"type\": \"LONG_EXIT\",
    \"qty\": 0,
    \"useDhan\": true,
    \"symbol\": \"BSE-May2026-FUT\",
    \"signal_id\": \"live_safety_${TS}_exit\"
  }"
```

**Expect:** HTTP 202 + signal_id.
**Verify:** Telegram alert 🔴 EXIT.
**Verify:** Dhan website at 9:15:30 IST → zero open positions (entry + exit
filled at open, position flat with brokerage cost ~₹40-80 round-trip).

If both Telegram alerts arrive AND Dhan shows zero open positions after 9:15:
✅ TRADETRI live-mode is verified end-to-end. Stand by for Pine signals.

If anything is missing or wrong: trip the kill switch immediately
(see "Emergency procedures") and investigate before allowing Pine to fire.

## During market hours

Pine fires alerts on bar close. Each ENTRY: brain re-evaluates indicators,
either approves with a tier (2 or 4 lots) or rejects. Each PARTIAL/EXIT/SL_HIT:
acts on the open position directly (Pine drives, no brain).

Telegram should fire on every:
- Order placed (INFO)
- Order filled (SUCCESS)
- PARTIAL exit (📉 SUCCESS)
- EXIT (🔴 INFO)
- SL_HIT (🛑 WARNING)
- AI rejection (WARNING)
- Backend error (CRITICAL)

If Telegram goes quiet for >30 min during a known-active period, check:
1. `curl -sf https://api.tradeforge.in/health`
2. `ssh ubuntu@43.205.195.227 "docker logs --since=10m trading_bridge_backend 2>&1 | tail -30"`

## Emergency procedures

### Kill switch — stop all new orders + close open positions

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227 \
  'docker exec trading_bridge_backend python -c "\
import asyncio
from uuid import UUID
from app.db.session import get_sessionmaker
from app.services.kill_switch_service import kill_switch_service
async def main():
    async with get_sessionmaker()() as s:
        result = await kill_switch_service.test_trip(
            UUID(\"46a56dd5-492c-489a-a315-86204f36a022\"), s
        )
        print(result)
asyncio.run(main())
"'
```

This trips the kill switch for the user. New webhook signals are rejected
with 403. `square_off_all` runs against every active broker credential
(closes Dhan positions). CRITICAL Telegram alert fires.

### Reset kill switch (after the operator confirms safe)

```bash
USER_ID=46a56dd5-492c-489a-a315-86204f36a022

# Step 1: get a confirmation token
TOKEN=$(curl -s -X POST https://api.tradeforge.in/api/kill-switch/reset-token \
  -H "X-User-Id: ${USER_ID}" | python3 -c "import sys, json; print(json.load(sys.stdin)['confirmation_token'])")

# Step 2: reset
curl -X POST https://api.tradeforge.in/api/kill-switch/reset \
  -H "X-User-Id: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d "{\"confirmation_token\":\"${TOKEN}\"}"
```

### Force-revert to PAPER mode (rollback)

If the system is misbehaving and you need to flip back to paper mode:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227 \
  'cd ~/trading-bridge/backend && \
   sed -i "s/^STRATEGY_PAPER_MODE=false/STRATEGY_PAPER_MODE=true/" .env && \
   docker compose up -d --force-recreate backend && sleep 12 && \
   curl -sf http://localhost:8000/health && echo'
```

After this, no new webhook signals fire real orders. Existing open Dhan
positions remain open — close them manually via Dhan website or fire EXIT
webhooks.

### Backup .env files

The pre-flip .env is preserved at:
```
/home/ubuntu/trading-bridge/backend/.env.bak-pre-live-flip-20260503-142639
```

To restore exact pre-flip state:
```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227 \
  'cd ~/trading-bridge/backend && \
   cp .env.bak-pre-live-flip-20260503-142639 .env && \
   docker compose up -d --force-recreate backend'
```

## TradingView alert update (manual, must do before 9:00 AM)

1. Open TradingView, navigate to the BSE Ltd. F&O strategy chart.
2. Click the alert (⏰ icon) to edit.
3. **Webhook URL** field — replace contents with single URL:
   ```
   https://tradetri.com/api/webhook/strategy/_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ
   ```
   Remove `server_final30mar.py` URL if still listed.
4. **Alert message** field — leave unchanged (Pine's `f_msg_custom` already
   produces the correct shape).
5. Save.

## What's NOT happening Monday

- Server `server_final30mar.py` no longer receives the Pine webhook (URL
  removed in step 4 above). Server itself can keep running idle as a backup.
- TRADETRI's autonomous position_loop is NO-OP for direct-exit strategies —
  Pine drives every exit decision. Position-loop only ticks for the position
  to maintain `highest_price_seen` updates (paper-mode-only behavior; live
  mode skips entirely per `position_manager.py:111-130`).
- Self-learning, dynamic AVG, market intel, microstructure, regime detection
  — all OFF (Phase 2+). Brain runs on hardcoded v5 weights only.

## Quick reference

| Item | Value |
|---|---|
| Webhook URL | `https://tradetri.com/api/webhook/strategy/_XIFL4ajdBbEjyCUL6kRXfZf2ixCmyoNx6bW3x5fvEQ` |
| Backend host | `ubuntu@43.205.195.227` |
| SSH key | `~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem` |
| Strategy id | `89423ecc-c76e-432c-b107-0791508542f0` |
| User id | `46a56dd5-492c-489a-a315-86204f36a022` |
| Symbol | `BSE-May2026-FUT` (Dhan canonical) |
| Lot size | 375 |
| Front-month sec_id | 66109 |
| Telegram bot | `Tradetri_jayesh_alert_bot` |
| Telegram chat | 431466871 (Jayesh) |
