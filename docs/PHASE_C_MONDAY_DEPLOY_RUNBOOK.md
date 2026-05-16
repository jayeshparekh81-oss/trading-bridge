# Phase C — Monday Morning Deploy Runbook

Branch: `feat/phase-c-prep` (this prep) → `feat/phase-c-prep` updated Monday with the strategy_webhook integration → merged to `main` → deployed.

Deploy window: **Monday before market open (target 7:00 AM IST, hard stop 8:45 AM IST).** If anything in the pre-deploy checklist comes back YELLOW or RED, abort and reschedule.

Two live customers; BSE strategy actively executing trades. Treat every step as a live-fire operation.

---

## What's already done (this prep session)

* Cherry-picked `backend/app/services/futures_resolver.py` from `origin/feat/dockerfile-talib` onto `feat/phase-c-prep` — file landed identical to the source-of-truth version, **no modifications**.
* Added `backend/tests/services/test_futures_resolver.py` — **45 tests, 98% coverage** on the resolver.
* Added `backend/scripts/phase_c_prechecks.sql` — two SQL queries + a `trade_markers` cross-check.
* Added `backend/scripts/verify_bse_fut_segment.py` — downloads live scrip master, prints segment-label distribution for `BSE-*-FUT` rows.
* Did **NOT** cherry-pick the `strategy_webhook.py` integration. That's Step 2 below, applied Monday under supervision.

---

## STEP 1 — Pre-deploy checklist (Sunday evening / Monday early morning)

Run from a laptop with the prep branch checked out. Each item must pass before moving to STEP 2.

### 1.1 — Confirm latest DB backup exists

```bash
# On EC2 (43.205.195.227):
ls -lh /var/backups/tradetri/postgres/ | tail -5
```

The newest dump must be < 24 h old. If not, run `scripts/backup_postgres.sh` and wait for completion before proceeding.

### 1.2 — Run SQL pre-checks against prod Postgres

```bash
# On EC2:
docker exec -i tradeforge_postgres psql -U postgres -d tradetri \
  < backend/scripts/phase_c_prechecks.sql > /tmp/phase_c_precheck_$(date +%F).log
cat /tmp/phase_c_precheck_*.log
```

**Decision rule** (per the comments in `phase_c_prechecks.sql`):

| Output condition | Verdict | Action |
|---|---|---|
| Both queries empty | GREEN | Proceed to 1.3 |
| Result rows are all `BSE-<MMM>YYYY-FUT` form | GREEN | Proceed to 1.3 |
| Any `NSE:BSE`, `BSE1!`, `BSE:NSE`, or bare `BSE` row with `position_count > 0` (Q2) or with non-zero recent `signal_count` (Q1) | YELLOW | Run the position-symbol remap (script in §1.4) **before** STEP 2 |
| Any unfamiliar BSE-prefixed string | RED | **STOP**. Surface to Jayesh; do not deploy. |

**Save the log** — paste it into the deploy chat thread before STEP 2 so Jayesh can confirm the verdict.

### 1.3 — Verify Dhan scrip-master segment label

```bash
# Local (NOT on EC2 — keeps the live container untouched):
cd backend && \
  /path/to/.venv/bin/python scripts/verify_bse_fut_segment.py | tee /tmp/phase_c_segment_check.log
```

Expected last line: `GREEN: every BSE-*-FUT row carries the NSE_FNO segment label.`

If the script exits non-zero or prints `DEPLOY BLOCKER`, **STOP**. The resolver's segment filter (`NSE_FNO`) does not match what Dhan actually publishes for BSE futures, and the resolver would silently no-op for every BSE order. Surface to Jayesh and reschedule.

### 1.4 — (CONDITIONAL) Position-symbol remap script

Skip this step entirely if 1.2 came back GREEN.

If 1.2 came back YELLOW with non-canonical open positions, run a one-off update **before** the strategy_webhook patch lands:

```sql
-- Choose <ACTIVE-MONTH> by re-running the resolver locally for today's date,
-- OR by inspecting Q1/Q2 output for the canonical form already in use:
UPDATE strategy_positions
SET symbol = 'BSE-MAY2026-FUT'   -- <-- replace with the active-month form
WHERE symbol IN ('NSE:BSE', 'BSE1!', 'BSE:NSE', 'BSE')
  AND status = 'OPEN';
```

Re-run Q2 from `phase_c_prechecks.sql` and confirm zero rows remain in non-canonical form.

---

## STEP 2 — Deploy (Monday 7:00 AM IST, before market 9:15)

Hard cut-off: 8:45 AM IST. If we're not green by then, abort and reschedule for tomorrow.

### 2.1 — Cherry-pick strategy_webhook.py integration

```bash
git checkout feat/phase-c-prep
git checkout origin/feat/dockerfile-talib -- backend/app/api/strategy_webhook.py
git diff --stat
# Expected: 1 file changed, ~31 insertions
```

### 2.2 — Run the FULL test suite locally

```bash
cd backend && /path/to/.venv/bin/python -m pytest tests/ -v --tb=short
```

**Acceptance:**
* All 45 `test_futures_resolver.py` tests pass.
* All Phase A + Phase B tests still pass.
* Pre-existing 11 baseline failures from `TECH_DEBT_PRE_PHASE_A.md` are acceptable and unchanged.
* **No NEW failures introduced by the strategy_webhook patch.**

If any new failure appears, **STOP**. Do not push, do not deploy. Surface to Jayesh with full traceback.

### 2.3 — Commit + push prep branch

```bash
git add backend/app/api/strategy_webhook.py
git commit -m "feat(phase-c): integrate futures_resolver into strategy_webhook (cherry-pick from feat/dockerfile-talib)"
git push -u origin feat/phase-c-prep
```

### 2.4 — Merge to main

```bash
git checkout main
git pull --ff-only
git merge --no-ff feat/phase-c-prep -m "merge: feat/phase-c-prep — futures_resolver + strategy_webhook integration"
git push origin main
```

### 2.5 — Deploy to EC2

```bash
ssh tradetri@43.205.195.227
cd /opt/tradetri
git pull origin main
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend
```

**No migration needed** — Phase C is a pure code change; the `trade_markers` table was created in Phase A `025_add_trade_markers` and isn't touched.

### 2.6 — Smoke-test with one minimal BSE signal

After containers report healthy:

```bash
# On EC2 — tail logs in one window:
docker logs -f tradeforge_backend 2>&1 | grep -E 'futures_resolver|strategy_webhook.symbol_normalized'
```

In another window, fire a single test webhook (NOT a real customer signal — use a test strategy with minimum-lot quantity):

```bash
curl -X POST https://api.tradetri.com/strategy-webhook/<test-token> \
  -H 'Content-Type: application/json' \
  -d '{"symbol": "NSE:BSE", "action": "ENTRY", "side": "BUY", "quantity": 75}'
```

**Expected log lines:**
```
strategy_webhook.symbol_normalized       original=NSE:BSE  normalized=BSE-<MMM>YYYY-FUT
futures_resolver.continuous_future_resolved   original=NSE:BSE  resolved=BSE-<MMM>YYYY-FUT  expiry=...  picked_from=N
```

If no log line appears, the resolver is silently no-op'ing — investigate scrip-master state inside the container before letting real signals flow:

```bash
docker exec tradeforge_backend python -c "
from app.brokers.dhan import _SCRIP_MASTER
print('loaded:', _SCRIP_MASTER.is_loaded())
print('rows:', len(_SCRIP_MASTER._by_symbol))
print('BSE-*-FUT count:', sum(
    1 for s, seg in _SCRIP_MASTER._by_symbol
    if s.startswith('BSE-') and s.endswith('-FUT') and seg == 'NSE_FNO'
))
"
```

---

## STEP 3 — Verification (Monday 8:00 AM, before market open)

Watch the first real BSE signal of the day. Targets:

* `strategy_webhook.symbol_normalized` log line emitted.
* Persisted `strategy_signals.symbol` row carries `BSE-<MMM>YYYY-FUT`.
* Order placed on Dhan with the canonical symbol.
* Dhan response is `OK` / `TRANSIT` / `OPEN` (not `REJECTED`).

After market close (3:30 PM):

```bash
# Re-run the SQL pre-checks. Compare to morning's log.
docker exec -i tradeforge_postgres psql -U postgres -d tradetri \
  < backend/scripts/phase_c_prechecks.sql > /tmp/phase_c_postcheck_$(date +%F).log
diff /tmp/phase_c_precheck_*.log /tmp/phase_c_postcheck_*.log
```

**Expected:** new `BSE-<MMM>YYYY-FUT` rows in Q1 (`signal_count` increases). No new `NSE:BSE` / `BSE1!` rows. Position rows in Q2 should match the canonical form.

---

## STEP 4 — Rollback plan (if anything breaks)

Triggers for rollback:
* Any Dhan order rejection for a BSE order with `BrokerInvalidSymbolError`.
* Any `futures_resolver.no_contracts_found` or `futures_resolver.scrip_master_load_failed` ERROR for a real customer signal.
* New drift in `strategy_positions` (positions carrying a symbol that doesn't match Dhan's reported open positions).

### 4.1 — Revert the deploy

```bash
ssh tradetri@43.205.195.227
cd /opt/tradetri
git log --oneline -5      # find the previous-good commit (before the Phase C merge)
git checkout <previous-good-sha>
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend
```

### 4.2 — Revert the merge on main (after the live system is back to good)

```bash
# Locally:
git checkout main
git pull
git revert -m 1 <merge-commit-sha-of-phase-c>
git push origin main
```

The revert keeps history clean (no destructive `--force`). The Phase C work stays preserved on `feat/phase-c-prep` for re-attempt after fixing the root cause.

### 4.3 — Re-check positions table

```sql
-- Run Q2 from phase_c_prechecks.sql one more time. Confirm no
-- positions are stuck in a non-canonical form. If they are, run
-- the §1.4 remap update with the rollback target's expected symbol.
```

---

## What this runbook does NOT cover

* **The option drift** (`BSE-May2026-3600-CE`, `BSE-May2026-3700-CE` reported in the prior reconciliation report). The resolver only handles `-FUT` symbols; options are out of scope. Investigate separately as a manual reconciliation cleanup, not as part of this deploy.
* **Holiday-shifted last-Thursday expiries** (e.g. when NSE F&O moves expiry to Wednesday because Thursday is a holiday). The resolver computes last-Thursday from the calendar only — no holiday lookup. Document the carve-out and revisit when the indicator-sprint adds the NSE F&O holiday calendar feed.
* **Multi-broker support.** This integration is Dhan-specific. Fyers continues to receive whatever symbol the webhook layer hands it. Phase D+ if/when we add Fyers F&O.

---

## Sign-off checklist

Before STEP 2.4 (`merge to main`), confirm:

- [ ] STEP 1.1 — Backup verified, < 24h old
- [ ] STEP 1.2 — SQL pre-check log saved + Jayesh confirmed verdict
- [ ] STEP 1.3 — Segment-label verifier exited 0 (GREEN line printed)
- [ ] STEP 1.4 — (Conditional) Position remap done, Q2 re-verified
- [ ] STEP 2.2 — Full test suite green (only the 11 pre-existing baseline failures)
- [ ] Two-customer notice not required (no API contract change; only internal symbol normalization)

After STEP 2.6 (smoke test):

- [ ] Test signal logged `strategy_webhook.symbol_normalized`
- [ ] Test signal logged `futures_resolver.continuous_future_resolved`
- [ ] Dhan accepted the test order (or a clear non-resolver-related rejection — note in the chat)
- [ ] No ERROR logs from `futures_resolver.*` for the test signal

After market close (STEP 3):

- [ ] Post-deploy SQL diff shows canonical symbols in new rows
- [ ] No new drift in `strategy_positions` vs Dhan-reported positions
