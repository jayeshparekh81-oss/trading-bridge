# Dhan Integration Test — Operator Runbook

**This is a manual founder-only pre-launch sanity check. NOT in CI/CD.**

The script `dhan_integration_test.py` exercises the live Dhan API
end-to-end: token validity → historical fetch → user funds →
SafetyChain preflight → dry-run order → optional real order. Use
it before each production deploy that touches the broker
integration; skip it for backend-only changes that don't go near
order placement.

## Pre-flight checklist

Before running ANY mode that hits the network:

- [ ] **Dhan access token is current.** Tokens expire; the
      cheapest check is `--check-token` first. If it fails with
      401, regenerate from the Dhan partner portal before
      proceeding.
- [ ] **Dhan client id matches the token.** The two are paired
      per partner credential.
- [ ] **Test capital available.** Approximately `₹100` is enough
      for a 1-lot NIFTY-test order. The script's quantity hard
      cap is 5 — you cannot accidentally place a large order.
- [ ] **Market hours** for any test that fetches recent candles
      or places an order: 9:15 AM – 3:30 PM IST, Mon–Fri,
      excluding NSE holidays. Token + funds checks work outside
      market hours.
- [ ] **Liquid symbol chosen.** Default is NIFTY (the index).
      For real-order tests, prefer NIFTY index futures or a
      heavily-traded stock (RELIANCE, HDFCBANK). Avoid mid/
      small-caps where slippage could hurt even a 1-lot test.
- [ ] **`.env` populated** at `backend/.env` with:
      ```
      DHAN_ACCESS_TOKEN=...
      DHAN_CLIENT_ID=...
      DATABASE_URL=postgres://.../tradetri
      TEST_USER_EMAIL=founder-test@tradetri.in
      TEST_STRATEGY_NAME=integration-test
      ```
- [ ] **Test user + strategy exist** in the database. The script
      does NOT auto-create them. Either:
      ```sql
      -- one-off: bootstrap test user with paper_sessions=7 + live enabled
      INSERT INTO users (email, password_hash, role, is_active,
                         paper_sessions_completed, live_trading_enabled)
      VALUES ('founder-test@tradetri.in', 'x', 'user', true, 7, true);
      ```
      ...and create a simple strategy via the UI or seed script.

## Honest caveat

This runbook was written + the script was tested *without* live
Dhan credentials. The dry-run-without-credentials codepath is
covered (every step skips cleanly). The real-network paths
(`/v2/profile`, `/v2/fundlimit`, historical fetch with valid
token) are wired correctly per the existing module signatures
but cannot be smoke-tested from a developer laptop. **First run
in production is the first integration test of those paths.**

## Run modes

```sh
# Cheapest possible signal — token + client id are valid.
./backend/scripts/dhan_integration_test.py --check-token

# Pull a day of NIFTY 5m candles (verifies fetcher + parser).
./backend/scripts/dhan_integration_test.py --test-historical

# Read your fund balance (zero risk — read-only API).
./backend/scripts/dhan_integration_test.py --test-funds

# Run the SafetyChain against the configured test (user, strategy).
./backend/scripts/dhan_integration_test.py --test-safety

# Full flow up to + including the dry-run order.
# This is the recommended pre-launch run — exercises the entire
# orchestrator without sending anything to the broker.
./backend/scripts/dhan_integration_test.py --test-flow

# Full flow + REAL order. Requires --live AND interactive 'CONFIRM'
# AND a 5-second countdown. Quantity is capped at 5; default 1.
./backend/scripts/dhan_integration_test.py --test-flow \
  --live --symbol NIFTY --quantity 1

# Every mode sequentially (most thorough — ~30 seconds without --live).
./backend/scripts/dhan_integration_test.py --all
```

## Expected output (happy path)

```
[INFO] detailed log: backend/scripts/logs/dhan_integration_20260510T053015Z.log
[INFO] base url: https://api.dhan.co/v2
[INFO] creds: token=set client_id=set

━━━ Step 1: Dhan token validity ━━━
  ✓ token_check — profile responded: dhanClientId=1101234567

━━━ Step 2: Historical data fetch (NIFTY, 5m, 1 day) ━━━
  ✓ historical_fetch — got 75 candles, latest close = 23845.5

━━━ Step 3: User funds (read-only) ━━━
  ✓ funds_check — available balance = 12450.75

━━━ Step 4: SafetyChain preflight (6 active checks) ━━━
      ✓ auto_kill_switch: Kill switch off — trading allowed.
      ✓ paper_sessions: 7+ paper sessions complete.
      ✓ trust_score: Trust score above threshold.
      ✓ truth_score: Truth check passed.
      ✓ live_trading_enabled: Live trading enabled (global + user).
      ✓ broker_connection: Dhan broker connected.
  ✓ safety_chain — all 6 checks passed

━━━ Step 5: Dry-run order (NIFTY, qty=1, dry_run=True) ━━━
  ✓ dry_run_order — order_id=DRY_RUN_SIMULATED, safety_passed=True

━━━ Summary ━━━
  PASS  token_check  (132.4ms)
  PASS  historical_fetch  (412.1ms)
  PASS  funds_check  (98.7ms)
  PASS  safety_chain  (12.3ms)
  PASS  dry_run_order  (24.9ms)

Totals: 5 passed, 0 failed, 0 skipped
```

## Common errors + fixes

### `HTTP 401` from token check

Token expired. Generate a fresh token from the Dhan partner
portal and update `DHAN_ACCESS_TOKEN` in `.env`.

### `historical_fetch — got 0 candles`

Market is closed and no candles fall in the requested window.
The fetcher itself worked — try again during market hours.

### `safety_chain — blocked by paper_sessions`

The test user hasn't completed 7 paper sessions yet. Either run
7 paper sessions for the test strategy first, or temporarily
bump `paper_sessions_completed` on the test user row (test data
only — never on a real user row).

### `safety_chain — blocked by live_trading_enabled`

Either the global `LIVE_TRADING_ENABLED` env var is unset, or
the test user's `live_trading_enabled` column is `false`. Both
need to be `true` for the chain to pass.

### `dry_run_order — broker_credential_id is null`

The test strategy doesn't have a Dhan credential linked. Connect
a broker via the dashboard's Brokers page first, then ensure
the strategy's `broker_credential_id` references that row.

### `real_order — dhan returned RMS error`

Dhan's risk-management system blocked the order at the broker
side. Reasons vary: insufficient margin, symbol restricted for
intraday, lot-size mismatch. Check the detailed log file for
the exact RMS message.

## If you accidentally placed a real order

1. **Open the Dhan app or web portal immediately.**
2. Find the order by id — the script logs it loudly at the end:
   ```
   🚨 ORDERS WERE PLACED — MANUALLY CANCEL IF NEEDED:
     → order_id = 1234567890123
   ```
3. If still pending → cancel from the broker UI.
4. If filled → square off via the Positions tab. Document the
   loss / gain for the post-incident note.
5. Update this runbook with whatever made the safeguards
   insufficient, so the next operator doesn't repeat the
   mistake.

## Logs

Every run drops a detailed file at
`backend/scripts/logs/dhan_integration_<UTC-timestamp>.log` next
to the script. Console output is colour-coded summary; the file
captures per-step request URLs, response shapes, and
millisecond timings — useful when a single step fails and you
want to know whether it was the network, the parser, or the
downstream gate.

## Safety summary (defence in depth)

| Layer | Defence |
| --- | --- |
| Default mode | `dry_run=True` everywhere; real orders need explicit `--live` |
| CLI flag | `--quantity` defaults to 1; hard cap at 5 (refused above) |
| Interactive | Must type `CONFIRM` (case-sensitive) at the prompt |
| Countdown | 5 seconds before placement; ctrl-C still aborts |
| Server | Backend SafetyChain (6 checks) blocks even valid `--live` orders if any gate fails |
| Broker | Dhan's own RMS rejects orders that fail margin / symbol / lot-size checks |

A real order requires every layer to consent. Any layer can veto.
